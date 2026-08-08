"""Predictor contract tests. Random-init checkpoint fixtures — plumbing, not performance."""

from pathlib import Path

import pytest
import torch
from PIL import Image

from ml.inference.predictor import Predictor
from ml.training.classes import class_list
from ml.training.model import build_model


@pytest.fixture()
def tiny_checkpoint(tmp_path):
    classes = class_list()
    model = build_model(len(classes), pretrained=False)
    ckpt = {
        "format_version": 1,
        "arch": "mobilenet_v3_small",
        "state_dict": model.state_dict(),
        "meta": {
            "model_version": "0.1.0-test",
            "classes": classes,
            "num_classes": len(classes),
            "image_size": 64,
            "dataset": "plantvillage",
            "dataset_version": "plantvillage@v1",
            "seed": 1,
            "purpose": "test fixture",
        },
    }
    path = tmp_path / "ckpt.pt"
    torch.save(ckpt, path)
    return path


@pytest.fixture()
def predictor(tiny_checkpoint):
    return Predictor(tiny_checkpoint, device="cpu")


@pytest.fixture()
def photo(tmp_path):
    path = tmp_path / "leaf.jpg"
    Image.new("RGB", (128, 128), (30, 180, 60)).save(path)
    return path


def test_band_mapping_boundaries(predictor):
    assert predictor.band_for(0.70) == "HIGH"
    assert predictor.band_for(0.60) == "HIGH"
    assert predictor.band_for(0.50) == "MEDIUM"
    assert predictor.band_for(0.30) == "LOW"
    assert predictor.band_for(0.20) is None


def test_prediction_contract_keys(predictor, photo, tmp_path):
    result = predictor.predict(photo, explain_dir=tmp_path / "explain")

    for key in (
        "prediction_id", "status", "phrasing", "crop", "condition", "confidence",
        "confidence_band", "uncertainty", "estimated_visual_severity", "severity_label",
        "regions", "gradcam_overlay", "model_version", "dataset_version",
        "threshold_version", "latency_ms", "timestamp", "top_k",
        "limitation_notice", "explainability_caveat",
    ):
        assert key in result, f"missing key: {key}"

    assert result["status"] in ("SUSPECTED", "INCONCLUSIVE")
    assert 0.0 <= result["confidence"] <= 1.0
    assert 0.0 <= result["uncertainty"] <= 1.0  # normalized entropy
    assert 0.0 <= result["estimated_visual_severity"] <= 1.0
    assert result["model_version"] == "0.1.0-test"
    assert result["dataset_version"] == "plantvillage@v1"
    assert result["threshold_version"] == "0.1"
    assert len(result["top_k"]) == 3
    assert abs(sum(t["confidence"] for t in result["top_k"]) - sum(sorted((t["confidence"] for t in result["top_k"]), reverse=True))) < 0.5
    assert "Decision support" in result["limitation_notice"]
    assert "not a guarantee of disease location" in result["explainability_caveat"]
    assert result["severity_label"] == "Estimated visual severity"
    assert result["condition"]["disease_id"] in class_list()
    assert result["crop"] in ("Tomato", "Potato", "Corn (maize)", "Apple")
    assert result["gradcam_overlay"] is not None
    assert Path(result["gradcam_overlay"]).exists()


def test_phrasing_never_claims_certainty(predictor, photo):
    result = predictor.predict(photo)
    if result["status"] == "SUSPECTED":
        assert result["phrasing"].startswith("Suspected ")
        assert "% confidence" in result["phrasing"]
    else:
        assert result["phrasing"].startswith("Inconclusive")
        assert "retake" in result["phrasing"]


def test_gradcam_regions_structure(predictor, photo):
    regions = predictor.predict(photo)["regions"]
    assert "num_cells" in regions and "fraction" in regions and "bbox_xyxy_norm" in regions
    assert 0.0 <= regions["fraction"] <= 1.0
    if regions["bbox_xyxy_norm"] is not None:
        x0, y0, x1, y1 = regions["bbox_xyxy_norm"]
        assert 0 <= x0 <= x1 <= 1 and 0 <= y0 <= y1 <= 1
