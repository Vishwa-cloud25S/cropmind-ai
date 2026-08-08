"""License-gated dataset downloader.

Guarantees:
- Refuses to download until the operator confirms the license (--accept-license);
  the gate message points at the exact page where terms were checked.
- Verifies the download is really a zip archive (PK signature), because mirror
  endpoints change shape (JSON wrappers) without notice.
- Extracts safely (no path traversal) and, for "Download All"-style archives,
  prefers the nested *without-augmentation* archive to prevent augmented
  duplicates leaking into splits.
- Writes PROVENANCE.json — a first-class provenance record (spec §6).
"""

import hashlib
import json
import logging
import os
import time
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import requests

from ml.data import classmap
from ml.data.registry import REGISTRY, DatasetSpec

logger = logging.getLogger("cropmind.ml.download")


class LicenseNotAcceptedError(RuntimeError):
    pass


class DownloadError(RuntimeError):
    pass


def _fetch(url: str, dest: Path, log_every_mb: int = 64) -> int:
    """Stream url -> dest. Raises DownloadError on non-200 or JSON responses."""
    logger.info("downloading %s", url)
    with requests.get(url, stream=True, timeout=(10, 300), allow_redirects=True) as r:
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


def safe_extract(archive: Path, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as zf:
        try:
            zf.extractall(dest, filter="data")  # PEP 706 (py>=3.11.4)
        except TypeError:  # very old interpreters
            dest_resolved = dest.resolve()
            for member in zf.namelist():
                target = (dest / member).resolve()
                if target != dest_resolved and str(dest_resolved) + os.sep not in str(target):
                    raise DownloadError(f"unsafe path in archive: {member}") from None
            zf.extractall(dest)


def _extract_nested_without_augmentation(extract_root: Path) -> Path:
    """If the archive contains nested zips, prefer the *without augmentation* one."""
    nested = sorted(extract_root.rglob("*.zip"))
    if not nested:
        return extract_root
    preferred = [z for z in nested if "without" in z.name.lower() and "aug" in z.name.lower()]
    chosen = preferred[0] if preferred else nested[0]
    target = extract_root / chosen.stem
    if not target.exists():
        logger.info("extracting nested archive %s", chosen.name)
        safe_extract(chosen, target)
    return target


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


def download_dataset(key: str, dest_root: Path, accept_license: bool = False) -> Path:
    """Download + extract + record provenance. Returns the images root."""
    spec: DatasetSpec = REGISTRY[key]
    if not accept_license:
        raise LicenseNotAcceptedError(
            f"Refusing to download {spec.name!r} without license confirmation.\n"
            f"  1. Review the terms at {spec.page_url} (we observed: {spec.license_observed})\n"
            f"  2. Re-run with --accept-license"
        )
    dest_root = Path(dest_root)
    dataset_dir = dest_root / key
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
            except DownloadError as exc:
                last_error = exc
                logger.warning("candidate failed: %s", exc)
                archive.unlink(missing_ok=True)
        if used_url is None:
            raise DownloadError(f"all download candidates failed for {key!r}: {last_error}") from last_error

    extract_root = dataset_dir / "extracted"
    if not extract_root.exists():
        logger.info("extracting %s", archive.name)
        safe_extract(archive, extract_root)
    content_root = _extract_nested_without_augmentation(extract_root)
    images_root = find_images_root(content_root, key)

    class_dirs = sorted(c.name for c in images_root.iterdir() if c.is_dir())
    image_count = sum(
        1 for p in images_root.rglob("*") if p.is_file() and not p.name.startswith(".")
    )
    provenance = {
        "dataset": key,
        "name": spec.name,
        "version": spec.version,
        "page_url": spec.page_url,
        "license_id": spec.license_id,
        "license_url": spec.license_url,
        "license_observed": spec.license_observed,
        "downloaded_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "source_url_used": used_url,
        "candidates_attempted": list(spec.candidates),
        "archive_file": archive.name,
        "archive_sha256": sha256_file(archive),
        "archive_bytes": archive.stat().st_size,
        "images_root": str(images_root.relative_to(dataset_dir)),
        "class_dirs": class_dirs,
        "class_dir_count": len(class_dirs),
        "image_count": image_count,
        "notes": spec.notes,
        "attribution": "See docs/datasets.md citations; attribution retained even under CC0.",
    }
    (dataset_dir / "PROVENANCE.json").write_text(
        json.dumps(provenance, indent=2) + "\n", encoding="utf-8"
    )
    logger.info("provenance written: %s images in %s class dirs", image_count, len(class_dirs))
    return images_root


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
