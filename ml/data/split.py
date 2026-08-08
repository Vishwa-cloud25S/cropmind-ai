"""Deterministic, stratified train/val/test splitting.

- Stratification is per disease_id (class balance survives the split).
- Splitting is at IMAGE level. Augmented-image leakage is impossible by
  construction because only without-augmentation source data is used (registry).
- Same seed → byte-identical outputs; the seed is recorded in the manifest.
- Unmapped/out-of-scope and explicitly excluded class dirs are recorded under
  `skipped` — never silently dropped.
"""

import hashlib
import json
import random
from datetime import UTC, datetime
from pathlib import Path

from ml.data import classmap

IMAGE_EXTS = {".jpg", ".jpeg", ".png"}
DEFAULT_RATIOS = (0.70, 0.15, 0.15)


def collect_items(images_root: Path, dataset: str) -> tuple[dict[str, list[str]], dict, dict]:
    """Walk class folders; returns (items_by_class, skipped_unmapped, skipped_excluded)."""
    items: dict[str, list[str]] = {}
    unmapped: dict[str, int] = {}
    excluded: dict[str, int] = {}
    for path in sorted(images_root.rglob("*")):
        if not (path.is_file() and path.suffix.lower() in IMAGE_EXTS):
            continue
        class_dir = path.parent.name
        mapped = classmap.map_class_dir(dataset, class_dir)
        if mapped is classmap.EXCLUDE:
            excluded[class_dir] = excluded.get(class_dir, 0) + 1
            continue
        if mapped is None:
            unmapped[class_dir] = unmapped.get(class_dir, 0) + 1
            continue
        rel = path.relative_to(images_root).as_posix()
        items.setdefault(mapped, []).append(rel)
    return items, unmapped, excluded


def _counts(n: int, ratios: tuple[float, float, float]) -> tuple[int, int, int]:
    n_train = int(n * ratios[0])
    n_val = int(n * ratios[1])
    if n >= 3:  # guarantee representation in every split when the class allows it
        n_train = max(n_train, 1)
        n_val = max(n_val, 1)
        n_train = min(n_train, n - n_val - 1)
    n_test = n - n_train - n_val
    return n_train, n_val, n_test


def split_dataset(
    images_root: Path,
    out_dir: Path,
    dataset: str,
    seed: int = 42,
    ratios: tuple[float, float, float] = DEFAULT_RATIOS,
    version: str = "v1",
) -> dict:
    """Write train.txt/val.txt/test.txt + split_manifest.json. Returns the manifest."""
    images_root, out_dir = Path(images_root), Path(out_dir)
    if abs(sum(ratios) - 1.0) > 1e-9:
        raise ValueError(f"ratios must sum to 1.0, got {ratios}")
    items, unmapped, excluded = collect_items(images_root, dataset)
    if not items:
        raise ValueError(f"no images mapped for dataset {dataset!r} under {images_root}")

    rng = random.Random(seed)
    splits: dict[str, list[tuple[str, str]]] = {"train": [], "val": [], "test": []}
    for disease_id, rels in sorted(items.items()):
        rels = sorted(rels)
        rng.shuffle(rels)
        n_train, n_val, n_test = _counts(len(rels), ratios)
        splits["train"] += [(r, disease_id) for r in rels[:n_train]]
        splits["val"] += [(r, disease_id) for r in rels[n_train : n_train + n_val]]
        splits["test"] += [(r, disease_id) for r in rels[n_train + n_val : n_train + n_val + n_test]]

    out_dir.mkdir(parents=True, exist_ok=True)
    hasher = hashlib.sha256()
    counts = {}
    for name in ("train", "val", "test"):
        rows = sorted(splits[name])
        text = "".join(f"{rel}\t{disease_id}\n" for rel, disease_id in rows)
        (out_dir / f"{name}.txt").write_text(text, encoding="utf-8")
        hasher.update(name.encode() + text.encode())
        per_class: dict[str, int] = {}
        for _, disease_id in rows:
            per_class[disease_id] = per_class.get(disease_id, 0) + 1
        counts[name] = {"count": len(rows), "classes": dict(sorted(per_class.items()))}

    manifest = {
        "dataset": dataset,
        "version": version,
        "seed": seed,
        "ratios": list(ratios),
        "created_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "images_root": str(images_root),
        "splits": counts,
        "skipped": {"unmapped": dict(sorted(unmapped.items())), "excluded": dict(sorted(excluded.items()))},
        "tiny_classes_warning": sorted(c for c, rels in items.items() if len(rels) < 3),
        "content_sha256": hasher.hexdigest(),
        "policy": "Stratified image-level split; source data is without-augmentation only (see PROVENANCE.json).",
    }
    (out_dir / "split_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def read_split(split_dir: Path, name: str) -> list[tuple[str, str]]:
    lines = (Path(split_dir) / f"{name}.txt").read_text(encoding="utf-8").splitlines()
    return [tuple(line.split("\t", 1)) for line in lines if line.strip()]  # type: ignore[misc]
