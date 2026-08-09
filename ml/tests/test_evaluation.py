"""Phase 4 evaluation tests: pure math + gate logic + full CLI integration on a toy run."""

import json
import uuid
from pathlib import Path

import numpy as np
import pytest
import torch
import yaml
from PIL import Image

from ml.evaluation import cli, core, report, runner
from ml.training.classes import class_list
from ml.training.model import build_model

CONFIG_DIR = Path(__file__).resolve().parents[1] / "configs"
CLASSES = class_list(CONFIG_DIR)


def _gate(gates: list[dict], gate_id: str) -> dict:
    return next(g for g in gates if g["id"] == gate_id)


# ---------------- pure: core math ----------------
def test_confusion_and_per_class_hand_computed():
    classes = ["a", "b", "c"]
    records = (
        [{"ground_truth": "a", "predicted": p} for p in ["a"] * 4 + ["b"]]
        + [{"ground_truth": "b", "predicted": p} for p in ["a"] + ["b"] * 4]
        + [{"ground_truth": "c", "predicted": "c"} for _ in range(4)]
    )
    cm = core.confusion_matrix(records, classes)
    assert cm.sum() == 14
    metrics = core.per_class_metrics(cm, classes)
    assert metrics["top1"] == pytest.approx(12 / 14, abs=1e-6)
    assert metrics["per_class"]["a"]["precision"] == round(4 / 5, 4)  # col a: 4tp + 1fp
    assert metrics["per_class"]["a"]["recall"] == round(4 / 5, 4)
    assert metrics["per_class"]["b"]["precision"] == round(4 / 5, 4)
    assert metrics["per_class"]["c"]["f1"] == 1.0
    assert metrics["per_class"]["c"]["support"] == 4


def test_latency_stats_percentiles():
    stats = core.latency_stats([float(v) for v in range(1, 101)])
    assert stats["count"] == 100
    assert stats["mean_ms"] == 50.5
    assert stats["max_ms"] == 100.0
    assert 49.0 <= stats["p50_ms"] <= 51.0
    assert 94.0 <= stats["p95_ms"] <= 96.0
    assert core.latency_stats([]) == {"count": 0, "mean_ms": None, "p50_ms": None, "p95_ms": None, "max_ms": None}


def test_band_histogram_includes_inconclusive_share():
    records = [
        {"status": "SUSPECTED", "confidence_band": "HIGH"},
        {"status": "SUSPECTED", "confidence_band": "LOW"},
        {"status": "INCONCLUSIVE", "confidence_band": None},
        {"status": "INCONCLUSIVE", "confidence_band": None},
    ]
    bands = core.band_histogram(records)
    assert bands["HIGH"]["count"] == 1
    assert bands["INCONCLUSIVE"]["count"] == 2
    assert bands["INCONCLUSIVE"]["share"] == 0.5
    assert sum(b["count"] for b in bands.values()) == 4


def test_top_confusions_excludes_diagonal_and_orders():
    cm = np.array([[10, 3, 0], [1, 8, 2], [0, 0, 9]])
    top = core.top_confusions(cm, ["a", "b", "c"], k=3)
    assert top[0] == {"actual": "a", "predicted": "b", "count": 3}
    assert all(t["actual"] != t["predicted"] for t in top)


def test_support_evaluation_rule_boundaries():
    per_class = {
        "edge_ok": {"precision": 0.9, "recall": 0.9, "f1": 0.9, "support": 20},
        "thin_support": {"precision": 0.95, "recall": 0.95, "f1": 0.95, "support": 19},
        "weak_f1": {"precision": 0.9, "recall": 0.89, "f1": 0.895, "support": 100},
    }
    result = core.support_evaluation(per_class)
    assert result["eligible"] == ["edge_ok"]
    assert sorted(result["watchlist"]) == ["thin_support", "weak_f1"]


# ---------------- pure: gates ----------------
def test_gates_pass_met_path():
    gates = core.evaluate_gates(
        eval_top1=0.9959,
        training_top1=0.9959,
        latency={"p95_ms": 120.0},
        device="cpu",
        ood={"top1": 0.52, "coverage": "17/21"},
    )
    assert _gate(gates, "M1-in-domain-top1")["status"] == "PASS"
    assert _gate(gates, "M1-ood-top1")["status"] == "MET"
    assert _gate(gates, "M1-latency-cpu")["status"] == "PASS"


def test_gates_fail_shortfall_not_run():
    gates = core.evaluate_gates(
        eval_top1=0.5, training_top1=None, latency={"p95_ms": 3000.0}, device="cpu", ood=None
    )
    assert _gate(gates, "M1-in-domain-top1")["status"] == "FAIL"
    assert _gate(gates, "M1-latency-cpu")["status"] == "FAIL"
    assert _gate(gates, "M1-ood-top1")["status"] == "NOT_RUN"
    cuda = core.evaluate_gates(eval_top1=0.9, training_top1=0.9, latency={"p95_ms": 3.0}, device="cuda", ood={"top1": 0.4, "coverage": "17/21"})
    assert _gate(cuda, "M1-latency-cpu")["status"] == "NOT_RUN"  # gate needs reference CPU
    assert _gate(cuda, "M1-ood-top1")["status"] == "SHORTFALL"


def test_gates_flag_drift_in_note():
    gates = core.evaluate_gates(
        eval_top1=0.90, training_top1=0.9959, latency={"p95_ms": 10.0}, device="cpu", ood=None
    )
    gate = _gate(gates, "M1-in-domain-top1")
    assert "DRIFT" in gate["note"]
    assert gate["status"] == "PASS"  # 0.90 still above the bar — drift is informational, not hidden


# ---------------- runner units ----------------
def test_ood_items_maps_and_records_skips(tmp_path):
    root = tmp_path / "plantdoc"
    for dirname, count in (("Tomato Early blight leaf", 2), ("Blueberry leaf", 3), ("Empty corner", 0)):
        folder = root / dirname
        folder.mkdir(parents=True)
        for i in range(count):
            Image.new("RGB", (8, 8), (10, 20, 30)).save(folder / f"i{i}.jpg")
    items, skipped = runner.ood_items(root, "plantdoc")
    assert len(items) == 2
    assert all(gt == "tomato_early_blight" for _, gt in items)
    assert skipped["Blueberry leaf"] == 3
    assert skipped["Empty corner"] == 0


def test_select_exemplars_prefers_confident_errors_then_inconclusive():
    records = [
        {"correct": False, "status": "SUSPECTED", "confidence": 0.9, "uncertainty": 0.1},
        {"correct": False, "status": "SUSPECTED", "confidence": 0.99, "uncertainty": 0.0},
        {"correct": True, "status": "SUSPECTED", "confidence": 0.99, "uncertainty": 0.0},
        {"correct": True, "status": "INCONCLUSIVE", "confidence": 0.1, "uncertainty": 0.9},
    ]
    picked = runner.select_exemplars(records, 3)
    assert picked[0]["confidence"] == 0.99 and not picked[0]["correct"]
    assert picked[-1]["status"] == "INCONCLUSIVE"
    assert all(not r["correct"] or r["status"] == "INCONCLUSIVE" for r in picked)


# ---------------- integration: full CLI on a toy run ----------------
@pytest.fixture()
def toy_run_dir(tmp_path):
    model = build_model(len(CLASSES), pretrained=False)
    ckpt = {
        "format_version": 1,
        "arch": "mobilenet_v3_small",
        "state_dict": {k: v.cpu() for k, v in model.state_dict().items()},
        "meta": {
            "model_version": "0.0.0-evaltest",
            "classes": CLASSES,
            "num_classes": len(CLASSES),
            "image_size": 224,
            "dataset_version": "toy",
            "seed": 0,
        },
    }
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    torch.save(ckpt, run_dir / "checkpoint.pt")
    (run_dir / "checkpoint.sha256").write_text("f" * 64 + "\n", encoding="utf-8")
    (run_dir / "metrics.json").write_text(json.dumps({"test": {"top1": 0.9}}), encoding="utf-8")

    images_root = tmp_path / "images"
    rows = []
    for cls_id, dirname in (("apple_healthy", "clsA"), ("tomato_healthy", "clsB")):
        folder = images_root / dirname
        folder.mkdir(parents=True)
        for i in range(3):
            Image.new("RGB", (32, 32), (i * 50, 90, 120)).save(folder / f"{dirname}_{i}.jpg")
            rows.append(f"{dirname}/{dirname}_{i}.jpg\t{cls_id}")
    split_dir = tmp_path / "splits"
    split_dir.mkdir()
    (split_dir / "test.txt").write_text("\n".join(rows) + "\n", encoding="utf-8")
    (split_dir / "split_manifest.json").write_text(
        json.dumps({"images_root": str(images_root), "content_sha256": "0" * 64}), encoding="utf-8"
    )
    (run_dir / "config.yaml").write_text(
        yaml.safe_dump({"data": {"splits_dir": str(split_dir)}}), encoding="utf-8"
    )
    return run_dir


def test_cli_report_end_to_end(toy_run_dir, tmp_path, capsys):
    out = tmp_path / "eval_out"
    code = cli.main([
        "report", "--run-dir", str(toy_run_dir), "--out", str(out), "--num-exemplars", "4", "--max-images", "6",
    ])
    assert code == 0
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))

    assert summary["dataset"]["images"] == 6
    assert summary["model_version"] == "0.0.0-evaltest"
    assert summary["ood"] is None
    gate_status = {g["id"]: g["status"] for g in summary["gates"]}
    assert gate_status["M1-ood-top1"] == "NOT_RUN"
    assert gate_status["M1-in-domain-top1"] in ("PASS", "FAIL")  # random weights — measured, not assumed
    assert gate_status["M1-latency-cpu"] in ("PASS", "FAIL")
    assert summary["in_domain"]["latency"]["count"] == 6
    assert summary["in_domain"]["training_reported_top1"] == 0.9
    assert sum(b["count"] for b in summary["in_domain"]["bands"].values()) == 6
    assert len(summary["exemplars"]) <= 4
    assert (out / "confusion_in_domain.png").exists()
    assert list((out / "exemplars").glob("*-orig.png"))

    md = (out / "REPORT.md").read_text(encoding="utf-8")
    assert "M1-in-domain-top1" in md
    assert "NOT RUN" in md
    assert "pipeline --dataset plantdoc" in md
    assert "python -m ml.evaluation.cli report" in md
    printed = capsys.readouterr().out
    assert "gate M1-in-domain-top1:" in printed


# ---------------- report: exemplar materialization (Windows re-run regression) ----------------
class _StubExemplarPredictor:
    """Predictor-shaped stub: writes a fresh uuid-named overlay per call, like the real one."""

    def predict(self, path, explain_dir=None, top_k=3):
        overlay = Path(explain_dir) / f"{uuid.uuid4().hex[:12]}-gradcam.png"
        overlay.write_bytes(b"faux-overlay")
        return {"gradcam_overlay": str(overlay)}


def _leaf(tmp_path, name):
    p = tmp_path / name
    Image.new("RGB", (16, 16), (7, 90, 30)).save(p)
    return {
        "path": str(p), "ground_truth": "apple_healthy", "predicted": "tomato_healthy",
        "confidence": 0.5, "status": "SUSPECTED",
    }


def test_materialize_exemplars_rerun_overwrites_and_drops_stale(tmp_path):
    """Gate C crashed here on Windows re-runs: Path.rename refuses an existing target
    (WinError 183), and a shorter new exemplar set must never leave older-run files behind."""
    ex_dir = tmp_path / "out" / "exemplars"
    picked3 = [_leaf(tmp_path, f"a{i}.jpg") for i in range(3)]
    captions1 = report.materialize_exemplars(_StubExemplarPredictor(), picked3, ex_dir)
    assert len(captions1) == 3
    assert len(list(ex_dir.glob("*-gradcam.png"))) == 3

    picked1 = [_leaf(tmp_path, "b0.jpg")]
    captions2 = report.materialize_exemplars(_StubExemplarPredictor(), picked1, ex_dir)  # must not raise
    assert len(captions2) == 1
    names = sorted(p.name for p in ex_dir.iterdir())
    assert names == ["00-gradcam.png", "00-orig.png", "captions.json"]  # stale 01-/02- artifacts gone
    written = json.loads((ex_dir / "captions.json").read_text(encoding="utf-8"))
    assert len(written) == 1 and written[0]["source_path"] == picked1[0]["path"]
