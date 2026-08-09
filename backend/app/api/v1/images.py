"""Images API (Phase 5): upload with the security pipeline, read metadata, download the
re-encoded copy. Writes are audited with request id + client ip (docs/02 §9/§10)."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.exc import IntegrityError

from app.core.config import get_settings
from app.core.logging import request_id_ctx
from app.db import models
from app.db.session import DbSession
from app.services.uploads import UploadRejected, store_upload

router = APIRouter(tags=["images"])

CHUNK = 1024 * 1024


def _audit(session, action: str, entity_id: str, request: Request) -> None:
    session.add(
        models.AuditLog(
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
        "sha256": image.sha256,
        "width": image.width,
        "height": image.height,
        "byte_size": image.byte_size,
        "captured_at": image.captured_at.isoformat() if image.captured_at else None,
        "exif": image.exif_json,
        "source_type": image.source_type,
        "created_at": image.created_at.isoformat() if image.created_at else None,
    }


@router.post("/images", status_code=201)
async def upload_image(
    request: Request,
    db: DbSession,
    file: UploadFile = File(...),
    field_id: str | None = Query(default=None),
    demo: bool = Query(default=False),
) -> dict:
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
        _audit(db, "IMAGE_UPLOAD_DEDUPLICATED", existing.id, request)
        payload = _image_payload(existing)
        payload["deduplicated"] = True
        return {"image": payload}

    image = models.Image(
        id=stored.image_id,
        field_id=field_id,
        path=stored.path,
        thumb_path=stored.thumb_path,
        sha256=stored.sha256,
        width=stored.width,
        height=stored.height,
        byte_size=stored.byte_size,
        captured_at=stored.captured_at,
        exif_json=stored.exif_json,
        source_type="DEMO" if (demo and settings.demo_mode) else "SMARTPHONE",
    )
    db.add(image)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(400, "invalid field_id or duplicate image") from None
    _audit(db, "IMAGE_UPLOADED", image.id, request)
    payload = _image_payload(image)
    payload["deduplicated"] = False
    return {"image": payload}


@router.get("/images/{image_id}")
def get_image(image_id: str, db: DbSession) -> dict:
    image = db.get(models.Image, image_id)
    if image is None:
        raise HTTPException(404, "image not found")
    return {"image": _image_payload(image)}


@router.get("/images/{image_id}/download")
def download_image(image_id: str, db: DbSession, thumb: bool = False) -> FileResponse:
    """Serves the server-side re-encode (or its thumbnail) — never the original bytes."""
    image = db.get(models.Image, image_id)
    if image is None:
        raise HTTPException(404, "image not found")
    rel = image.thumb_path if thumb else image.path
    target = Path(get_settings().upload_dir) / rel
    if not target.is_file():
        raise HTTPException(404, "stored file missing")
    return FileResponse(target, media_type="image/jpeg", filename=f"cropmind-{image_id[:8]}{'-thumb' if thumb else ''}.jpg")
