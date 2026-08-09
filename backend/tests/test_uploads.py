"""Upload-pipeline tests: magic-byte sniffing, validation rejections, re-encode
normalization, sha256 dedupe — unit level plus the /images API surface."""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from PIL import Image as PILImage

from app.services.uploads import UploadRejected, sniff_image_type, store_upload


def _jpeg_bytes(size: tuple[int, int] = (64, 48), color=(20, 160, 60), fmt: str = "JPEG") -> bytes:
    buf = io.BytesIO()
    PILImage.new("RGB", size, color).save(buf, fmt)
    return buf.getvalue()


# ── sniff_image_type ──────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        (b"\xff\xd8\xff\xe0JFIF", "jpeg"),
        (b"\x89PNG\r\n\x1a\nrest", "png"),
        (b"RIFF\x00\x00\x00\x00WEBP", "webp"),
        (b"II*\x00more", "tiff"),
        (b"MM\x00*more", "tiff"),
        (b"RIFF\x00\x00\x00\x00WAVE", None),  # RIFF but not WebP
        (b"not-an-image", None),
        (b"\xff\xd8", None),  # truncated jpeg signature
        (b"", None),
    ],
)
def test_sniff_matrix(header: bytes, expected: str | None) -> None:
    assert sniff_image_type(header) == expected


# ── store_upload unit behaviour ───────────────────────────────────────────────


def test_store_upload_happy_path(tmp_path) -> None:
    stored = store_upload(
        _jpeg_bytes((4000, 1000)),  # longest edge above max_side → downscaled 4:1
        declared_content_type="image/jpeg",
        upload_dir=tmp_path,
        max_bytes=25 * 1024 * 1024,
        max_side=2048,
        thumb_side=384,
    )
    assert stored.width == 2048 and stored.height == 512  # aspect preserved, capped at max_side
    copy = Path(tmp_path, stored.path)
    thumb = Path(tmp_path, stored.thumb_path)
    assert copy.is_file() and thumb.is_file()
    assert copy.read_bytes()[:3] == b"\xff\xd8\xff"  # stored copy is a clean JPEG re-encode
    with PILImage.open(thumb) as t:
        assert max(t.size) <= 384
    assert stored.sha256 and stored.byte_size == copy.stat().st_size


def test_store_upload_rejects_oversize(tmp_path) -> None:
    with pytest.raises(UploadRejected) as exc:
        store_upload(_jpeg_bytes(), declared_content_type=None, upload_dir=tmp_path, max_bytes=10, max_side=64, thumb_side=16)
    assert exc.value.code == 413


def test_store_upload_rejects_unknown_bytes(tmp_path) -> None:
    with pytest.raises(UploadRejected) as exc:
        store_upload(
            b"MZ\x90\x00executable", declared_content_type="image/jpeg",
            upload_dir=tmp_path, max_bytes=1024, max_side=64, thumb_side=16,
        )
    assert exc.value.code == 415


def test_store_upload_rejects_declared_content_mismatch(tmp_path) -> None:
    # A renamed file: declared .jpeg but actually PNG content → 400, honesty over convenience.
    with pytest.raises(UploadRejected) as exc:
        store_upload(
            _jpeg_bytes(fmt="PNG"), declared_content_type="image/jpeg",
            upload_dir=tmp_path, max_bytes=1024, max_side=64, thumb_side=16,
        )
    assert exc.value.code == 400 and "image/png" in exc.value.detail


def test_store_upload_rejects_corrupt_payload(tmp_path) -> None:
    with pytest.raises(UploadRejected) as exc:
        store_upload(
            b"\xff\xd8\xff\xe0" + b"garbage-not-a-jpeg", declared_content_type=None,
            upload_dir=tmp_path, max_bytes=1024, max_side=64, thumb_side=16,
        )
    assert exc.value.code == 400


def test_store_upload_empty_rejected(tmp_path) -> None:
    with pytest.raises(UploadRejected) as exc:
        store_upload(b"", declared_content_type=None, upload_dir=tmp_path, max_bytes=10, max_side=64, thumb_side=16)
    assert exc.value.code == 400


# ── /images API ───────────────────────────────────────────────────────────────


def _upload_file():
    return {"file": ("leaf.jpg", _jpeg_bytes(), "image/jpeg")}


def test_post_images_creates_record_and_files(client, tmp_path) -> None:
    resp = client.post("/images", files=_upload_file())
    assert resp.status_code == 201, resp.text
    payload = resp.json()["image"]
    assert payload["deduplicated"] is False
    assert payload["width"] == 64 and payload["height"] == 48
    assert payload["source_type"] == "SMARTPHONE"
    upload_dir = Path(tmp_path / "uploads")
    assert len(list(upload_dir.rglob("*.jpg"))) == 2  # normalized copy + thumbnail

    got = client.get(f"/images/{payload['id']}")
    assert got.status_code == 200 and got.json()["image"]["id"] == payload["id"]

    dl = client.get(f"/images/{payload['id']}/download")
    assert dl.status_code == 200 and dl.content[:3] == b"\xff\xd8\xff"
    th = client.get(f"/images/{payload['id']}/download", params={"thumb": True})
    assert th.status_code == 200 and "-thumb" in th.headers["content-disposition"]


def test_post_same_bytes_deduplicates(client, tmp_path) -> None:
    first = client.post("/images", files=_upload_file()).json()["image"]
    second = client.post("/images", files=_upload_file()).json()["image"]
    assert second["id"] == first["id"]
    assert second["deduplicated"] is True
    upload_dir = Path(tmp_path / "uploads")
    assert len(list(upload_dir.rglob("*.jpg"))) == 2  # the stray re-encode was removed


def test_post_images_rejects_wrong_content(client) -> None:
    resp = client.post("/images", files={"file": ("leaf.png", _jpeg_bytes(fmt="PNG"), "image/jpeg")})
    assert resp.status_code == 400 and "image/png" in resp.json()["detail"]

    resp = client.post("/images", files={"file": ("evil.jpg", b"MZ\x90\x00exe", "image/jpeg")})
    assert resp.status_code == 415

    resp = client.post("/images", files={"file": ("bad.jpg", b"\xff\xd8\xff\xe0junk", "image/jpeg")})
    assert resp.status_code == 400


def test_get_image_unknown_404(client) -> None:
    assert client.get("/images/nope").status_code == 404
    assert client.get("/images/nope/download").status_code == 404
