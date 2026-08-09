"""Analyses API (Phase 5): enqueue (202 Accepted), status, prediction read-back.

The prediction payload is the stored Predictor contract — the API never re-derives
honesty fields (Suspected-phrasing, bands, INCONCLUSIVE, caveats travel verbatim in
raw_json). Demo predictions (sample model) are flagged, never silent.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.core.config import get_settings
from app.db import models
from app.db.session import DbSession, get_session_factory
from app.services.queue import LocalDbQueue

router = APIRouter(tags=["analyses"])


class AnalysisCreate(BaseModel):
    image_id: str
    field_id: str | None = None
    demo: bool = Field(default=False)


def _queue() -> LocalDbQueue:
    return LocalDbQueue(get_session_factory())


@router.post("/analyses", status_code=202)
def create_analysis(body: AnalysisCreate, db: DbSession) -> dict:
    image = db.get(models.Image, body.image_id)
    if image is None:
        raise HTTPException(404, "image not found")
    analysis = models.Analysis(
        image_id=image.id,
        field_id=body.field_id or image.field_id,
        demo=bool(body.demo and get_settings().demo_mode),
    )
    db.add(analysis)
    db.flush()
    # Same-session enqueue: analysis + job commit atomically (FK safety — see queue.enqueue).
    job = _queue().enqueue(
        analysis.id, max_attempts=get_settings().job_max_attempts, session=db
    )
    return {
        "analysis_id": analysis.id,
        "job_id": job.id,
        "status": "QUEUED",
        "poll": f"/analyses/{analysis.id}",
        "note": "202 Accepted — the ML worker picks this up asynchronously.",
    }


def _status_payload(analysis: models.Analysis) -> dict:
    job = analysis.job
    payload = {
        "analysis_id": analysis.id,
        "image_id": analysis.image_id,
        "status": analysis.status,
        "demo": analysis.demo,
        "created_at": analysis.created_at.isoformat() if analysis.created_at else None,
        "started_at": analysis.started_at.isoformat() if analysis.started_at else None,
        "completed_at": analysis.completed_at.isoformat() if analysis.completed_at else None,
        "error": analysis.error,
    }
    if job is not None:
        payload["job"] = {
            "id": job.id,
            "status": job.status,
            "attempts": job.attempts,
            "max_attempts": job.max_attempts,
        }
    return payload


@router.get("/analyses")
def list_analyses(
    db: DbSession,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = 0,
    status: str | None = Query(default=None),
) -> dict:
    """History surface (Phase 6 UI): newest-first; optional status filter."""
    stmt = select(models.Analysis)
    if status is not None:
        allowed = {"QUEUED", "PROCESSING", "COMPLETED", "FAILED"}
        if status not in allowed:
            raise HTTPException(400, {"detail": "unknown status filter", "allowed": sorted(allowed)})
        stmt = stmt.where(models.Analysis.status == status)
    rows = (
        db.execute(stmt.order_by(models.Analysis.created_at.desc(), models.Analysis.id.desc()).limit(limit).offset(offset))
        .scalars()
        .all()
    )
    return {"count": len(rows), "analyses": [_status_payload(a) for a in rows]}


@router.get("/analyses/{analysis_id}")
def get_analysis(analysis_id: str, db: DbSession) -> dict:
    analysis = db.get(models.Analysis, analysis_id)
    if analysis is None:
        raise HTTPException(404, "analysis not found")
    return _status_payload(analysis)


@router.get("/analyses/{analysis_id}/prediction")
def get_analysis_prediction(analysis_id: str, db: DbSession) -> dict:
    from app.api.v1.predictions import prediction_payload  # local import: one serializer

    analysis = db.get(models.Analysis, analysis_id)
    if analysis is None:
        raise HTTPException(404, "analysis not found")
    if analysis.status != "COMPLETED" or analysis.prediction is None:
        raise HTTPException(
            409,
            {
                "detail": "prediction not ready",
                "analysis_status": analysis.status,
                "poll": f"/analyses/{analysis.id}",
            },
        )
    return prediction_payload(analysis.prediction, analysis=analysis)


@router.get("/analyses/{analysis_id}/gradcam")
def get_analysis_gradcam(analysis_id: str, db: DbSession) -> FileResponse:
    """Serves the stored Grad-CAM overlay for the analysis view (Phase 6 UI)."""
    analysis = db.get(models.Analysis, analysis_id)
    if analysis is None:
        raise HTTPException(404, "analysis not found")
    if analysis.status != "COMPLETED" or analysis.prediction is None or not analysis.prediction.gradcam_path:
        raise HTTPException(
            409,
            {"detail": "Grad-CAM overlay not available", "analysis_status": analysis.status},
        )
    target = Path(get_settings().upload_dir) / analysis.prediction.gradcam_path
    if not target.is_file():
        raise HTTPException(404, "stored overlay missing")
    return FileResponse(target, media_type="image/png", filename=f"cropmind-gradcam-{analysis_id[:8]}.png")
