"""Images API (Phase 5; auth-scoped Phase 10): upload with the security pipeline,
read metadata, download the re-encoded copy. Writes are audited with request id +
client ip (docs/02 §9/§10).

Access (docs/04 §3.10): authenticated uploads record `uploader_id`; the anonymous
demo path (DEMO_MODE + demo=true) is the only unsigned upload, and it is always
stored flagged `DEMO`. Reads follow the uploader-visibility rule (own + legacy
NULL rows; ADMIN/AGRONOMIST see all). Content dedupe is global — identical bytes
map to one row; if that row is outside your scope you get an honest 409 instead
of a peek at someone else's upload metadata."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.exc import IntegrityError

from app.core.config import get_settings
from app.core.logging import request_id_ctx
from app.db import models
from app.db.session import DbSession
from app.services import security
from app.services.ratelimit import enforce_write
from app.services.uploads import UploadRejected, store_upload

router = APIRouter(tags=["images"])

CHUNK = 1024 * 1024


def _audit(session, action: str, entity_id: str, request: Request, user: models.User | None = None) -> None:
    session.add(
        models.AuditLog(
            user_id=user.id if user else None,
            action=action,
            entity="image",
            entity_id=entity_id,
            ip=request.client.host if request.client else None,
            request_id=request_id_ctx.get(),
        )
    )


def _image_payload(image: models.Image) -> dict:
    return {
        "id": image.id,
        "field_id": image.field_id,
        "uploader_id": image.uploader_id,  # null = demo/legacy row (shared workspace)
        "sha256": image.sha256,
        "width": image.width,
        "height": image.height,
        "byte_size": image.byte_size,
        "captured_at": image.captured_at.isoformat() if image.captured_at else None,
        "exif": image.exif_json,
        "source_type": image.source_type,
        "created_at": image.created_at.isoformat() if image.created_at else None,
    }


def _visible_image(db: DbSession, image_id: str, user: models.User | None) -> models.Image:
    security.read_gate(user)
    image = db.get(models.Image, image_id)
    if image is None:
        raise HTTPException(404, "image not found")
    security.visible_or_404(image.uploader_id, user, "image")
    return image


@router.post("/images", status_code=201)
async def upload_image(
    request: Request,
    db: DbSession,
    user: security.CurrentUser,
    file: UploadFile = File(...),
    field_id: str | None = Query(default=None),
    demo: bool = Query(default=False),
) -> dict:
    enforce_write(request)
    # Auth rule: an account, or the clearly-flagged anonymous demo path.
    actor = security.require_user(user, demo_ok=True)
    demo_flag = bool(demo and get_settings().demo_mode)
    if actor is None and not demo_flag:
        # require_user(demo_ok) lets anonymous callers through only to be checked here:
        # demo=false anonymously is not a real upload path.
        raise HTTPException(
            401,
            {"detail": "sign in to upload your own imagery — or use demo=true (flagged DEMO) without an account"},
            headers={"WWW-Authenticate": "Bearer"},
        )
    if field_id is not None:
        field = db.get(models.Field, field_id)
        if field is None:
            raise HTTPException(404, "field not found")
        farm = db.get(models.Farm, field.farm_id)
        security.visible_or_404(farm.owner_id if farm else None, actor, "field")

    settings = get_settings()
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    content = bytearray()
    while chunk := await file.read(CHUNK):
        content += chunk
        if len(content) > max_bytes:
            raise HTTPException(413, f"image exceeds the {settings.max_upload_size_mb} MB limit")
    try:
        stored = store_upload(
            bytes(content),
            declared_content_type=file.content_type,
            upload_dir=Path(settings.upload_dir),
            max_bytes=max_bytes,
            max_side=settings.upload_max_side,
            thumb_side=settings.upload_thumb_side,
        )
    except UploadRejected as exc:
        raise HTTPException(exc.code, exc.detail) from exc

    existing = db.query(models.Image).filter(models.Image.sha256 == stored.sha256).first()
    if existing is not None:
        # Dedupe: content identity wins over file identity; the stray normalized copy is removed.
        for rel in (stored.path, stored.thumb_path):
            try:
                (Path(settings.upload_dir) / rel).unlink(missing_ok=True)
            except OSError:
                pass
        try:
            security.visible_or_404(existing.uploader_id, actor, "image")
        except HTTPException as exc:  # identical bytes already live under another account
            raise HTTPException(
                409,
                {
                    "detail": "these exact bytes are already stored under another account — "
                    "content dedupe is global, so the existing copy cannot be shared into your workspace",
                    "deduplicated": True,
                },
            ) from exc
        _audit(db, "IMAGE_UPLOAD_DEDUPLICATED", existing.id, request, actor)
        payload = _image_payload(existing)
        payload["deduplicated"] = True
        return {"image": payload}

    image = models.Image(
        id=stored.image_id,
        field_id=field_id,
        uploader_id=actor.id if actor else None,
        path=stored.path,
        thumb_path=stored.thumb_path,
        sha256=stored.sha256,
        width=stored.width,
        height=stored.height,
        byte_size=stored.byte_size,
        captured_at=stored.captured_at,
        exif_json=stored.exif_json,
        source_type="DEMO" if demo_flag else "SMARTPHONE",
    )
    db.add(image)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(400, "invalid field_id or duplicate image") from None
    _audit(db, "IMAGE_UPLOADED", image.id, request, actor)
    payload = _image_payload(image)
    payload["deduplicated"] = False
    if actor is None:
        payload["demo_note"] = "anonymous demo upload — flagged DEMO; sign in for a private workspace"
    return {"image": payload}


@router.get("/images/{image_id}")
def get_image(image_id: str, db: DbSession, user: security.CurrentUser) -> dict:
    return {"image": _image_payload(_visible_image(db, image_id, user))}


@router.get("/images/{image_id}/download")
def download_image(image_id: str, db: DbSession, user: security.CurrentUser, thumb: bool = False) -> FileResponse:
    """Serves the server-side re-encode (or its thumbnail) — never the original bytes."""
    image = _visible_image(db, image_id, user)
    rel = image.thumb_path if thumb else image.path
    target = Path(get_settings().upload_dir) / rel
    if not target.is_file():
        raise HTTPException(404, "stored file missing")
    return FileResponse(target, media_type="image/jpeg", filename=f"cropmind-{image_id[:8]}{'-thumb' if thumb else ''}.jpg")
