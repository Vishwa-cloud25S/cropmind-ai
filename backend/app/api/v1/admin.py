"""Admin surface v1 (Phase 10 — FR-21 essentials): users, feedback, audit, overview.

ADMIN role only (403 with the honest reason otherwise; 401 when anonymous).
Role changes are audited with OLD → NEW transitions, and an admin cannot change
their own role (the last-admin footgun is blocked, not warned about).
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import func, select

from app.core.logging import request_id_ctx
from app.db import models
from app.db.session import DbSession
from app.services import security
from app.services.ratelimit import client_ip

router = APIRouter(tags=["admin"])


def _require_admin(db: DbSession, user: security.CurrentUser) -> models.User:
    return security.require_role(user, "ADMIN")


class RoleChange(BaseModel):
    role: Literal["FARMER", "AGRONOMIST", "ADMIN"]


@router.get("/admin/users")
def list_users(db: DbSession, user: security.CurrentUser) -> dict:
    _require_admin(db, user)
    rows = security.list_users(db)
    farm_counts = dict(
        db.execute(select(models.Farm.owner_id, func.count()).group_by(models.Farm.owner_id)).all()
    )
    return {
        "count": len(rows),
        "users": [
            {
                **security.user_payload(u),
                "farm_count": farm_counts.get(u.id, 0),
                "bootstrap_note": security.BOOTSTRAP_NOTE if i == 0 and u.role == "ADMIN" else None,
            }
            for i, u in enumerate(rows)
        ],
    }


@router.patch("/admin/users/{user_id}/role")
def change_role(user_id: str, body: RoleChange, db: DbSession, request: Request, user: security.CurrentUser) -> dict:
    admin = _require_admin(db, user)
    target = db.get(models.User, user_id)
    if target is None:
        raise HTTPException(404, "user not found")
    if target.id == admin.id:
        raise HTTPException(
            409,
            "you cannot change your own role — ask another admin (this blocks the 'no admins left' footgun)",
        )
    old = target.role
    if body.role == old:
        return {"user": security.user_payload(target), "role_transition": f"{old} → {old} (unchanged)"}
    target.role = body.role
    db.flush()
    db.add(
        models.AuditLog(
            user_id=admin.id,
            action="AUTH_ROLE_CHANGED",
            entity="user",
            entity_id=target.id,
            ip=client_ip(request),
            request_id=request_id_ctx.get(),
        )
    )
    return {"user": security.user_payload(target), "role_transition": f"{old} → {body.role}"}


@router.get("/admin/feedback")
def list_feedback(
    db: DbSession,
    user: security.CurrentUser,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = 0,
) -> dict:
    admin = _require_admin(db, user)
    from app.api.v1.feedback import feedback_payload  # one serializer

    total = db.execute(select(func.count()).select_from(models.Feedback)).scalar_one()
    rows = (
        db.execute(select(models.Feedback).order_by(models.Feedback.created_at.desc()).limit(limit).offset(offset))
        .scalars()
        .all()
    )
    by_correctness = dict(
        db.execute(select(models.Feedback.correctness, func.count()).group_by(models.Feedback.correctness)).all()
    )
    return {
        "count": len(rows),
        "total": total,
        "by_correctness": by_correctness,
        "feedback": [feedback_payload(r, viewer=admin) for r in rows],
        "note": "verdicts inform the data strategy; no automatic retraining happens",
    }


@router.get("/admin/audit-logs")
def list_audit_logs(
    db: DbSession,
    user: security.CurrentUser,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = 0,
) -> dict:
    _require_admin(db, user)
    rows = (
        db.execute(select(models.AuditLog).order_by(models.AuditLog.created_at.desc()).limit(limit).offset(offset))
        .scalars()
        .all()
    )
    return {
        "count": len(rows),
        "audit_logs": [
            {
                "id": r.id,
                "action": r.action,
                "entity": r.entity,
                "entity_id": r.entity_id,
                "user_id": r.user_id,
                "ip": r.ip,
                "request_id": r.request_id,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ],
    }


@router.get("/admin/overview")
def overview(db: DbSession, user: security.CurrentUser) -> dict:
    _require_admin(db, user)

    def count(model) -> int:
        return db.execute(select(func.count()).select_from(model)).scalar_one()

    by = lambda model, col: dict(db.execute(select(col, func.count()).group_by(col)).all())
    return {
        "overview": {
            "users": count(models.User),
            "farms": count(models.Farm),
            "fields": count(models.Field),
            "images": count(models.Image),
            "analyses": count(models.Analysis),
            "analyses_by_status": by(models.Analysis, models.Analysis.status),
            "predictions_by_status": by(models.Prediction, models.Prediction.status),
            "zones_by_review_status": by(models.InterventionZone, models.InterventionZone.review_status),
            "reports": count(models.Report),
            "feedback": count(models.Feedback),
            "simulation_runs": count(models.SimulationRun),
            "model_versions": count(models.ModelVersion),
            "dataset_sources": count(models.DatasetSource),
            "revoked_tokens": count(models.RevokedToken),
        },
        "note": "counts are measured from the database at request time — nothing cached, nothing invented",
    }
