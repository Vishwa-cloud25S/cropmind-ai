import json

import pytest

from ml.data import download
from ml.data.download import LicenseNotAcceptedError


def test_license_gate_blocks_download_without_acceptance(tmp_path, monkeypatch):
    def _boom(*args, **kwargs):  # network must never be touched without consent
        raise AssertionError("network should not be called")

    monkeypatch.setattr(download, "_fetch", _boom)
    with pytest.raises(LicenseNotAcceptedError):
        download.download_dataset("plantvillage", tmp_path, accept_license=False)


def test_full_download_flow_with_nested_without_augmentation(tmp_path, monkeypatch, toy_zip):
    archive = toy_zip

    def _fake_fetch(url, dest, **kwargs):
        dest.write_bytes(archive.read_bytes())
        return archive.stat().st_size

    monkeypatch.setattr(download, "_fetch", _fake_fetch)
    images_root = download.download_dataset("plantvillage", tmp_path / "raw", accept_license=True)

    prov = json.loads((tmp_path / "raw" / "plantvillage" / "PROVENANCE.json").read_text())
    assert prov["license_id"] == "CC0-1.0"
    assert len(prov["archive_sha256"]) == 64
    assert prov["image_count"] == 5
    assert (images_root / "Tomato_early_blight").is_dir()

    # class dirs detected through the nested "without augmentation" zip
    assert set(prov["class_dirs"]) == {"Tomato_early_blight", "Apple_healthy"}


def test_corrupt_download_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(download, "_fetch", lambda url, dest, **kw: dest.write_bytes(b"not a zip"))
    with pytest.raises(download.DownloadError):
        download.download_dataset("plantdoc", tmp_path / "raw", accept_license=True)


def test_safe_extract_blocks_path_traversal(tmp_path):
    import zipfile

    evil = tmp_path / "evil.zip"
    with zipfile.ZipFile(evil, "w") as zf:
        zf.writestr("../../escape.txt", "owned")
    with pytest.raises(download.DownloadError):
        download.safe_extract(evil, tmp_path / "out")
