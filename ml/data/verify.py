"""Pipeline verification: provenance completeness + split integrity + leakage checks,
plus raw-dataset structure verification used by manual import.

Returns lists of problems (empty = OK) so it can serve both the CLI and tests.
"""

import json
from pathlib import Path

from ml.data import classmap
from ml.data import split as split_mod
from ml.data.registry import REGISTRY

REQUIRED_PROVENANCE_KEYS = {
    "dataset",
    "name",
    "version",
    "page_url",
    "doi",
    "citation",
    "license_id",
    "license_url",
    "license_observed",
    "downloaded_utc",
    "acquisition",
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


def _coverage_context(dataset: str) -> tuple[set[str], set[str]]:
    """(documented disease_ids, V1 crop prefixes) derived from the class map itself."""
    targets = {t for t in classmap.MAPS.get(dataset, {}).values() if t is not classmap.EXCLUDE}
    prefixes = {str(t).split("_", 1)[0] for t in targets}
    return targets, prefixes


def verify_dataset_structure(images_root: Path, dataset: str) -> tuple[list[str], list[str]]:
    """Structural gate before a dataset feeds the pipeline (spec §10 of the fix).

    Three independent checks beyond existence:
    1. floor — enough mappable folders to rule out "pointed at the wrong root";
    2. coverage (require_full_class_coverage=True datasets, i.e. the training source) —
       EVERY documented class must have a folder; partial coverage = silent class loss;
    3. V1-crop-prefix — an unmapped folder named like a V1 crop is a class-map GAP
       (missing alias), not out-of-scope data: fatal for training sources, recorded
       warning for documented partial-coverage (eval) datasets.

    Returns (problems, warnings). Problems block; warnings are recorded/reported only.
    """
    spec = REGISTRY[dataset]
    problems: list[str] = []
    warnings: list[str] = []
    root = Path(images_root)
    if not root.is_dir():
        return [f"images root does not exist or is not a directory: {root}"], warnings

    class_dirs = [d for d in root.iterdir() if d.is_dir()]
    if not class_dirs:
        return [f"no class folders found under {root}"], warnings

    expected_ids, crop_prefixes = _coverage_context(dataset)
    mapped_ok, unmapped, excluded = [], [], []
    covered_ids: set[str] = set()
    for class_dir in class_dirs:
        mapping = classmap.map_class_dir(dataset, class_dir.name)
        if mapping is classmap.EXCLUDE:
            excluded.append(class_dir.name)
        elif mapping is None:
            unmapped.append(class_dir.name)
        else:
            mapped_ok.append(class_dir)
            covered_ids.add(str(mapping))

    v1_like_unmapped = sorted(
        name for name in unmapped if classmap.normalize(name).split("_", 1)[0] in crop_prefixes
    )
    if v1_like_unmapped:
        detail = (
            "V1-crop class folders with no mapping key (class map gap — extend the aliases in "
            f"ml/data/classmap.py; these are NOT out-of-scope folders): {v1_like_unmapped}"
        )
        if spec.require_full_class_coverage:
            problems.append(detail + " — refusing to train with silent class loss.")
        else:
            warnings.append(detail + " — recorded, skipped (documented partial coverage).")

    if len(mapped_ok) < spec.expected_min_mapped_class_dirs:
        problems.append(
            f"structure check failed: {len(mapped_ok)} mappable class folders found, expected at least "
            f"{spec.expected_min_mapped_class_dirs} for dataset {dataset!r}. "
            f"Check that you are pointing at the class-folder root of the correct dataset "
            f"(e.g. the without-augmentation folder for PlantVillage)."
        )
    if spec.require_full_class_coverage:
        missing = sorted(expected_ids - covered_ids)
        if missing:
            problems.append(
                f"coverage incomplete for dataset {dataset!r}: documented classes with no mapped folder: "
                f"{missing} (extend ml/data/classmap.py aliases or check you pointed at the full extraction)"
            )
    for class_dir in mapped_ok:
        has_image = any(
            p.is_file() and p.suffix.lower() in split_mod.IMAGE_EXTS
            for p in class_dir.iterdir()
        )
        if not has_image:
            problems.append(f"mappable class folder contains no images: {class_dir.name}")
    non_v1_unmapped = sorted(set(unmapped) - set(v1_like_unmapped))
    if non_v1_unmapped:
        warnings.append(f"class folders outside the documented V1 scope (recorded, skipped): {non_v1_unmapped}")
    if excluded:
        warnings.append(f"class folders explicitly excluded by policy: {sorted(excluded)}")
    return problems, warnings


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
