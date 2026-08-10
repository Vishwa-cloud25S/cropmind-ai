"""Feedback capture (Phase 10 — FR-18): per-account correctness verdicts.

Feedback is deliberately per-account (no anonymous submissions): a verdict that
can't be attributed can't be audited or followed up. Submissions feed the data
strategy (docs/07 data card) — the UI states this plainly; nothing is silently
re-trained (retraining is a separate, documented pipeline step).
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.core.logging import request_id_ctx
from app.db import models
from app.db.session import DbSession
from app.services import security
from app.services.ratelimit import client_ip, enforce_write

router = APIRouter(tags=["feedback"])

CORRECTNESS = ("YES", "NO", "NOT_SURE")
IMAGE_QUALITY = ("GOOD", "BLURRY", "BAD_LIGHTING", "NOT_A_LEAF")


class FeedbackCreate(BaseModel):
    correctness: Literal["YES", "NO", "NOT_SURE"]
    actual_condition: str | None = Field(default=None, max_length=120)
    notes: str | None = Field(default=None, max_length=2000)
    image_quality: Literal["GOOD", "BLURRY", "BAD_LIGHTING", "NOT_A_LEAF"] | None = None


def feedback_payload(row: models.Feedback, *, viewer: models.User | None = None) -> dict:
    payload = {
        "id": row.id,
        "analysis_id": row.analysis_id,
        "user_id": row.user_id,
        "correctness": row.correctness,
        "actual_condition": row.actual_condition,
        "notes": row.notes,
        "image_quality": row.image_quality,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }
    if viewer is not None and viewer.role in security.VISION_ALL_ROLES:
        payload["user_email"] = row.user.email if row.user else None
    return payload


def _analysis_visible(db, analysis_id: str, user: models.User) -> models.Analysis:
    analysis = db.get(models.Analysis, analysis_id)
    if analysis is None:
        raise HTTPException(404, "analysis not found")
    security.visible_or_404(analysis.requested_by, user, "analysis")
    return analysis


@router.post("/analyses/{analysis_id}/feedback", status_code=201)
def submit_feedback(analysis_id: str, body: FeedbackCreate, db: DbSession, request: Request, user: security.CurrentUser) -> dict:
    enforce_write(request)
    user = security.require_user(user)  # per-account by design — see module docstring
    analysis = _analysis_visible(db, analysis_id, user)
    if analysis.status != "COMPLETED" or analysis.prediction is None:
        raise HTTPException(
            409,
            {
                "detail": "feedback needs a completed prediction — verdicts on empty results are noise",
                "analysis_status": analysis.status,
            },
        )
    row = models.Feedback(
        analysis_id=analysis.id,
        user_id=user.id,
        correctness=body.correctness,
        actual_condition=body.actual_condition,
        notes=body.notes,
        image_quality=body.image_quality,
    )
    db.add(row)
    db.flush()
    db.add(
        models.AuditLog(
            user_id=user.id,
            action="FEEDBACK_SUBMITTED",
            entity="feedback",
            entity_id=row.id,
            ip=client_ip(request),
            request_id=request_id_ctx.get(),
        )
    )
    return {
        "feedback": feedback_payload(row),
        "note": "recorded against your account — it informs the data strategy; no automatic retraining happens",
    }


@router.get("/analyses/{analysis_id}/feedback")
def list_my_feedback(analysis_id: str, db: DbSession, user: security.CurrentUser) -> dict:
    """Own verdicts on this analysis (admins/agronomists get all rows for review)."""
    auth_user = security.require_user(user)
    analysis = db.get(models.Analysis, analysis_id)
    if analysis is None:
        raise HTTPException(404, "analysis not found")
    security.visible_or_404(analysis.requested_by, auth_user, "analysis")
    stmt = select(models.Feedback).where(models.Feedback.analysis_id == analysis_id)
    if auth_user.role not in security.VISION_ALL_ROLES:
        stmt = stmt.where(models.Feedback.user_id == auth_user.id)
    rows = db.execute(stmt.order_by(models.Feedback.created_at.desc())).scalars().all()
    return {"count": len(rows), "feedback": [feedback_payload(r, viewer=auth_user) for r in rows]}
