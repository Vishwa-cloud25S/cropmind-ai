"""Intervention simulator API (Phase 8): labelled spray-plan SIMULATION runs.

Honesty rules enforced here (docs/04 §3.8):
  * treatment polygons are USER-drawn WGS84 geography (validated exactly like
    field boundaries) — the simulator never scales image-space zones;
  * the declared rate is whatever the user typed; we reject non-positive rates
    and never suggest one; output is stored + served with SIMULATION labels;
  * every run persists params + result verbatim, so any savings figure the UI
    ever displayed can be re-derived and audited later.
"""

from __future__ import annotations

import json
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.core.logging import request_id_ctx
from app.db import models
from app.db.session import DbSession
from app.services import security, simbridge
from app.services.mapping import validate_wgs84_polygon
from app.services.ratelimit import enforce_write


def _visible_field(db, field_id: str, user) -> models.Field:
    field = db.get(models.Field, field_id)
    if field is None:
        raise HTTPException(404, "field not found")
    farm = db.get(models.Farm, field.farm_id)
    security.visible_or_404(farm.owner_id if farm else None, user, "field")
    return field

router = APIRouter(tags=["simulations"])


class SprayPlanRequest(BaseModel):
    field_id: str
    treatment_polygons: list[dict] = Field(min_length=1, max_length=50)
    spray_width_m: float = Field(gt=0.25, le=50)
    speed_mps: float = Field(gt=0.1, le=30)
    declared_rate_l_per_ha: float = Field(gt=0, le=2000)  # YOUR number — we never suggest rates
    turn_overhead_s: float = Field(default=0.0, ge=0, le=60)


@router.post("/simulations/spray-plan", status_code=201)
def create_spray_plan(body: SprayPlanRequest, db: DbSession, request: Request, user: security.CurrentUser) -> dict:
    enforce_write(request)
    actor = security.require_role(user, "FARMER", "ADMIN")  # planning action; AGRONOMIST reviews
    field = _visible_field(db, body.field_id, actor)
    if not field.boundary_geojson:
        raise HTTPException(
            409,
            {
                "detail": "field has no boundary — draw one on the Map page first; "
                "the simulator plans routes on real drawn geography, nothing else",
            },
        )
    treatments: list[dict] = []
    for index, polygon in enumerate(body.treatment_polygons, start=1):
        try:
            treatments.append(validate_wgs84_polygon(polygon))
        except ValueError as exc:
            raise HTTPException(400, {"detail": f"invalid treatment polygon {index}: {exc}"}) from exc

    try:
        run_row = simbridge.run_spray_plan(
            db,
            field,
            {
                "treatment_polygons": treatments,
                "spray_width_m": body.spray_width_m,
                "speed_mps": body.speed_mps,
                "declared_rate_l_per_ha": body.declared_rate_l_per_ha,
                "turn_overhead_s": body.turn_overhead_s,
            },
        )
    except ValueError as exc:  # engine constraints: inside/overlap/rate/swath cap — reason verbatim
        raise HTTPException(400, {"detail": str(exc)}) from exc

    db.add(
        models.AuditLog(
            user_id=actor.id,
            action="SIMULATION_RUN_CREATED",
            entity="simulation_run",
            entity_id=run_row.id,
            ip=request.client.host if request.client else None,
            request_id=request_id_ctx.get(),
        )
    )
    db.flush()
    return {"simulation": simbridge.simulation_payload(run_row)}


@router.get("/simulations")
def list_simulations(
    db: DbSession,
    user: security.CurrentUser,
    field_id: str | None = Query(default=None),
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: int = 0,
) -> dict:
    security.read_gate(user)
    stmt = (
        select(models.SimulationRun)
        .join(models.Field, models.SimulationRun.field_id == models.Field.id)
        .join(models.Farm, models.Field.farm_id == models.Farm.id)
        .where(security.ownership_filter(models.Farm.owner_id, user))
    )
    if field_id is not None:
        stmt = stmt.where(models.SimulationRun.field_id == field_id)
    rows = (
        db.execute(stmt.order_by(models.SimulationRun.created_at.desc(), models.SimulationRun.id.desc()).limit(limit).offset(offset))
        .scalars()
        .all()
    )
    return {
        "count": len(rows),
        "simulations": [simbridge.simulation_payload(r, summary=True) for r in rows],
        "note": "stored runs are reproducible: params + versioned engine → identical output (files win)",
    }


@router.get("/simulations/{simulation_id}")
def get_simulation(simulation_id: str, db: DbSession, user: security.CurrentUser) -> dict:
    security.read_gate(user)
    run_row = db.get(models.SimulationRun, simulation_id)
    if run_row is None:
        raise HTTPException(404, "simulation not found")
    _visible_field(db, run_row.field_id, user)
    return {"simulation": simbridge.simulation_payload(run_row)}


@router.get("/simulations/{simulation_id}/route.geojson")
def get_simulation_route(simulation_id: str, db: DbSession, user: security.CurrentUser) -> Response:
    security.read_gate(user)
    run_row = db.get(models.SimulationRun, simulation_id)
    if run_row is None:
        raise HTTPException(404, "simulation not found")
    _visible_field(db, run_row.field_id, user)
    route = run_row.result_json["route_geojson"]
    return Response(
        json.dumps(route, indent=2),
        media_type="application/geo+json",
        headers={"Content-Disposition": f'attachment; filename="cropmind-spray-simulation-route-{simulation_id[:8]}.geojson"'},
    )
