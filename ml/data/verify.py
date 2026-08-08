"""Pipeline verification: provenance completeness + split integrity + leakage checks.

Returns lists of problems (empty = OK) so it can serve both the CLI and tests.
"""

import json
from pathlib import Path

from ml.data import split as split_mod

REQUIRED_PROVENANCE_KEYS = {
    "dataset",
    "name",
    "version",
    "page_url",
    "license_id",
    "license_url",
    "license_observed",
    "downloaded_utc",
    "archive_sha256",
    "images_root",
    "image_count",
}

SPLIT_NAMES = ("train", "val", "test")


def verify_provenance(provenance_path: Path) -> list[str]:
    path = Path(provenance_path)
    if not path.exists():
        return [f"missing provenance file: {path}"]
    data = json.loads(path.read_text(encoding="utf-8"))
    problems = [f"provenance missing key: {key}" for key in sorted(REQUIRED_PROVENANCE_KEYS - data.keys())]
    if data.get("archive_sha256") and len(data["archive_sha256"]) != 64:
        problems.append("archive_sha256 is not a sha256 hex digest")
    return problems


def verify_splits(split_dir: Path) -> list[str]:
    split_dir = Path(split_dir)
    problems: list[str] = []
    manifest_path = split_dir / "split_manifest.json"
    if not manifest_path.exists():
        return [f"missing split manifest: {manifest_path}"]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    images_root = Path(manifest["images_root"])

    seen: dict[str, str] = {}
    totals: dict[str, list] = {}
    for name in SPLIT_NAMES:
        file_path = split_dir / f"{name}.txt"
        if not file_path.exists():
            problems.append(f"missing split file: {file_path}")
            continue
        rows = split_mod.read_split(split_dir, name)
        if not rows:
            problems.append(f"{name}.txt is empty")
        paths = [rel for rel, _ in rows]
        if len(paths) != len(set(paths)):
            problems.append(f"{name}.txt contains duplicate paths")
        for rel in paths:
            if rel in seen and seen[rel] != name:
                problems.append(f"LEAKAGE: {rel} appears in both {seen[rel]} and {name}")
            seen[rel] = name
            if not (images_root / rel).exists():
                problems.append(f"{name}: referenced file does not exist: {rel}")
        totals[name] = rows

    recorded = manifest.get("splits", {})
    for name in SPLIT_NAMES:
        if name in totals and recorded.get(name, {}).get("count") != len(totals[name]):
            problems.append(
                f"manifest count mismatch for {name}: manifest={recorded.get(name, {}).get('count')} actual={len(totals[name])}"
            )
    return problems
