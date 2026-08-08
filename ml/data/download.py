"""License-gated dataset acquisition: automated download + manual import.

Guarantees:
- Refuses to act until the operator confirms the license (--accept-license);
  the gate message points at the exact page where terms were checked.
- Verifies downloads are really zip archives (PK signature), because mirror
  endpoints change shape (JSON wrappers) without notice.
- Extracts manually member-by-member: deterministic order, path-traversal validation,
  Windows MAX_PATH-safe writes, and a completion marker that marks a tree as usable
  (partial extractions self-heal). "Download All"-style archives resolve to the nested
  *without-augmentation* archive to prevent augmented duplicates leaking into splits.
- HTTP 403 (DownloadForbiddenError) fails fast with manual-route guidance:
  the automated client is refused by the source, and we do NOT bypass access
  controls (no UA spoofing, session tricks) nor retry forbidden endpoints.
- Manual import routes (user-provided --archive / --directory) are verified
  structurally before any use.
- Always writes PROVENANCE.json: source, version, DOI, citation, license,
  access date, acquisition method, checksums (spec §6).
"""

import hashlib
import json
import logging
import os
import re
import shutil
import time
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import requests

from ml.data import classmap, verify
from ml.data.registry import REGISTRY, DatasetSpec, ProgrammaticStatus
from ml.data.winpath import windows_safe

logger = logging.getLogger("cropmind.ml.download")


class LicenseNotAcceptedError(RuntimeError):
    pass


class DownloadError(RuntimeError):
    pass


class DownloadForbiddenError(DownloadError):
    """HTTP 403: the source refused the automated request.

    We do not bypass access controls (no UA spoofing, session tricks, or other
    workarounds). The manual/browser route is the documented alternative.
    """


def _fetch(url: str, dest: Path, log_every_mb: int = 64) -> int:
    """Stream url -> dest. Raises on non-200 or JSON responses; 403 gets its own class."""
    logger.info("downloading %s", url)
    with requests.get(url, stream=True, timeout=(10, 300), allow_redirects=True) as r:
        if r.status_code == 403:
            raise DownloadForbiddenError(f"HTTP 403 from {url}")
        if r.status_code != 200:
            raise DownloadError(f"HTTP {r.status_code} from {url}")
        if "json" in r.headers.get("content-type", ""):
            raise DownloadError(f"endpoint returned JSON instead of an archive: {url}")
        total = int(r.headers.get("content-length") or 0)
        written, next_log = 0, log_every_mb << 20
        with open(dest, "wb") as fh:
            for chunk in r.iter_content(chunk_size=1 << 20):
                if not chunk:
                    continue
                fh.write(chunk)
                written += len(chunk)
                if written >= next_log:
                    mb, total_mb = written / (1 << 20), total / (1 << 20)
                    logger.info("  %.0f MB downloaded%s", mb, f" / {total_mb:.0f} MB" if total else "")
                    next_log += log_every_mb << 20
    return written


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def is_zip_archive(path: Path) -> bool:
    with open(path, "rb") as fh:
        return fh.read(4) == b"PK\x03\x04"


# Written only after the LAST member is extracted; its presence marks the tree complete.
# A crashed/partial extraction has no marker and self-heals by re-extracting (deterministic overwrites).
EXTRACTION_MARKER = ".extracted-ok"

_DRIVE_PREFIX = ("A:", "B:", "C:", "D:", "E:", "F:", "G:", "H:", "I:", "J:", "K:", "L:", "M:",
                 "N:", "O:", "P:", "Q:", "R:", "S:", "T:", "U:", "V:", "W:", "X:", "Y:", "Z:")


def _validate_member_name(name: str, archive: Path) -> list[str]:
    """Normalized path segments for one archive member; rejects zip-slip/absolute/drive forms."""
    if len(name) >= 3 and name[1] == ":" and name[2] in ("/", "\\") and name[0].upper() + ":" in _DRIVE_PREFIX:
        raise DownloadError(f"unsafe path in archive {archive.name}: {name!r} (drive-letter prefix)")
    parts = [part for part in name.replace("\\", "/").split("/") if part not in ("", ".")]
    if name.startswith(("/", "\\")):
        raise DownloadError(f"unsafe path in archive {archive.name}: {name!r} (absolute path)")
    if ".." in parts:
        raise DownloadError(f"unsafe path in archive {archive.name}: {name!r} (path traversal)")
    return parts


_ILLEGAL_SEGMENT_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_RESERVED_NAMES = (
    {"con", "prn", "aux", "nul"} | {f"com{i}" for i in range(1, 10)} | {f"lpt{i}" for i in range(1, 10)}
)


def sanitize_segment(name: str) -> str:
    """Deterministic filesystem-safe path segment (identity for already-safe names).

    Windows forbids `<>:"/\\|?*` and control characters in every path segment, strips
    trailing dots/spaces, and reserves device names — archive members genuinely ship such
    names (PlantDoc: `IMG_1629.JPG?1507122477.jpg`). Applied identically on every OS so an
    extraction is byte-for-byte reproducible cross-platform.
    """
    cleaned = _ILLEGAL_SEGMENT_CHARS.sub("_", name).rstrip(" .")
    if not cleaned:
        cleaned = "_"
    if cleaned.split(".", 1)[0].lower() in _RESERVED_NAMES:
        cleaned = "_" + cleaned
    return cleaned


def _renamed_members_block(renames: list[tuple[str, str]]) -> dict:
    """Provenance subsection recording filesystem-safety renames (never silent, never deleted)."""
    if not renames:
        return {}
    return {
        "extraction": {
            "renamed_count": len(renames),
            "renamed_examples": [
                {"member": original, "written_as": written} for original, written in renames[:10]
            ],
            "policy": (
                "Members whose names Windows forbids are renamed deterministically at extraction, "
                "and case-insensitive filename clashes (e.g. car1.jpg vs CAR1.jpg) are deduped "
                "with ~2/~3… suffixes — nothing is ever overwritten; every rename is recorded here."
            ),
        }
    }


def _bump_segment(segment: str, n: int) -> str:
    """`name.jpg` -> `name~2.jpg`; extension preserved so image loading by suffix still works."""
    stem, dot, ext = segment.rpartition(".")
    if dot and stem:
        return f"{stem}~{n}{dot}{ext}"
    return f"{segment}~{n}"


def _dedupe_file_parts(
    safe_parts: list[str], member_name: str, seen: dict[str, str]
) -> tuple[list[str], bool]:
    """Resolve case-insensitive filename collisions deterministically.

    Archives ship distinct members that collide case-insensitively (PlantDoc: `car1.jpg` vs
    `CAR1.jpg`). First member in sorted order keeps its name; later ones get `~2`, `~3`…
    suffixes. Nothing is ever overwritten silently; every bump is recorded by the caller.
    A member re-appearing under its own name (duplicate entry in one archive) maps to itself.
    """
    key = "/".join(safe_parts).casefold()
    previous = seen.get(key)
    if previous is None or previous == member_name:
        seen[key] = member_name
        return safe_parts, False
    n = 2
    while True:
        bumped = [*safe_parts[:-1], _bump_segment(safe_parts[-1], n)]
        key = "/".join(bumped).casefold()
        previous = seen.get(key)
        if previous is None or previous == member_name:
            seen[key] = member_name
            return bumped, True
        n += 1


def safe_extract(archive: Path, dest: Path) -> list[tuple[str, str]]:
    """Manual, deterministic, MAX_PATH-aware extraction — ZipFile.extractall is never called.

    extractall has no `filter` parameter in any CPython release (the old PEP 706 branch was dead
    code that diverted every call into a second, unfiltered extractall), and win32 opens fail on
    >260-char targets (PlantDoc ships ~210-char member names) and on members whose names contain
    characters Windows forbids (e.g. PlantDoc's `IMG_1629.JPG?1507122477.jpg`). Rules: zip-slip
    validation per member, per-segment sanitization (deterministic, identical on every OS),
    deterministic `~2`-suffix dedup for case-insensitive file collisions (`car1.jpg`/`CAR1.jpg`)
    — renaming IS the refusal to overwrite — parents created before each file, extended-length
    paths on Windows, members in sorted order, completion marker written only after the last
    byte. Directory entries are never deduped: case-variant directories merge on Windows exactly
    as they would on a Windows checkout of the source repository. Returns the recorded file
    renames as (original member, written-as relative path) — surfaced in PROVENANCE.json.
    """
    archive, dest = Path(archive), Path(dest)
    os.makedirs(dest, exist_ok=True)
    renames: list[tuple[str, str]] = []
    seen: dict[str, str] = {}
    with zipfile.ZipFile(archive) as zf:
        for member in sorted(zf.infolist(), key=lambda m: m.filename):
            if not member.filename.strip("/\\"):
                continue  # archive-root pseudo entry
            parts = _validate_member_name(member.filename, archive)
            if not parts:
                continue
            safe_parts = [sanitize_segment(part) for part in parts]
            is_dir = member.is_dir() or member.filename.endswith(("/", "\\"))
            target = Path(dest, *safe_parts)
            if is_dir:
                try:
                    os.makedirs(windows_safe(target), exist_ok=True)
                except OSError as exc:
                    raise DownloadError(
                        f"cannot extract member {member.filename!r} from {archive.name} to {target}: {exc}"
                    ) from exc
                continue
            final_parts, clashed = _dedupe_file_parts(safe_parts, member.filename, seen)
            if final_parts != parts:
                written_as = "/".join(final_parts)
                renames.append((member.filename, written_as))
                if len(renames) <= 25:
                    if clashed:
                        logger.warning(
                            "member renamed to avoid a name clash on case-insensitive filesystems: %r -> %r",
                            member.filename,
                            written_as,
                        )
                    else:
                        logger.warning(
                            "member renamed for filesystem safety: %r -> %r", member.filename, written_as
                        )
            target = Path(dest, *final_parts)
            try:
                os.makedirs(windows_safe(target.parent), exist_ok=True)
                with zf.open(member) as source, open(windows_safe(target), "wb") as out:
                    shutil.copyfileobj(source, out)
            except OSError as exc:
                raise DownloadError(
                    f"cannot extract member {member.filename!r} from {archive.name} to {target}: {exc}"
                ) from exc
    if renames:
        logger.warning(
            "%d member(s) renamed for filesystem safety/clash in %s — recorded in PROVENANCE.json (extraction)",
            len(renames),
            archive.name,
        )
    (dest / EXTRACTION_MARKER).write_text("complete\n", encoding="utf-8")
    return renames


def _extract_nested_without_augmentation(extract_root: Path) -> tuple[Path, list[tuple[str, str]]]:
    """If the archive contains nested zips, prefer the *without augmentation* one.

    Returns (content_root, renames); renames is empty when the tree is reused or flat.
    """
    nested = sorted(extract_root.rglob("*.zip"))
    if not nested:
        return extract_root, []
    preferred = [z for z in nested if "without" in z.name.lower() and "aug" in z.name.lower()]
    chosen = preferred[0] if preferred else nested[0]
    target = extract_root / chosen.stem
    renames: list[tuple[str, str]] = []
    if not (target / EXTRACTION_MARKER).exists():
        logger.info("extracting nested archive %s", chosen.name)
        renames = safe_extract(chosen, target)
    return target, renames


def find_images_root(extract_root: Path, dataset: str, min_class_dirs: int = 2) -> Path:
    """Locate the directory whose subdirectories are dataset class folders."""
    best, best_score = None, -1
    for candidate in [extract_root, *[p for p in extract_root.rglob("*") if p.is_dir()]]:
        child_dirs = [c for c in candidate.iterdir() if c.is_dir()]
        score = sum(1 for c in child_dirs if classmap.map_class_dir(dataset, c.name))
        if score > best_score:
            best, best_score = candidate, score
    if best is None or best_score < min_class_dirs:
        raise DownloadError(f"could not locate class-folder root under {extract_root} (best={best_score})")
    return best


def manual_route_guidance(spec: DatasetSpec) -> str:
    """User-facing explanation for a blocked automatic download."""
    steps = "\n".join(f"  {i + 1}. {s}" for i, s in enumerate(spec.manual_steps))
    return (
        f"{spec.name!r} cannot be downloaded programmatically.\n"
        f"Status: {spec.programmatic_status} — {spec.status_note}\n\n"
        f"HTTP 403 means the authoritative source rejected automated download "
        f"(it requires a manual/browser download). We do not bypass authentication, "
        f"CAPTCHAs or other access controls, and we do not use unofficial scraped copies.\n\n"
        f"Official manual route ({spec.page_url}):\n{steps}\n"
    )


def _base_provenance(spec: DatasetSpec, now: str) -> dict:
    return {
        "dataset": spec.key,
        "name": spec.name,
        "version": spec.version,
        "doi": spec.doi,
        "citation": spec.citation,
        "page_url": spec.page_url,
        "license_id": spec.license_id,
        "license_url": spec.license_url,
        "license_observed": spec.license_observed,
        "programmatic_status": spec.programmatic_status,
        "downloaded_utc": now,
        "access_date_utc": now,
        "notes": spec.notes,
        "attribution": spec.citation or "See docs/datasets.md citations.",
    }


def _license_gate(spec: DatasetSpec, action: str, accept_license: bool) -> None:
    if accept_license:
        return
    raise LicenseNotAcceptedError(
        f"Refusing to {action} without license confirmation.\n"
        f"  1. Review the terms at {spec.page_url} (we observed: {spec.license_observed})\n"
        f"  2. Re-run with --accept-license"
    )


def _extraction_root(dataset_dir: Path, archive: Path) -> tuple[Path, list[tuple[str, str]]]:
    """Reuse only COMPLETE extractions (marker present); partial/crashed trees re-extract.

    Returns (extract_root, renames); renames is empty when a complete tree is reused.
    """
    extract_root = dataset_dir / "extracted"
    if (extract_root / EXTRACTION_MARKER).exists():
        logger.info("reusing existing extraction %s", extract_root)
        return extract_root, []
    if extract_root.exists():
        logger.warning("incomplete extraction (no %s) — re-extracting: %s", EXTRACTION_MARKER, extract_root)
    else:
        logger.info("extracting %s", archive.name)
    renames = safe_extract(archive, extract_root)
    return extract_root, renames


def _summarize_root(images_root: Path, dataset_dir: Path) -> dict:
    class_dirs = sorted(c.name for c in images_root.iterdir() if c.is_dir())
    return {
        "class_dirs": class_dirs,
        "class_dir_count": len(class_dirs),
        "image_count": sum(
            1 for p in images_root.rglob("*") if p.is_file() and not p.name.startswith(".")
        ),
    }


def download_dataset(key: str, dest_root: Path, accept_license: bool = False) -> Path:
    """Automated route. AUTO_BLOCKED datasets refuse fast with manual guidance."""
    spec: DatasetSpec = REGISTRY[key]
    _license_gate(spec, f"download {spec.name!r}", accept_license)
    if spec.programmatic_status == ProgrammaticStatus.AUTO_BLOCKED:
        raise DownloadError(manual_route_guidance(spec))

    dataset_dir = Path(dest_root) / key
    dataset_dir.mkdir(parents=True, exist_ok=True)
    archive = dataset_dir / spec.archive_name

    used_url, last_error = None, None
    if archive.exists() and is_zip_archive(archive):
        logger.info("reusing existing archive %s", archive)
        used_url = "(cached local archive)"
    else:
        for url in spec.candidates:
            try:
                _fetch(url, archive)
                if not is_zip_archive(archive):
                    raise DownloadError("downloaded file is not a zip archive (bad/moved endpoint)")
                used_url = url
                break
            except DownloadForbiddenError as exc:
                # Fail fast: 403 means automated access as such is refused; iterating into
                # more endpoints of the same gated host (and bypassing controls) achieves nothing.
                archive.unlink(missing_ok=True)
                raise DownloadError(manual_route_guidance(spec)) from exc
            except DownloadError as exc:
                last_error = exc
                logger.warning("candidate failed: %s", exc)
                archive.unlink(missing_ok=True)
        if used_url is None:
            raise DownloadError(f"all download candidates failed for {key!r}: {last_error}") from last_error

    extract_root, renames = _extraction_root(dataset_dir, archive)
    content_root, nested_renames = _extract_nested_without_augmentation(extract_root)
    renames = renames + nested_renames
    images_root = find_images_root(content_root, key)

    now = datetime.now(UTC).isoformat(timespec="seconds")
    provenance = {
        **_base_provenance(spec, now),
        "acquisition": {
            "method": "auto-download",
            "source_basename": archive.name,
            "imported_utc": now,
            "archive_sha256": sha256_file(archive),
            "sha256_note": None,
        },
        "source_url_used": used_url,
        "candidates_attempted": list(spec.candidates),
        "archive_file": archive.name,
        "archive_bytes": archive.stat().st_size,
        "images_root": str(images_root.relative_to(dataset_dir)),
        **_renamed_members_block(renames),
        **_summarize_root(images_root, dataset_dir),
    }
    (dataset_dir / "PROVENANCE.json").write_text(
        json.dumps(provenance, indent=2) + "\n", encoding="utf-8"
    )
    logger.info("provenance written: %s images", provenance["image_count"])
    return images_root


def import_dataset(
    key: str,
    dest_root: Path,
    *,
    archive: Path | None = None,
    directory: Path | None = None,
    accept_license: bool = False,
) -> Path:
    """Manual acquisition route: verify + register a user-provided archive or directory.

    - archive:   PK-signature check → path-traversal-safe extract → nested
                 without-augmentation preference → structure verification → sha256 recorded.
    - directory: verifies the class-folder structure IN PLACE (no multi-GB copy);
                 checksum skipped with an explicit recorded reason.
    """
    spec = REGISTRY[key]
    _license_gate(spec, f"import {spec.name!r} via the manual route", accept_license)
    if (archive is None) == (directory is None):
        raise ValueError("exactly one of archive= or directory= is required")

    dataset_dir = Path(dest_root) / key
    dataset_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now(UTC).isoformat(timespec="seconds")

    renames: list[tuple[str, str]] = []
    if archive is not None:
        archive = Path(archive)
        if not archive.exists():
            raise DownloadError(f"archive not found: {archive}")
        if not is_zip_archive(archive):
            raise DownloadError(
                f"not a zip archive: {archive}. If your browser produced a folder instead, use --directory."
            )
        extract_root, renames = _extraction_root(dataset_dir, archive)
        content_root, nested_renames = _extract_nested_without_augmentation(extract_root)
        renames = renames + nested_renames
        resolved_root = find_images_root(content_root, key)
        resolved_str, dataset_dir_str = str(resolved_root), str(dataset_dir.resolve())
        images_root_rel = (
            resolved_root.relative_to(dataset_dir_str).as_posix()
            if resolved_str.startswith(dataset_dir_str)
            else None
        )
        archive_sha256: str | None = sha256_file(archive)
        sha_note = None
        acquisition_method = "manual-archive"
        source_basename = archive.name
    else:
        directory = Path(directory).resolve()
        if not directory.is_dir():
            raise DownloadError(f"directory not found: {directory}")
        try:
            resolved_root = find_images_root(directory, key)
        except DownloadError as exc:
            raise DownloadError(
                f"{exc}\nPoint --directory at the dataset's class-folder root (or a parent of it)."
            ) from exc
        images_root_rel = None
        archive_sha256 = None
        sha_note = (
            "directory import: no single archive to checksum; "
            "file-level integrity is covered by split verification"
        )
        acquisition_method = "manual-directory"
        source_basename = directory.name

    problems, warnings = verify.verify_dataset_structure(resolved_root, key)
    for warning in warnings:
        logger.warning(warning)
    if problems:
        raise DownloadError("Dataset structure verification failed:\n  - " + "\n  - ".join(problems))

    provenance = {
        **_base_provenance(spec, now),
        "acquisition": {
            "method": acquisition_method,
            "source_basename": source_basename,
            "imported_utc": now,
            "archive_sha256": archive_sha256,
            "sha256_note": sha_note,
        },
        "images_root": images_root_rel if images_root_rel is not None else str(resolved_root),
        "images_root_absolute": images_root_rel is None,
        "structure_warnings": warnings,
        **_renamed_members_block(renames),
        **_summarize_root(resolved_root, dataset_dir),
    }
    (dataset_dir / "PROVENANCE.json").write_text(
        json.dumps(provenance, indent=2) + "\n", encoding="utf-8"
    )
    logger.info(
        "import OK: %s images across %s class dirs (%s)",
        provenance["image_count"],
        provenance["class_dir_count"],
        acquisition_method,
    )
    return resolved_root


def main_dest_default() -> Path:
    return Path(__file__).resolve().parents[2] / "data" / "raw"


if __name__ == "__main__":  # pragma: no cover - convenience
    import sys

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    key = sys.argv[1] if len(sys.argv) > 1 else "plantvillage"
    accept = "--accept-license" in sys.argv
    start = time.time()
    root = download_dataset(key, main_dest_default(), accept_license=accept)
    print(f"OK in {time.time() - start:.1f}s — images root: {root}")
