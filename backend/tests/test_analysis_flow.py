"""End-to-end analysis flow (Phase 5 core): upload → enqueue → worker tick → prediction.

The worker never loads torch here — a stub predictor returns the exact shipped
Predictor contract (ml/inference/predictor.py), so the tests assert the API/DB
maps that contract faithfully and loses no honesty fields.
"""

from __future__ import annotations

import io
from pathlib import Path

from PIL import Image as PILImage

from app.core.config import get_settings
from app.services.analysis import process_analysis
from app.services.mlbridge import ModelHandle
from app.workers.analysis_worker import tick


def _jpeg_bytes(size=(64, 48)) -> bytes:
    buf = io.BytesIO()
    PILImage.new("RGB", size, (18, 140, 60)).save(buf, "JPEG")
    return buf.getvalue()


def _contract(**overrides) -> dict:
    """A faithful copy of the Predictor's predict() dict (see ml/inference/predictor.py)."""
    result = {
        "prediction_id": "stub-contract-01",
        "status": "SUSPECTED",
        "phrasing": "Suspected corn - Northern Leaf Blight - 92% confidence",
        "crop": "corn",
        "condition": {"disease_id": "corn_northern_leaf_blight", "name": "Northern Leaf Blight"},
        "confidence": 0.9231,
        "confidence_band": "HIGH",
        "uncertainty": 0.21,
        "estimated_visual_severity": 0.18,
        "severity_label": "Estimated visual severity",
        "regions": {"num_cells": 4, "fraction": 0.18, "bbox_xyxy_norm": [0.1, 0.2, 0.6, 0.8], "threshold": 0.5},
        "gradcam_overlay": None,
        "model_version": "0.1.0",
        "dataset_version": "mendeley-v1",
        "threshold_version": "0.1",
        "latency_ms": 101.5,
        "timestamp": "2026-08-09T00:00:00+00:00",
        "top_k": [
            {"disease_id": "corn_northern_leaf_blight", "confidence": 0.9231},
            {"disease_id": "corn_cercospora", "confidence": 0.052},
            {"disease_id": "corn_common_rust", "confidence": 0.011},
        ],
        "limitation_notice": "Decision support only - not a definitive diagnosis.",
        "explainability_caveat": "Highlighted regions contribute strongly; not a disease-location guarantee.",
    }
    result.update(overrides)
    return result


class StubPredictor:
    """Same call surface as ml.inference.predictor.Predictor, no torch."""

    def __init__(self, result: dict):
        self._result = result
        self.calls = 0

    def predict(self, image_path: Path, explain_dir: Path | None = None, top_k: int = 3) -> dict:
        self.calls += 1
        result = dict(self._result)
        if explain_dir is not None:
            Path(explain_dir).mkdir(parents=True, exist_ok=True)
            overlay = Path(explain_dir) / "stub-gradcam.png"
            overlay.write_bytes(b"\x89PNG\r\n\x1a\n")  # content irrelevant to the mapping
            result["gradcam_overlay"] = str(overlay)
        return result


def _handle(stub: StubPredictor, tmp_path, demo: bool = True) -> ModelHandle:
    ckpt = tmp_path / "stub-checkpoint.pt"
    ckpt.write_bytes(b"stub")
    ckpt.with_suffix(".sha256").write_text("f" * 64 + "  stub-checkpoint.pt\n", encoding="utf-8")
    return ModelHandle(predictor=stub, checkpoint_path=ckpt, demo=demo)


def _upload(client) -> str:
    resp = client.post("/images", files={"file": ("leaf.jpg", _jpeg_bytes(), "image/jpeg")})
    assert resp.status_code == 201, resp.text
    return resp.json()["image"]["id"]


def test_full_flow_happy_path(client, tmp_path, db_session_factory) -> None:
    image_id = _upload(client)

    create = client.post("/analyses", json={"image_id": image_id, "demo": True})
    assert create.status_code == 202
    body = create.json()
    analysis_id = body["analysis_id"]
    assert body["status"] == "QUEUED"

    not_ready = client.get(f"/analyses/{analysis_id}/prediction")
    assert not_ready.status_code == 409  # honest: never serves a partial prediction

    status = client.get(f"/analyses/{analysis_id}")
    assert status.status_code == 200 and status.json()["job"]["attempts"] == 0

    stub = StubPredictor(_contract())
    processed = tick("test-worker", handle=_handle(stub, tmp_path))
    assert processed == 1 and stub.calls == 1

    status = client.get(f"/analyses/{analysis_id}")
    assert status.json()["status"] == "COMPLETED"

    resp = client.get(f"/analyses/{analysis_id}/prediction")
    assert resp.status_code == 200, resp.text
    pred = resp.json()

    # Honesty contract travels verbatim — nothing re-derived API-side.
    assert pred["status"] == "SUSPECTED"
    assert pred["phrasing"] == "Suspected corn - Northern Leaf Blight - 92% confidence"
    assert pred["band"] == "HIGH"
    assert pred["demo"] is True  # sample-model flag, never silent
    assert pred["analysis_demo_requested"] is True
    assert pred["model"] == {
        "name": "cropmind-leaf-classifier",
        "version": "0.1.0",
        "dataset_version": "mendeley-v1",
        "threshold_version": "0.1",
        "demo": True,
    }
    assert pred["regions"][0]["geometry"]["coordinate_space"] == "image-normalized-xyxy"
    assert pred["regions"][0]["area_px"] == round(0.18 * 64 * 48)
    assert pred["gradcam_available"] is True
    assert "human verification" in pred["client_notice"]
    assert pred["raw"]["top_k"] == _contract()["top_k"]  # contract preserved verbatim
    assert pred["raw"]["phrasing"] == pred["phrasing"]

    # Grad-CAM artifact is stored upload_dir-relative, alongside the image copies.
    from app.db import models

    with db_session_factory() as session:
        row = session.get(models.Prediction, pred["prediction_id"])
        assert row.gradcam_path.startswith("explain/")
        assert (Path(get_settings().upload_dir) / row.gradcam_path).is_file()

    assert tick("test-worker", handle=_handle(stub, tmp_path)) == 0  # queue drained


def test_processing_is_idempotent(client, tmp_path, db_session_factory) -> None:
    image_id = _upload(client)
    analysis_id = client.post("/analyses", json={"image_id": image_id}).json()["analysis_id"]
    stub = StubPredictor(_contract())
    handle = _handle(stub, tmp_path)
    assert tick("w", handle=handle) == 1
    # Direct re-invocation on a COMPLETED analysis: no second model run, no duplicate rows.
    process_analysis(
        db_session_factory, analysis_id, handle=handle, upload_dir=Path(get_settings().upload_dir)
    )
    assert stub.calls == 1
    from sqlalchemy import func, select

    from app.db import models

    with db_session_factory() as session:
        count = session.execute(select(func.count()).select_from(models.Prediction)).scalar_one()
        assert count == 1


def test_inconclusive_flow_below_low_band(client, tmp_path) -> None:
    image_id = _upload(client)
    analysis_id = client.post("/analyses", json={"image_id": image_id}).json()["analysis_id"]
    stub = StubPredictor(
        _contract(
            status="INCONCLUSIVE",
            phrasing=("Inconclusive (corn - Northern Leaf Blight at 22% is below the LOW band)"
                      " - retake photo or request agronomist review"),
            confidence=0.2199,
            confidence_band=None,
        )
    )
    assert tick("w", handle=_handle(stub, tmp_path)) == 1
    pred = client.get(f"/analyses/{analysis_id}/prediction").json()
    assert pred["status"] == "INCONCLUSIVE"
    assert pred["band"] is None
    assert pred["phrasing"].startswith("Inconclusive (")
    assert "retake photo" in pred["phrasing"]  # the honest guidance, verbatim


def test_analysis_of_unknown_image_404(client) -> None:
    resp = client.post("/analyses", json={"image_id": "does-not-exist"})
    assert resp.status_code == 404


def test_worker_failure_surfaces_honest_error(client, tmp_path, db_session_factory) -> None:
    image_id = _upload(client)
    analysis_id = client.post("/analyses", json={"image_id": image_id}).json()["analysis_id"]

    class BrokenPredictor(StubPredictor):
        def predict(self, image_path, explain_dir=None, top_k=3):
            raise OSError("cannot read image bytes")

    handle = _handle(BrokenPredictor(_contract()), tmp_path)
    # Run the job through ALL attempts; the queue fast-forward needs a DB touch per retry.
    from datetime import UTC, datetime

    from sqlalchemy import update

    from app.db import models

    for _ in range(3):
        tick("w", handle=handle)
        with db_session_factory.begin() as session:
            # Fast-forward the retry backoff so the next tick can claim the job.
            session.execute(
                update(models.AnalysisJob).values(run_after=datetime.now(UTC).replace(tzinfo=None))
            )
    with db_session_factory() as session:
        analysis = session.get(models.Analysis, analysis_id)
        assert analysis.status == "FAILED"
        assert "OSError" in analysis.error and "cannot read image bytes" in analysis.error
