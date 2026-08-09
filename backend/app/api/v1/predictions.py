"""Predictions API (Phase 5): read-only truth of stored predictions.

The phrasing is exactly what the model module produced ("Suspected {crop} - {name} -
{x}% confidence"), bands and INCONCLUSIVE included; no number is re-computed here.
Demo (sample-model) predictions are flagged at top level, never silent.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from app.db import models
from app.db.session import DbSession

router = APIRouter(tags=["predictions"])

CLIENT_NOTICE = (
    "Predictions are decision support requiring human verification. Suspected-condition "
    "screening only — no chemical product or dosage guidance is provided."
)


def prediction_payload(prediction: models.Prediction, *, analysis: models.Analysis | None = None) -> dict:
    return {
        "prediction_id": prediction.id,
        "analysis_id": prediction.analysis_id,
        "status": prediction.status,
        "phrasing": prediction.phrasing,
        "crop": prediction.crop,
        "condition": {"disease_id": prediction.condition, "name": prediction.condition_name},
        "confidence": prediction.confidence,
        "band": prediction.band,
        "uncertainty": prediction.uncertainty,
        "estimated_visual_severity": prediction.severity,
        "severity_label": "Estimated visual severity",
        "latency_ms": prediction.latency_ms,
        "demo": prediction.demo,
        "model": {
            "name": prediction.model_version.name,
            "version": prediction.model_version.version,
            "dataset_version": prediction.model_version.dataset_version,
            "threshold_version": prediction.model_version.threshold_version,
            "demo": prediction.model_version.demo,
        },
        "regions": [
            {"geometry": r.geometry_geojson, "area_px": r.area_px, "confidence": r.confidence}
            for r in prediction.regions
        ],
        "gradcam_available": prediction.gradcam_path is not None,
        "created_at": prediction.created_at.isoformat() if prediction.created_at else None,
        "analysis_demo_requested": analysis.demo if analysis else None,
        "client_notice": CLIENT_NOTICE,
        "explainability_caveat": (
            "Highlighted regions indicate areas that contributed strongly to the model's "
            "prediction. They are not a guarantee of disease location."
        ),
        "raw": prediction.raw_json,  # the full model-module contract, verbatim
    }


@router.get("/predictions")
def list_predictions(db: DbSession, limit: int = Query(default=20, ge=1, le=100), offset: int = 0) -> dict:
    rows = (
        db.execute(
            select(models.Prediction)
            .order_by(models.Prediction.created_at.desc(), models.Prediction.id.desc())
            .limit(limit)
            .offset(offset)
        )
        .scalars()
        .all()
    )
    return {
        "count": len(rows),
        "predictions": [prediction_payload(r) for r in rows],
        "client_notice": CLIENT_NOTICE,
    }


@router.get("/predictions/{prediction_id}")
def get_prediction(prediction_id: str, db: DbSession) -> dict:
    prediction = db.get(models.Prediction, prediction_id)
    if prediction is None:
        raise HTTPException(404, "prediction not found")
    return prediction_payload(prediction, analysis=prediction.analysis)
