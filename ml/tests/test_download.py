import json
from dataclasses import replace

import pytest

from ml.data import download, registry
from ml.data.download import DownloadError, LicenseNotAcceptedError


def test_license_gate_blocks_download_without_acceptance(tmp_path, monkeypatch):
    def _boom(*args, **kwargs):  # network must never be touched without consent
        raise AssertionError("network should not be called")

    monkeypatch.setattr(download, "_fetch", _boom)
    with pytest.raises(LicenseNotAcceptedError):
        download.download_dataset("plantdoc", tmp_path, accept_license=False)


def test_auto_blocked_dataset_refuses_fast_with_manual_guidance(tmp_path, monkeypatch):
    def _boom(*args, **kwargs):
        raise AssertionError("network must not be attempted for an AUTO_BLOCKED dataset")

    monkeypatch.setattr(download, "_fetch", _boom)
    with pytest.raises(DownloadError) as excinfo:
        download.download_dataset("plantvillage", tmp_path, accept_license=True)

    message = str(excinfo.value)
    assert "cannot be downloaded programmatically" in message
    assert "HTTP 403" in message
    assert "https://data.mendeley.com/datasets/tywbtsjrjv/1" in message
    assert "import --dataset plantvillage" in message


def test_403_fail_fast_never_tries_remaining_candidates(tmp_path, monkeypatch):
    calls = []

    def _raise_403(url, dest, **kwargs):
        calls.append(url)
        raise download.DownloadForbiddenError(f"HTTP 403 from {url}")

    two_candidates = replace(
        registry.PLANTDOC, candidates=("https://example.invalid/a.zip", "https://example.invalid/b.zip")
    )
    monkeypatch.setitem(registry.REGISTRY, "plantdoc", two_candidates)
    monkeypatch.setattr(download, "_fetch", _raise_403)

    with pytest.raises(DownloadError) as excinfo:
        download.download_dataset("plantdoc", tmp_path, accept_license=True)

    assert calls == ["https://example.invalid/a.zip"]  # stopped after first forbidden response
    assert "rejected automated download" in str(excinfo.value)


def test_full_download_flow_plantdoc(tmp_path, monkeypatch, toy_plantdoc_zip):
    archive = toy_plantdoc_zip

    def _fake_fetch(url, dest, **kwargs):
        dest.write_bytes(archive.read_bytes())
        return archive.stat().st_size

    monkeypatch.setattr(download, "_fetch", _fake_fetch)
    images_root = download.download_dataset("plantdoc", tmp_path / "raw", accept_license=True)

    prov = json.loads((tmp_path / "raw" / "plantdoc" / "PROVENANCE.json").read_text())
    assert prov["license_id"] == "CC-BY-4.0"
    assert prov["acquisition"]["method"] == "auto-download"
    assert len(prov["acquisition"]["archive_sha256"]) == 64
    assert prov["image_count"] == 5
    assert set(prov["class_dirs"]) == {"Tomato Early blight leaf", "Apple leaf"}
    assert (images_root / "Tomato Early blight leaf").is_dir()


def test_corrupt_download_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(download, "_fetch", lambda url, dest, **kw: dest.write_bytes(b"not a zip"))
    with pytest.raises(DownloadError):
        download.download_dataset("plantdoc", tmp_path / "raw", accept_license=True)


def test_safe_extract_blocks_path_traversal(tmp_path):
    import zipfile

    evil = tmp_path / "evil.zip"
    with zipfile.ZipFile(evil, "w") as zf:
        zf.writestr("../../escape.txt", "owned")
    with pytest.raises(DownloadError):
        download.safe_extract(evil, tmp_path / "out")
