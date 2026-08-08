"""Run the REAL shipped inference path (ml/inference/predictor.py) over eval item sets.

The evaluation never reimplements inference: it drives the same Predictor contract the
product uses, so bands/uncertainty/latency measured here are the product's own numbers.
"""

import logging
import time
from pathlib import Path

from ml.data import classmap
from ml.data import split as split_mod
from ml.inference.predictor import Predictor
from ml.preprocessing.dataset import load_manifest

logger = logging.getLogger("cropmind.ml.evaluation")


def in_domain_items(split_dir: Path) -> tuple[list[tuple[Path, str]], dict]:
    """Held-out items: (image_path, disease_id) from the deterministic test split."""
    split_dir = Path(split_dir)
    manifest = load_manifest(split_dir)
    images_root = Path(manifest["images_root"])
    rows = split_mod.read_split(split_dir, "test")
    return [(images_root / rel, disease_id) for rel, disease_id in rows], manifest


def ood_items(images_root: Path, dataset_key: str = "plantdoc") -> tuple[list[tuple[Path, str]], dict]:
    """Out-of-domain items from raw class folders; unmapped folders are recorded, never dropped silently."""
    images_root = Path(images_root)
    items: list[tuple[Path, str]] = []
    skipped: dict[str, int] = {}
    for folder in sorted(p for p in images_root.iterdir() if p.is_dir()):
        mapped = classmap.map_class_dir(dataset_key, folder.name)
        files = [p for p in sorted(folder.iterdir()) if p.suffix.lower() in split_mod.IMAGE_EXTS]
        if mapped is None or mapped is classmap.EXCLUDE or not files:
            skipped[folder.name] = skipped.get(folder.name, 0) + len(files)
            continue
        items.extend((p, str(mapped)) for p in files)
    return items, skipped


def select_exemplars(records: list[dict], limit: int) -> list[dict]:
    """Worst-case exemplars: most-confident errors first, then INCONCLUSIVE samples."""
    errors = sorted((r for r in records if not r["correct"]), key=lambda r: r["confidence"], reverse=True)
    inconclusive = [r for r in records if r["status"] == "INCONCLUSIVE"]
    picked = (errors + inconclusive)[: max(limit, 0)]
    return picked


def evaluate_items(
    predictor: Predictor,
    items: list[tuple[Path, str]],
    *,
    desc: str,
    limit: int | None = None,
    progress_every: int = 250,
) -> list[dict]:
    """Per-image records through the shipped predictor (explain artifacts off for speed)."""
    subset = items if limit is None else items[:limit]
    records: list[dict] = []
    started = time.time()
    for i, (path, ground_truth) in enumerate(subset, start=1):
        pred = predictor.predict(path, explain_dir=None, top_k=3)
        predicted = pred["condition"]["disease_id"]
        records.append({
            "path": str(path),
            "ground_truth": ground_truth,
            "predicted": predicted,
            "correct": predicted == ground_truth,
            "confidence": pred["confidence"],
            "confidence_band": pred["confidence_band"],
            "status": pred["status"],
            "uncertainty": pred["uncertainty"],
            "latency_ms": pred["latency_ms"],
        })
        if i % progress_every == 0 or i == len(subset):
            logger.info("%s: %d/%d images (%.0fs)", desc, i, len(subset), time.time() - started)
    return records
