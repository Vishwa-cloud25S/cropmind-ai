"""Manual acquisition route tests: small fixtures only, no real dataset."""

import json
from dataclasses import replace

import pytest

from ml.data import download, registry, split, verify
from ml.data.download import DownloadError, LicenseNotAcceptedError


@pytest.fixture()
def lax_plantvillage_threshold(monkeypatch):
    """Toy fixtures have 2 mapped class dirs; the real gate wants >= 20."""
    monkeypatch.setitem(
        registry.REGISTRY,
        "plantvillage",
        replace(registry.PLANTVILLAGE, expected_min_mapped_class_dirs=2),
    )


def _prov(tmp_path):
    return json.loads((tmp_path / "raw" / "plantvillage" / "PROVENANCE.json").read_text())


def test_import_from_archive_writes_full_provenance(tmp_path, toy_zip, lax_plantvillage_threshold):
    images_root = download.import_dataset(
        "plantvillage", tmp_path / "raw", archive=toy_zip, accept_license=True
    )
    prov = _prov(tmp_path)

    assert verify.verify_provenance(tmp_path / "raw" / "plantvillage" / "PROVENANCE.json") == []
    assert prov["acquisition"]["method"] == "manual-archive"
    assert prov["acquisition"]["source_basename"] == toy_zip.name
    assert len(prov["acquisition"]["archive_sha256"]) == 64
    assert prov["doi"] == "10.17632/tywbtsjrjv.1"
    assert "Mendeley" in prov["citation"]
    assert prov["license_id"] == "CC0-1.0"
    assert prov["image_count"] == 5
    assert not prov["images_root_absolute"]
    assert (images_root / "Tomato_early_blight").is_dir()


def test_import_prefers_without_augmentation_nested_archive(tmp_path, toy_zip, lax_plantvillage_threshold):
    images_root = download.import_dataset(
        "plantvillage", tmp_path / "raw", archive=toy_zip, accept_license=True
    )
    assert "without_augmentation" in str(images_root)


def test_import_from_directory_registers_in_place(tmp_path, toy_images_root, lax_plantvillage_threshold):
    resolved = download.import_dataset(
        "plantvillage", tmp_path / "raw", directory=toy_images_root, accept_license=True
    )
    prov = _prov(tmp_path)

    assert resolved == toy_images_root
    assert prov["acquisition"]["method"] == "manual-directory"
    assert prov["acquisition"]["archive_sha256"] is None
    assert prov["acquisition"]["sha256_note"]
    assert prov["images_root"] == str(toy_images_root)
    dataset_dir = tmp_path / "raw" / "plantvillage"
    assert (dataset_dir / "PROVENANCE.json").exists()
    assert not (dataset_dir / "extracted").exists()  # nothing copied
    assert len(list((toy_images_root / "Tomato_early_blight").glob("*.jpg"))) == 12  # untouched


def test_import_structure_gate_refuses_junk_dir(tmp_path):
    junk = tmp_path / "junk"
    (junk / "random_photos").mkdir(parents=True)
    (junk / "more_stuff").mkdir()

    problems, _ = verify.verify_dataset_structure(junk, "plantvillage")
    assert problems  # default threshold is 20 mapped dirs

    # mappable class folders present but empty -> reaches the structure gate, which must fail
    hollow = tmp_path / "hollow"
    (hollow / "Tomato_early_blight").mkdir(parents=True)
    (hollow / "Apple_healthy").mkdir()
    problems, _ = verify.verify_dataset_structure(hollow, "plantvillage")
    assert any("no images" in p for p in problems) or any("mappable" in p for p in problems)

    with pytest.raises(DownloadError, match="structure verification failed"):
        download.import_dataset("plantvillage", tmp_path / "raw", directory=hollow, accept_license=True)


def test_import_requires_license_confirmation(tmp_path, toy_zip):
    with pytest.raises(LicenseNotAcceptedError):
        download.import_dataset("plantvillage", tmp_path / "raw", archive=toy_zip, accept_license=False)


def test_import_requires_exactly_one_source(tmp_path, toy_zip):
    with pytest.raises(ValueError):
        download.import_dataset("plantvillage", tmp_path / "raw", accept_license=True)
    with pytest.raises(ValueError):
        download.import_dataset(
            "plantvillage", tmp_path / "raw", archive=toy_zip, directory=tmp_path, accept_license=True
        )


def test_split_after_import_e2e(tmp_path, toy_zip, lax_plantvillage_threshold):
    images_root = download.import_dataset(
        "plantvillage", tmp_path / "raw", archive=toy_zip, accept_license=True
    )
    out_dir = tmp_path / "splits" / "plantvillage" / "v1"
    manifest = split.split_dataset(images_root, out_dir, "plantvillage", seed=7)

    assert verify.verify_splits(out_dir) == []
    total = sum(manifest["splits"][name]["count"] for name in ("train", "val", "test"))
    assert total == 5
    assert set(manifest["splits"]["train"]["classes"]) <= {"tomato_early_blight", "apple_healthy"}


def test_manual_guidance_message_contents():
    message = download.manual_route_guidance(registry.PLANTVILLAGE)
    assert "HTTP 403" in message
    assert "https://data.mendeley.com/datasets/tywbtsjrjv/1" in message
    assert "import --dataset plantvillage" in message
    assert "unofficial scraped copies" in message
