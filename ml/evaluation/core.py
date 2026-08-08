"""Evaluation math + M1 gate logic (docs/01 §6, docs/05-ml-pipeline §4).

Pure Python/NumPy — no torch — so every formula is unit-testable and CI-fast.
Per-class metrics intentionally match the training evaluator's definitions
(ml/training/train.py:evaluate) so eval-reported and training-reported numbers
are measured the same way.
"""

from collections import Counter

import numpy as np

# M1 gates (docs/01-product-requirements §6) — thresholds live here, single source.
GATE_TOP1_MIN = 0.80  # held-out in-domain (PlantVillage test split) top-1
GATE_OOD_TARGET = 0.50  # PlantDoc out-of-domain top-1, reported as-is (target, never tuned)
GATE_LATENCY_P95_MS = 2500.0  # ≤ 2.5 s/image on reference CPU
GATE_CONSISTENCY_MAX_DIFF = 0.02  # eval vs training-reported top-1 drift tolerance (informational)

# Documented support rule (docs/06-model-card): a class is only *eligible* to flip
# supported_by_model once the eval report shows F1 >= SUPPORT_F1_MIN with support >=
# SUPPORT_MIN on the held-out split. Flipping itself stays a separate reviewed commit.
SUPPORT_F1_MIN = 0.90
SUPPORT_MIN = 20

STATUSES = ("PASS", "FAIL", "MET", "SHORTFALL", "NOT_RUN")


def confusion_matrix(records: list[dict], classes: list[str]) -> np.ndarray:
    """rows = ground truth, cols = predicted. Records: {'ground_truth','predicted',...}."""
    idx = {c: i for i, c in enumerate(classes)}
    cm = np.zeros((len(classes), len(classes)), dtype=np.int64)
    for rec in records:
        cm[idx[rec["ground_truth"]], idx[rec["predicted"]]] += 1
    return cm


def per_class_metrics(cm: np.ndarray, classes: list[str]) -> dict:
    """Precision/recall/F1/support per class + overall top-1 — mirrors train.evaluate."""
    tp = np.diag(cm).astype(np.float64)
    pred_sum = cm.sum(axis=0).astype(np.float64)
    true_sum = cm.sum(axis=1).astype(np.float64)
    precision = tp / np.maximum(pred_sum, 1)
    recall = tp / np.maximum(true_sum, 1)
    denom = precision + recall
    f1 = np.where(denom > 0, 2 * precision * recall / np.maximum(denom, 1e-12), 0.0)
    return {
        "top1": float(tp.sum() / max(cm.sum(), 1)),
        "images": int(cm.sum()),
        "per_class": {
            c: {
                "precision": round(float(p), 4),
                "recall": round(float(r), 4),
                "f1": round(float(f), 4),
                "support": int(s),
            }
            for c, p, r, f, s in zip(classes, precision, recall, f1, true_sum, strict=True)
        },
    }


def latency_stats(latencies_ms: list[float]) -> dict:
    """Classification-pipeline latency distribution (p50/p95 are the reported gates)."""
    if not latencies_ms:
        return {"count": 0, "mean_ms": None, "p50_ms": None, "p95_ms": None, "max_ms": None}
    arr = np.asarray(sorted(latencies_ms), dtype=np.float64)
    return {
        "count": int(arr.size),
        "mean_ms": round(float(arr.mean()), 1),
        "p50_ms": round(float(np.percentile(arr, 50)), 1),
        "p95_ms": round(float(np.percentile(arr, 95)), 1),
        "max_ms": round(float(arr.max()), 1),
    }


def band_histogram(records: list[dict]) -> dict:
    """How often the UI bands fire on this split — incl. the honest INCONCLUSIVE share."""
    counts = Counter(r.get("status") == "SUSPECTED" and r.get("confidence_band") or "INCONCLUSIVE" for r in records)
    total = max(len(records), 1)
    return {
        band: {"count": int(counts.get(band, 0)), "share": round(counts.get(band, 0) / total, 4)}
        for band in ("HIGH", "MEDIUM", "LOW", "INCONCLUSIVE")
    }


def top_confusions(cm: np.ndarray, classes: list[str], k: int = 5) -> list[dict]:
    """Largest off-diagonal cells: (actual → predicted, count). Honest error anatomy."""
    pairs = [
        (actual, pred, int(cm[i, j]))
        for i, actual in enumerate(classes)
        for j, pred in enumerate(classes)
        if i != j and cm[i, j] > 0
    ]
    pairs.sort(key=lambda t: t[2], reverse=True)
    return [{"actual": a, "predicted": p, "count": n} for a, p, n in pairs[:k]]


def uncertainty_mean(records: list[dict]) -> float | None:
    if not records:
        return None
    return round(sum(r["uncertainty"] for r in records) / len(records), 4)


def support_evaluation(per_class: dict) -> dict:
    """Classify classes by the documented support rule — eligible vs watchlist."""
    eligible = sorted(c for c, m in per_class.items() if m["f1"] >= SUPPORT_F1_MIN and m["support"] >= SUPPORT_MIN)
    watchlist = sorted(set(per_class) - set(eligible))
    return {"eligible": eligible, "watchlist": watchlist}


def evaluate_gates(
    *,
    eval_top1: float,
    training_top1: float | None,
    latency: dict,
    device: str,
    ood: dict | None,
) -> list[dict]:
    """M1 gate measurement (docs/01 §6). Gates are measured, never asserted."""
    gates = []
    note = "held-out PlantVillage test split"
    if training_top1 is not None:
        diff = abs(eval_top1 - training_top1)
        note += f"; training-reported {training_top1:.4f} (Δ {diff:.4f}, tolerance {GATE_CONSISTENCY_MAX_DIFF})"
        if diff > GATE_CONSISTENCY_MAX_DIFF:
            note += " — DRIFT, investigate before claiming"
    gates.append({
        "id": "M1-in-domain-top1",
        "requirement": f"held-out top-1 ≥ {GATE_TOP1_MIN}",
        "measured": round(eval_top1, 4),
        "status": "PASS" if eval_top1 >= GATE_TOP1_MIN else "FAIL",
        "note": note,
    })
    if ood is None:
        gates.append({
            "id": "M1-ood-top1",
            "requirement": f"PlantDoc OOD top-1 reported as-is (target ≥ {GATE_OOD_TARGET})",
            "measured": None,
            "status": "NOT_RUN",
            "note": "plantdoc not available locally; run: python -m ml.data.cli pipeline --dataset plantdoc --accept-license",
        })
    else:
        gates.append({
            "id": "M1-ood-top1",
            "requirement": f"PlantDoc OOD top-1 reported as-is (target ≥ {GATE_OOD_TARGET})",
            "measured": round(ood["top1"], 4),
            "status": "MET" if ood["top1"] >= GATE_OOD_TARGET else "SHORTFALL",
            "note": "out-of-domain honesty metric; never tuned on; coverage " + ood.get("coverage", ""),
        })
    if device != "cpu":
        gates.append({
            "id": "M1-latency-cpu",
            "requirement": f"p95 ≤ {GATE_LATENCY_P95_MS:.0f} ms/image on reference CPU",
            "measured": None,
            "status": "NOT_RUN",
            "note": f"measured on {device}; rerun the report with --device cpu for the gate",
        })
    else:
        p95 = latency.get("p95_ms")
        gates.append({
            "id": "M1-latency-cpu",
            "requirement": f"p95 ≤ {GATE_LATENCY_P95_MS:.0f} ms/image on reference CPU",
            "measured": p95,
            "status": ("PASS" if p95 <= GATE_LATENCY_P95_MS else "FAIL") if p95 is not None else "NOT_RUN",
            "note": "classification pipeline latency (preprocess + forward + bands; Grad-CAM exemplars excluded)",
        })
    return gates
