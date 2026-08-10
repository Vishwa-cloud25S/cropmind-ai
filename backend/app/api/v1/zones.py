"""Intervention zones + field map data (Phase 7).

Zones are precision-intervention *simulations* in the evidence's coordinate space
(image-normalized-xyxy until a georeferenced source exists — see
app/services/mapping.py module docstring for the geo-honesty rules). Human review
(PENDING → APPROVED/REJECTED) is audited with old→new status, every time.
Exports are labelled simulations in filename and body.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.core.logging import request_id_ctx
from app.db import models
from app.db.session import DbSession
from app.services import mapping, security
from app.services.ratelimit import enforce_write

router = APIRouter(tags=["intervention-zones"])

_REVIEW_STATUSES = {"PENDING", "APPROVED", "REJECTED"}


def _audit(db, action: str, zone_id: str, request: Request, user: models.User | None = None) -> None:
    db.add(
        models.AuditLog(
            user_id=user.id if user else None,
            action=action,
            entity="intervention_zone",
            entity_id=zone_id,
            ip=request.client.host if request.client else None,
            request_id=request_id_ctx.get(),
        )
    )


def _visible_zone(db: DbSession, zone_id: str, user: models.User | None) -> models.InterventionZone:
    security.read_gate(user)
    zone = db.get(models.InterventionZone, zone_id)
    if zone is None:
        raise HTTPException(404, "intervention zone not found")
    security.visible_or_404(zone.analysis.requested_by, user, "intervention zone")
    return zone


# ── generation ─────────────────────────────────────────────────────────────────


@router.post("/analyses/{analysis_id}/intervention-zones", status_code=201)
def generate_analysis_zones(analysis_id: str, db: DbSession, request: Request, user: security.CurrentUser) -> dict:
    enforce_write(request)
    security.read_gate(user)
    analysis = db.get(models.Analysis, analysis_id)
    if analysis is None:
        raise HTTPException(404, "analysis not found")
    security.visible_or_404(analysis.requested_by, user, "analysis")
    if analysis.status != "COMPLETED" or analysis.prediction is None:
        raise HTTPException(
            409,
            {
                "detail": "analysis not completed — zones need a stored prediction",
                "analysis_status": analysis.status,
                "poll": f"/analyses/{analysis.id}",
            },
        )
    created, note = mapping.generate_zones(db, analysis)
    if created:
        _audit(db, "ZONES_GENERATED", created[0].id, request, user)
    db.flush()
    return {
        "count": len(created),
        "zones": [mapping.zone_payload(z, analysis) for z in created],
        "note": note,
        "simulation_label": mapping.SIMULATION_LABEL,
    }


# ── reads ──────────────────────────────────────────────────────────────────────


@router.get("/intervention-zones")
def list_zones(
    db: DbSession,
    user: security.CurrentUser,
    field_id: str | None = Query(default=None),
    review_status: str | None = Query(default=None),
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: int = 0,
) -> dict:
    security.read_gate(user)
    stmt = (
        select(models.InterventionZone)
        .join(models.Analysis, models.InterventionZone.analysis_id == models.Analysis.id)
        .where(security.ownership_filter(models.Analysis.requested_by, user))
    )
    if field_id is not None:
        stmt = stmt.where(models.Analysis.field_id == field_id)
    if review_status is not None:
        if review_status not in _REVIEW_STATUSES:
            raise HTTPException(400, {"detail": "unknown review_status filter", "allowed": sorted(_REVIEW_STATUSES)})
        stmt = stmt.where(models.InterventionZone.review_status == review_status)
    rows = (
        db.execute(
            stmt.order_by(models.InterventionZone.created_at.desc(), models.InterventionZone.id.desc())
            .limit(limit)
            .offset(offset)
        )
        .scalars()
        .all()
    )
    return {
        "count": len(rows),
        "zones": [mapping.zone_payload(z) for z in rows],
        "simulation_label": mapping.SIMULATION_LABEL,
    }


@router.get("/intervention-zones/export")
def export_zones(
    db: DbSession,
    user: security.CurrentUser,
    field_id: str | None = Query(default=None),
    review_status: str | None = Query(default=None),
    format: str = Query(default="geojson"),
) -> Response:
    security.read_gate(user)
    stmt = (
        select(models.InterventionZone)
        .join(models.Analysis, models.InterventionZone.analysis_id == models.Analysis.id)
        .where(security.ownership_filter(models.Analysis.requested_by, user))
    )
    if field_id is not None:
        stmt = stmt.where(models.Analysis.field_id == field_id)
    if review_status is not None:
        if review_status not in _REVIEW_STATUSES:
            raise HTTPException(400, {"detail": "unknown review_status filter", "allowed": sorted(_REVIEW_STATUSES)})
        stmt = stmt.where(models.InterventionZone.review_status == review_status)
    rows = db.execute(stmt.order_by(models.InterventionZone.created_at)).scalars().all()
    scope = field_id[:8] if field_id else "all"

    if format == "geojson":
        body = mapping.zones_geojson_export(rows)
        return Response(
            json.dumps(body, indent=2),
            media_type="application/geo+json",
            headers={"Content-Disposition": f'attachment; filename="cropmind-zone-simulation-{scope}.geojson"'},
        )
    if format == "csv":
        return Response(
            mapping.zones_csv_export(rows),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="cropmind-zone-simulation-{scope}.csv"'},
        )
    raise HTTPException(400, {"detail": "unknown export format", "allowed": ["csv", "geojson"]})


@router.get("/intervention-zones/{zone_id}")
def get_zone(zone_id: str, db: DbSession, user: security.CurrentUser) -> dict:
    return {"zone": mapping.zone_payload(_visible_zone(db, zone_id, user))}


# ── review ─────────────────────────────────────────────────────────────────────


class ZoneReview(BaseModel):
    review_status: str = Field(pattern="^(APPROVED|REJECTED)$")
    review_note: str | None = Field(default=None, max_length=500)


@router.patch("/intervention-zones/{zone_id}")
def review_zone(zone_id: str, body: ZoneReview, db: DbSession, request: Request, user: security.CurrentUser) -> dict:
    enforce_write(request)
    zone = _visible_zone(db, zone_id, user)
    previous = zone.review_status
    zone.review_status = body.review_status
    zone.review_note = body.review_note
    zone.reviewer_id = user.id if user else None
    zone.reviewed_at = datetime.now(UTC)
    _audit(db, "ZONE_REVIEWED", zone.id, request, user)
    db.flush()
    payload = mapping.zone_payload(zone)
    payload["review_transition"] = f"{previous} → {zone.review_status}"
    return {"zone": payload}


# ── map aggregation ────────────────────────────────────────────────────────────


@router.get("/fields/{field_id}/map-data")
def field_map_data(field_id: str, db: DbSession, user: security.CurrentUser) -> dict:
    """Everything the map page needs in one honest read — no derived data invented
    client-side; the decision-support strip is computed from stored rows only."""
    security.read_gate(user)
    field = db.get(models.Field, field_id)
    if field is None:
        raise HTTPException(404, "field not found")
    farm = db.get(models.Farm, field.farm_id)
    security.visible_or_404(farm.owner_id if farm else None, user, "field")

    analyses = (
        db.execute(
            select(models.Analysis)
            .where(models.Analysis.field_id == field_id)
            .order_by(models.Analysis.created_at.desc())
            .limit(100)
        )
        .scalars()
        .all()
    )
    zones = (
        db.execute(
            select(models.InterventionZone)
            .join(models.Analysis, models.InterventionZone.analysis_id == models.Analysis.id)
            .where(models.Analysis.field_id == field_id)
            .order_by(models.InterventionZone.created_at.desc())
        )
        .scalars()
        .all()
    )

    risk_counts = {level: 0 for level in mapping.RISK_ORDER}
    review_counts = {status: 0 for status in sorted(_REVIEW_STATUSES)}
    for zone in zones:
        risk_counts[zone.risk_level] += 1
        review_counts[zone.review_status] += 1
    pending = [z for z in zones if z.review_status == "PENDING"]
    pending.sort(key=lambda z: (mapping.review_priority(z.risk_level)[0], z.created_at))
    first_priority = [z.id for z in pending[:3]]

    return {
        "field": {
            "id": field.id,
            "farm_id": field.farm_id,
            "farm_name": field.farm.name if field.farm else None,
            "name": field.name,
            "crop_id": field.crop_id,
            "area_ha": field.area_ha,
            "boundary_geojson": field.boundary_geojson,
        },
        "analyses": [
            {
                "analysis_id": a.id,
                "image_id": a.image_id,
                "status": a.status,
                "demo": a.demo,
                "created_at": a.created_at.isoformat() if a.created_at else None,
                "prediction": (
                    {
                        "status": a.prediction.status,
                        "phrasing": a.prediction.phrasing,
                        "band": a.prediction.band,
                        "confidence": a.prediction.confidence,
                        "demo": a.prediction.demo,
                    }
                    if a.prediction
                    else None
                ),
            }
            for a in analyses
        ],
        "zones": [mapping.zone_payload(z) for z in zones],
        "decision_support": {
            "risk_counts": risk_counts,
            "review_counts": review_counts,
            "pending_zone_count": len(pending),
            "first_priority_zone_ids": first_priority,
            "note": "Rule-based triage from stored risk levels (docs/04 §3.7) — review order, not an agronomic risk score.",
            "simulation_label": mapping.SIMULATION_LABEL,
        },
    }
