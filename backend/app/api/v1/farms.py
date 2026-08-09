"""Farms & fields CRUD (Phase 6 frontend consumes these).

Pre-auth like the rest of the Phase 5/6 API (per-user scoping arrives with JWT in
Phase 10 — schema columns already exist). Field crop_ids are validated against the
published taxonomy: a field may only ever reference a crop the product supports.
Deletes are blocked (409) while children reference the row — honest conflict, no
silent cascades.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.core.config import get_settings
from app.core.logging import request_id_ctx
from app.db import models
from app.db.session import DbSession
from app.services.config_loader import load_taxonomy

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


def _farm_payload(db, farm: models.Farm) -> dict:
    field_count = db.execute(
        select(func.count()).select_from(models.Field).where(models.Field.farm_id == farm.id)
    ).scalar_one()
    return {
        "id": farm.id,
        "name": farm.name,
        "location": farm.location,
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


def _audit(db, action: str, entity: str, entity_id: str | None, request: Request) -> None:
    db.add(
        models.AuditLog(
            action=action,
            entity=entity,
            entity_id=entity_id,
            ip=request.client.host if request.client else None,
            request_id=request_id_ctx.get(),
        )
    )


# ── farms ──────────────────────────────────────────────────────────────────────


@router.post("/farms", status_code=201)
def create_farm(body: FarmCreate, db: DbSession, request: Request) -> dict:
    # owner_id stays NULL pre-auth (migration 0002); Phase 10 assigns real owners.
    farm = models.Farm(name=body.name, location=body.location, owner_id=None)
    db.add(farm)
    db.flush()
    _audit(db, "FARM_CREATED", "farm", farm.id, request)
    return {"farm": _farm_payload(db, farm)}


@router.get("/farms")
def list_farms(db: DbSession, limit: int = Query(default=50, ge=1, le=200), offset: int = 0) -> dict:
    rows = (
        db.execute(
            select(models.Farm).order_by(models.Farm.created_at.desc(), models.Farm.id.desc()).limit(limit).offset(offset)
        )
        .scalars()
        .all()
    )
    return {"count": len(rows), "farms": [_farm_payload(db, f) for f in rows]}


@router.get("/farms/{farm_id}")
def get_farm(farm_id: str, db: DbSession) -> dict:
    farm = db.get(models.Farm, farm_id)
    if farm is None:
        raise HTTPException(404, "farm not found")
    fields = (
        db.execute(
            select(models.Field).where(models.Field.farm_id == farm_id).order_by(models.Field.created_at)
        )
        .scalars()
        .all()
    )
    return {"farm": _farm_payload(db, farm), "fields": [_field_payload(f) for f in fields]}


@router.patch("/farms/{farm_id}")
def patch_farm(farm_id: str, body: FarmPatch, db: DbSession, request: Request) -> dict:
    farm = db.get(models.Farm, farm_id)
    if farm is None:
        raise HTTPException(404, "farm not found")
    if body.name is not None:
        farm.name = body.name
    if body.location is not None:
        farm.location = body.location
    _audit(db, "FARM_UPDATED", "farm", farm.id, request)
    return {"farm": _farm_payload(db, farm)}


@router.delete("/farms/{farm_id}", status_code=204)
def delete_farm(farm_id: str, db: DbSession, request: Request) -> None:
    farm = db.get(models.Farm, farm_id)
    if farm is None:
        raise HTTPException(404, "farm not found")
    field_count = db.execute(
        select(func.count()).select_from(models.Field).where(models.Field.farm_id == farm_id)
    ).scalar_one()
    if field_count:
        raise HTTPException(
            409, {"detail": "farm still has fields — delete or move them first", "field_count": field_count}
        )
    _audit(db, "FARM_DELETED", "farm", farm.id, request)
    db.delete(farm)


# ── fields ─────────────────────────────────────────────────────────────────────


@router.post("/farms/{farm_id}/fields", status_code=201)
def create_field(farm_id: str, body: FieldCreate, db: DbSession, request: Request) -> dict:
    farm = db.get(models.Farm, farm_id)
    if farm is None:
        raise HTTPException(404, "farm not found")
    _check_crop(body.crop_id)
    field = models.Field(farm_id=farm_id, name=body.name, crop_id=body.crop_id, area_ha=body.area_ha)
    db.add(field)
    db.flush()
    _audit(db, "FIELD_CREATED", "field", field.id, request)
    return {"field": _field_payload(field)}


@router.get("/fields/{field_id}")
def get_field(field_id: str, db: DbSession) -> dict:
    field = db.get(models.Field, field_id)
    if field is None:
        raise HTTPException(404, "field not found")
    return {"field": _field_payload(field)}


@router.patch("/fields/{field_id}")
def patch_field(field_id: str, body: FieldPatch, db: DbSession, request: Request) -> dict:
    field = db.get(models.Field, field_id)
    if field is None:
        raise HTTPException(404, "field not found")
    _check_crop(body.crop_id)
    if body.name is not None:
        field.name = body.name
    if body.crop_id is not None:
        field.crop_id = body.crop_id
    if body.area_ha is not None:
        field.area_ha = body.area_ha
    _audit(db, "FIELD_UPDATED", "field", field.id, request)
    return {"field": _field_payload(field)}


@router.delete("/fields/{field_id}", status_code=204)
def delete_field(field_id: str, db: DbSession, request: Request) -> None:
    field = db.get(models.Field, field_id)
    if field is None:
        raise HTTPException(404, "field not found")
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
    _audit(db, "FIELD_DELETED", "field", field.id, request)
    db.delete(field)
