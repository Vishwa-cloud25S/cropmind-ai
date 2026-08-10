"""Analyses API (Phase 5; auth-scoped Phase 10): enqueue (202 Accepted), status,
prediction read-back.

The prediction payload is the stored Predictor contract — the API never re-derives
honesty fields (Suspected-phrasing, bands, INCONCLUSIVE, caveats travel verbatim in
raw_json). Demo predictions (sample model) are flagged, never silent. Access follows
docs/04 §3.10: an account, or the flagged anonymous demo path; reads follow the
requested_by visibility rule.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.core.config import get_settings
from app.db import models
from app.db.session import DbSession, get_session_factory
from app.services import security
from app.services.queue import LocalDbQueue
from app.services.ratelimit import enforce_write

router = APIRouter(tags=["analyses"])


class AnalysisCreate(BaseModel):
    image_id: str
    field_id: str | None = None
    demo: bool = Field(default=False)


def _queue() -> LocalDbQueue:
    return LocalDbQueue(get_session_factory())


def _visible_analysis(db: DbSession, analysis_id: str, user: models.User | None) -> models.Analysis:
    security.read_gate(user)
    analysis = db.get(models.Analysis, analysis_id)
    if analysis is None:
        raise HTTPException(404, "analysis not found")
    security.visible_or_404(analysis.requested_by, user, "analysis")
    return analysis


@router.post("/analyses", status_code=202)
def create_analysis(body: AnalysisCreate, db: DbSession, request: Request, user: security.CurrentUser) -> dict:
    enforce_write(request)
    actor = security.require_user(user, demo_ok=True)
    demo_flag = bool(body.demo and get_settings().demo_mode)
    if actor is None and not demo_flag:
        raise HTTPException(
            401,
            {"detail": "sign in to run analyses on your imagery — or set demo=true (flagged) without an account"},
            headers={"WWW-Authenticate": "Bearer"},
        )
    image = db.get(models.Image, body.image_id)
    if image is None:
        raise HTTPException(404, "image not found")
    security.visible_or_404(image.uploader_id, actor, "image")
    field_id = body.field_id or image.field_id
    if field_id is not None:
        field = db.get(models.Field, field_id)
        if field is None:
            raise HTTPException(404, "field not found")
        farm = db.get(models.Farm, field.farm_id)
        security.visible_or_404(farm.owner_id if farm else None, actor, "field")
    analysis = models.Analysis(
        image_id=image.id,
        field_id=field_id,
        requested_by=actor.id if actor else None,
        demo=demo_flag,
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
    user: security.CurrentUser,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = 0,
    status: str | None = Query(default=None),
) -> dict:
    """History surface (Phase 6 UI): newest-first, scoped; optional status filter."""
    security.read_gate(user)
    stmt = select(models.Analysis).where(security.ownership_filter(models.Analysis.requested_by, user))
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
    return {
        "count": len(rows),
        "analyses": [_status_payload(a) for a in rows],
        "scope_note": "own + legacy NULL-owner rows (FARMER) · all rows (ADMIN/AGRONOMIST) · demo rows only (anonymous demo)",
    }


@router.get("/analyses/{analysis_id}")
def get_analysis(analysis_id: str, db: DbSession, user: security.CurrentUser) -> dict:
    return _status_payload(_visible_analysis(db, analysis_id, user))


@router.get("/analyses/{analysis_id}/prediction")
def get_analysis_prediction(analysis_id: str, db: DbSession, user: security.CurrentUser) -> dict:
    from app.api.v1.predictions import prediction_payload  # local import: one serializer

    analysis = _visible_analysis(db, analysis_id, user)
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
def get_analysis_gradcam(analysis_id: str, db: DbSession, user: security.CurrentUser) -> FileResponse:
    """Serves the stored Grad-CAM overlay for the analysis view (Phase 6 UI)."""
    analysis = _visible_analysis(db, analysis_id, user)
    if analysis.status != "COMPLETED" or analysis.prediction is None or not analysis.prediction.gradcam_path:
        raise HTTPException(
            409,
            {"detail": "Grad-CAM overlay not available", "analysis_status": analysis.status},
        )
    target = Path(get_settings().upload_dir) / analysis.prediction.gradcam_path
    if not target.is_file():
        raise HTTPException(404, "stored overlay missing")
    return FileResponse(target, media_type="image/png", filename=f"cropmind-gradcam-{analysis_id[:8]}.png")
