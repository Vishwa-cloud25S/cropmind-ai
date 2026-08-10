"""Farms & fields CRUD — authenticated + scoped (Phase 10).

Access rules (docs/04 §3.10): all endpoints need an account (401 otherwise —
farms are account data, not demo content). FARMER sees/creates own rows plus
legacy NULL-owner pre-auth rows (shared workspace, stated in payloads);
AGRONOMIST reads everything but cannot write farms/fields (403 with reason —
reviewer role); ADMIN does both. Out-of-scope rows answer 404 (existence is
not confirmed). Field crop_ids stay taxonomy-validated; deletes still 409 with
honest blocking counts.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.core.config import get_settings
from app.core.logging import request_id_ctx
from app.db import models
from app.db.session import DbSession
from app.services import security
from app.services.config_loader import load_taxonomy
from app.services.mapping import validate_wgs84_polygon
from app.services.ratelimit import enforce_write

router = APIRouter(tags=["farms"])


# ── payloads ───────────────────────────────────────────────────────────────────


class FarmCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    location: str | None = Field(default=None, max_length=300)


class FarmPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    location: str | None = None


class FieldCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    crop_id: str | None = Field(default=None, max_length=60)
    area_ha: float | None = Field(default=None, gt=0, le=100000)


class FieldPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    crop_id: str | None = Field(default=None, max_length=60)
    area_ha: float | None = Field(default=None, gt=0, le=100000)
    boundary_geojson: dict | None = None  # geographic WGS84 polygon drawn by the user (Phase 7)


def _farm_payload(db, farm: models.Farm) -> dict:
    field_count = db.execute(
        select(func.count()).select_from(models.Field).where(models.Field.farm_id == farm.id)
    ).scalar_one()
    return {
        "id": farm.id,
        "name": farm.name,
        "location": farm.location,
        "owner_id": farm.owner_id,  # null = pre-auth/demo legacy row (shared workspace, docs/04 §3.10)
        "field_count": field_count,
        "created_at": farm.created_at.isoformat() if farm.created_at else None,
    }


def _field_payload(field: models.Field) -> dict:
    return {
        "id": field.id,
        "farm_id": field.farm_id,
        "name": field.name,
        "crop_id": field.crop_id,  # taxonomy crop_id (may be null = undecided)
        "area_ha": field.area_ha,
        "boundary_geojson": field.boundary_geojson,  # geographic WGS84 polygon or null
        "created_at": field.created_at.isoformat() if field.created_at else None,
    }


def _valid_crop_ids() -> set[str]:
    taxonomy = load_taxonomy(str(get_settings().resolved_ml_config_dir))
    return {c["crop_id"] for c in taxonomy.get("crops", [])}


def _check_crop(crop_id: str | None) -> None:
    if crop_id is not None and crop_id not in _valid_crop_ids():
        raise HTTPException(
            400,
            {
                "detail": "unknown crop_id — only taxonomy-supported crops may be referenced",
                "allowed": sorted(_valid_crop_ids()),
            },
        )


def _audit(db, action: str, entity: str, entity_id: str | None, request: Request, user: models.User) -> None:
    db.add(
        models.AuditLog(
            user_id=user.id,
            action=action,
            entity=entity,
            entity_id=entity_id,
            ip=request.client.host if request.client else None,
            request_id=request_id_ctx.get(),
        )
    )


def _visible_farm(db: DbSession, farm_id: str, user: models.User, noun: str = "farm") -> models.Farm:
    farm = db.get(models.Farm, farm_id)
    if farm is None:
        raise HTTPException(404, f"{noun} not found")
    security.visible_or_404(farm.owner_id, user, noun)
    return farm


def _visible_field(db: DbSession, field_id: str, user: models.User) -> models.Field:
    field = db.get(models.Field, field_id)
    if field is None:
        raise HTTPException(404, "field not found")
    _visible_farm(db, field.farm_id, user, noun="field")
    return field


def _write_actor(request: Request, user: security.CurrentUser) -> models.User:
    enforce_write(request)
    return security.require_role(user, "FARMER", "ADMIN")


# ── farms ──────────────────────────────────────────────────────────────────────


@router.post("/farms", status_code=201)
def create_farm(body: FarmCreate, db: DbSession, request: Request, user: security.CurrentUser) -> dict:
    actor = _write_actor(request, user)
    farm = models.Farm(name=body.name, location=body.location, owner_id=actor.id)  # Phase 10: real owners
    db.add(farm)
    db.flush()
    _audit(db, "FARM_CREATED", "farm", farm.id, request, actor)
    return {"farm": _farm_payload(db, farm)}


@router.get("/farms")
def list_farms(
    db: DbSession, user: security.CurrentUser, limit: int = Query(default=50, ge=1, le=200), offset: int = 0
) -> dict:
    actor = security.require_user(user)
    stmt = (
        select(models.Farm)
        .where(security.ownership_filter(models.Farm.owner_id, actor))
        .order_by(models.Farm.created_at.desc(), models.Farm.id.desc())
        .limit(limit)
        .offset(offset)
    )
    rows = db.execute(stmt).scalars().all()
    return {
        "count": len(rows),
        "farms": [_farm_payload(db, f) for f in rows],
        "scope_note": "you see farms you own plus pre-auth NULL-owner rows (shared legacy workspace)"
        if actor.role == "FARMER"
        else f"{actor.role} scope: all farms",
    }


@router.get("/farms/{farm_id}")
def get_farm(farm_id: str, db: DbSession, user: security.CurrentUser) -> dict:
    actor = security.require_user(user)
    farm = _visible_farm(db, farm_id, actor)
    fields = (
        db.execute(select(models.Field).where(models.Field.farm_id == farm_id).order_by(models.Field.created_at))
        .scalars()
        .all()
    )
    return {"farm": _farm_payload(db, farm), "fields": [_field_payload(f) for f in fields]}


@router.patch("/farms/{farm_id}")
def patch_farm(farm_id: str, body: FarmPatch, db: DbSession, request: Request, user: security.CurrentUser) -> dict:
    actor = _write_actor(request, user)
    farm = _visible_farm(db, farm_id, actor)
    if body.name is not None:
        farm.name = body.name
    if body.location is not None:
        farm.location = body.location
    _audit(db, "FARM_UPDATED", "farm", farm.id, request, actor)
    return {"farm": _farm_payload(db, farm)}


@router.delete("/farms/{farm_id}", status_code=204)
def delete_farm(farm_id: str, db: DbSession, request: Request, user: security.CurrentUser) -> None:
    actor = _write_actor(request, user)
    farm = _visible_farm(db, farm_id, actor)
    field_count = db.execute(
        select(func.count()).select_from(models.Field).where(models.Field.farm_id == farm_id)
    ).scalar_one()
    if field_count:
        raise HTTPException(
            409, {"detail": "farm still has fields — delete or move them first", "field_count": field_count}
        )
    _audit(db, "FARM_DELETED", "farm", farm.id, request, actor)
    db.delete(farm)


# ── fields ─────────────────────────────────────────────────────────────────────


@router.post("/farms/{farm_id}/fields", status_code=201)
def create_field(farm_id: str, body: FieldCreate, db: DbSession, request: Request, user: security.CurrentUser) -> dict:
    actor = _write_actor(request, user)
    _visible_farm(db, farm_id, actor)
    _check_crop(body.crop_id)
    field = models.Field(farm_id=farm_id, name=body.name, crop_id=body.crop_id, area_ha=body.area_ha)
    db.add(field)
    db.flush()
    _audit(db, "FIELD_CREATED", "field", field.id, request, actor)
    return {"field": _field_payload(field)}


@router.get("/fields/{field_id}")
def get_field(field_id: str, db: DbSession, user: security.CurrentUser) -> dict:
    actor = security.require_user(user)
    return {"field": _field_payload(_visible_field(db, field_id, actor))}


@router.patch("/fields/{field_id}")
def patch_field(field_id: str, body: FieldPatch, db: DbSession, request: Request, user: security.CurrentUser) -> dict:
    actor = _write_actor(request, user)
    field = _visible_field(db, field_id, actor)
    _check_crop(body.crop_id)
    if body.name is not None:
        field.name = body.name
    if body.crop_id is not None:
        field.crop_id = body.crop_id
    if body.area_ha is not None:
        field.area_ha = body.area_ha
    if body.boundary_geojson is not None:
        try:
            field.boundary_geojson = validate_wgs84_polygon(body.boundary_geojson)
        except ValueError as exc:
            raise HTTPException(400, {"detail": f"invalid boundary: {exc}"}) from exc
    _audit(db, "FIELD_UPDATED", "field", field.id, request, actor)
    return {"field": _field_payload(field)}


@router.delete("/fields/{field_id}", status_code=204)
def delete_field(field_id: str, db: DbSession, request: Request, user: security.CurrentUser) -> None:
    actor = _write_actor(request, user)
    field = _visible_field(db, field_id, actor)
    image_count = db.execute(
        select(func.count()).select_from(models.Image).where(models.Image.field_id == field_id)
    ).scalar_one()
    zone_count = db.execute(
        select(func.count()).select_from(models.InterventionZone).join(models.Analysis).where(
            models.Analysis.field_id == field_id
        )
    ).scalar_one()
    if image_count or zone_count:
        raise HTTPException(
            409,
            {
                "detail": "field is referenced by uploaded imagery or zones — it cannot be removed",
                "image_count": image_count,
                "zone_count": zone_count,
            },
        )
    _audit(db, "FIELD_DELETED", "field", field.id, request, actor)
    db.delete(field)
