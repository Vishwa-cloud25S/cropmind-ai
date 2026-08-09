"""Upload validation + safe storage (docs/02 §9 security contract).

Guards, in order: declared content-type precheck → streamed size cap → MAGIC BYTES
(never the extension) → Pillow decode+verify → EXIF orientation normalize → re-encode
before serving → sha256 dedupe. Filenames are server-generated UUIDs only; the stored
copy is always a clean re-encode (JPEG RGB), never the original bytes.
"""

from __future__ import annotations

import hashlib
import io
import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from PIL import Image as PILImage
from PIL import ImageOps

logger = logging.getLogger("cropmind.uploads")

JPEG_MAGIC = b"\xff\xd8\xff"
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
WEBP_MAGIC = b"RIFF"  # + "WEBP" at offset 8
TIFF_MAGICS = (b"II*\x00", b"MM\x00*")

_MAGIC_TO_MIME = {
    "jpeg": "image/jpeg",
    "png": "image/png",
    "webp": "image/webp",
    "tiff": "image/tiff",
}


class UploadRejected(Exception):
    """Client-visible rejection; .code maps to an HTTP status."""

    def __init__(self, code: int, detail: str):
        super().__init__(detail)
        self.code, self.detail = code, detail


@dataclass
class StoredUpload:
    image_id: str
    sha256: str
    path: str  # repo/storage-relative normalized copy
    thumb_path: str
    width: int
    height: int
    byte_size: int
    captured_at: datetime | None
    exif_json: dict | None
    deduplicated: bool = False
    warnings: list[str] = field(default_factory=list)


def sniff_image_type(header: bytes) -> str | None:
    """Content identity from magic bytes; extensions/content-types are never trusted."""
    if header.startswith(JPEG_MAGIC):
        return "jpeg"
    if header.startswith(PNG_MAGIC):
        return "png"
    if header.startswith(WEBP_MAGIC) and header[8:12] == b"WEBP":
        return "webp"
    if any(header.startswith(m) for m in TIFF_MAGICS):
        return "tiff"
    return None


def _exif_summary(img: PILImage.Image) -> tuple[datetime | None, dict | None]:
    """Keep only meaningful, safe EXIF fields (capture time + GPS when present)."""
    try:
        exif = img.getexif()
    except Exception:  # noqa: BLE001 — broken EXIF must not reject a valid image
        return None, {"note": "unreadable EXIF stripped on re-encode"}
    if not exif:
        return None, None
    summary: dict = {}
    captured = None
    raw_dt = exif.get(36867) or exif.get(306)  # DateTimeOriginal / DateTime
    if isinstance(raw_dt, str):
        summary["datetime_original"] = raw_dt
        try:
            captured = datetime.strptime(raw_dt, "%Y:%m:%d %H:%M:%S").replace(tzinfo=UTC)
        except ValueError:
            summary["datetime_original_parse_note"] = "non-standard"
    gps = exif.get_ifd(34853) if 34853 in exif else None
    if gps:
        summary["gps_present"] = True  # coordinates intentionally not duplicated; re-encode strips them
    return captured, summary or None


def store_upload(
    data: bytes,
    *,
    declared_content_type: str | None,
    upload_dir: Path,
    max_bytes: int,
    max_side: int,
    thumb_side: int,
) -> StoredUpload:
    """Validate → normalize → persist one image. Raises UploadRejected for client faults."""
    if len(data) == 0:
        raise UploadRejected(400, "empty upload")
    if len(data) > max_bytes:
        raise UploadRejected(413, f"image exceeds the {max_bytes // (1024 * 1024)} MB limit")

    sniffed = sniff_image_type(data[:16])
    if sniffed is None:
        raise UploadRejected(415, "not a recognized image (JPEG/PNG/WebP/TIFF magic bytes required)")
    expected = _MAGIC_TO_MIME[sniffed]
    if declared_content_type and declared_content_type != expected:
        # Honesty over convenience: a mismatched declaration usually means a renamed file.
        logger.info("content-type mismatch: declared %s, magic says %s", declared_content_type, expected)
        raise UploadRejected(400, f"declared {declared_content_type} but content is {expected}")

    try:
        probe = PILImage.open(io.BytesIO(data))
        probe.verify()
        img = PILImage.open(io.BytesIO(data))  # verify() detaches the decoder; reopen fresh
        img.load()
    except Exception as exc:
        raise UploadRejected(400, f"corrupt or unsupported image payload: {exc.__class__.__name__}") from exc

    captured_at, exif_json = _exif_summary(img)
    img = ImageOps.exif_transpose(img)  # orientation honesty: stored copy is upright
    if img.mode != "RGB":
        img = img.convert("RGB")

    if max(img.size) > max_side:
        img = ImageOps.contain(img, (max_side, max_side))
    thumb = ImageOps.contain(img.copy(), (thumb_side, thumb_side))

    image_id = str(uuid.uuid4())
    sha256 = hashlib.sha256(data).hexdigest()
    rel = Path(sha256[:2]) / f"{image_id}.jpg"
    target = Path(upload_dir) / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    img.save(target, "JPEG", quality=88, optimize=True)
    thumb_rel = Path(sha256[:2]) / f"{image_id}_thumb.jpg"
    thumb_target = Path(upload_dir) / thumb_rel
    thumb.save(thumb_target, "JPEG", quality=82, optimize=True)

    return StoredUpload(
        image_id=image_id,
        sha256=sha256,
        path=str(rel).replace("\\", "/"),
        thumb_path=str(thumb_rel).replace("\\", "/"),
        width=int(img.size[0]),
        height=int(img.size[1]),
        byte_size=int(target.stat().st_size),
        captured_at=captured_at,
        exif_json=exif_json,
        warnings=[],
    )
