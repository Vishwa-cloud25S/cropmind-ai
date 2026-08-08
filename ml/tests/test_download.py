import json
import logging
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


# ---------------- safe extraction (Windows failure 2026-08-08, manual extractor) ----------------
import zipfile


def _make_zip(path, members: dict[str, bytes], dirs=()):
    with zipfile.ZipFile(path, "w") as zf:
        for dirname in dirs:
            zf.writestr(dirname.rstrip("/") + "/", "")
        for name, data in members.items():
            zf.writestr(name, data)
    return path


def test_safe_extract_nested_dirs_and_long_member(tmp_path):
    """PlantDoc-style deep tree + >260-char final path: parents created, bytes exact."""
    long_name = "apple-tree-" + "branch-" * 25 + "928225.jpg"
    member = f"master/train/Apple leaf/{long_name}"
    archive = _make_zip(
        tmp_path / "plantdoc.zip",
        {member: b"jpeg-bytes", "master/train/Corn leaf/c.jpg": b"c"},
        dirs=("master/train/Apple leaf/", "master/train/Corn leaf/"),
    )
    dest = tmp_path / "deep" / "more" / "extracted"
    download.safe_extract(archive, dest)
    target = dest / "master" / "train" / "Apple leaf" / long_name
    assert len(str(target)) > 260
    assert target.read_bytes() == b"jpeg-bytes"
    assert (dest / "master" / "train" / "Corn leaf" / "c.jpg").read_bytes() == b"c"
    assert (dest / download.EXTRACTION_MARKER).exists()


@pytest.mark.parametrize(
    "bad_name",
    ["../evil.txt", "/abs.txt", "\\abs.txt", "a/../b.txt", "..\\evil.txt", "C:/evil.txt", "D:\\evil.txt"],
)
def test_safe_extract_rejects_zip_slip_members(tmp_path, bad_name):
    archive = _make_zip(tmp_path / "evil.zip", {bad_name: b"pwn", "ok/good.txt": b"g"})
    dest = tmp_path / "out"
    with pytest.raises(DownloadError) as excinfo:
        download.safe_extract(archive, dest)
    assert archive.name in str(excinfo.value)
    assert not (dest / download.EXTRACTION_MARKER).exists()  # aborted tree is NOT marked complete
    for stray in dest.rglob("*") if dest.exists() else []:
        assert "evil" not in stray.name


def test_safe_extract_member_error_mentions_archive_member_target(tmp_path, monkeypatch):
    archive = _make_zip(tmp_path / "some-name.zip", {"a/b/c.jpg": b"data"})
    monkeypatch.setattr(
        download.shutil, "copyfileobj", lambda *_: (_ for _ in ()).throw(OSError("disk full"))
    )
    with pytest.raises(DownloadError) as excinfo:
        download.safe_extract(archive, tmp_path / "out")
    message = str(excinfo.value)
    assert "some-name.zip" in message
    assert "a/b/c.jpg" in message
    assert "disk full" in message
    assert "to" in message


def test_extraction_root_marker_idempotency_and_self_heal(tmp_path):
    archive = _make_zip(tmp_path / "data.zip", {"k/f1.jpg": b"1", "k/f2.jpg": b"2"})
    dataset_dir = tmp_path / "plantdoc"
    dataset_dir.mkdir()

    first, renames = download._extraction_root(dataset_dir, archive)
    assert renames == []  # clean names → nothing renamed
    assert (first / download.EXTRACTION_MARKER).exists()
    snapshot = {p.name: p.read_bytes() for p in first.rglob("*.jpg")}

    second, reuse_renames = download._extraction_root(dataset_dir, archive)  # complete tree → reused
    assert reuse_renames == []
    assert second == first
    assert {p.name: p.read_bytes() for p in second.rglob("*.jpg")} == snapshot

    # Partial/crashed tree (file removed, marker removed) must self-heal, not be "reused".
    (first / "k" / "f2.jpg").unlink()
    (first / download.EXTRACTION_MARKER).unlink()
    healed, _ = download._extraction_root(dataset_dir, archive)
    assert (healed / "k" / "f2.jpg").read_bytes() == b"2"
    assert (healed / download.EXTRACTION_MARKER).exists()


def test_safe_extract_deterministic_repeated_bytes(tmp_path):
    members = {f"d/f{i}.jpg": bytes([i]) * 64 for i in range(5)}
    archive = _make_zip(tmp_path / "d.zip", members)
    download.safe_extract(archive, tmp_path / "one")
    download.safe_extract(archive, tmp_path / "two")
    for name in members:
        assert (tmp_path / "one" / name).read_bytes() == (tmp_path / "two" / name).read_bytes()


# --- Filesystem-safety sanitization (Windows-illegal member names, PlantDoc reality) ---


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("IMG_1629.JPG?1507122477.jpg", "IMG_1629.JPG_1507122477.jpg"),  # real PlantDoc member
        ("Bell_pepper leaf", "Bell_pepper leaf"),  # inner spaces are legal — untouched
        ("a<b>z", "a_b_z"),
        ('x|y"z', "x_y_z"),
        ("trailing.", "trailing"),
        ("trailing  ", "trailing"),
        ("...", "_"),
        ("CON", "_CON"),
        ("con.txt", "_con.txt"),
        ("lpt3.jpg", "_lpt3.jpg"),
        ("normal_name-1.JPG", "normal_name-1.JPG"),  # identity for already-safe names
    ],
)
def test_sanitize_segment_deterministic(raw: str, expected: str) -> None:
    assert download.sanitize_segment(raw) == expected
    assert download.sanitize_segment(expected) == expected  # idempotent — replaying is a no-op


def test_safe_extract_sanitizes_windows_illegal_names(tmp_path, caplog):
    """The real Gate C failure: PlantDoc ships members whose names contain '?' — they must
    land renamed (deterministically, identically on every OS), recorded, and marked."""
    members = {
        "PlantDoc-Dataset-master/test/Bell_pepper leaf/IMG_1629.JPG?1507122477.jpg": b"illegal-name-bytes",
        "PlantDoc-Dataset-master/test/Bell_pepper leaf/normal.JPG": b"normal",
    }
    archive = _make_zip(tmp_path / "plantdoc.zip", members)
    dest = tmp_path / "out"
    with caplog.at_level(logging.WARNING, logger="cropmind.ml.download"):
        renames = download.safe_extract(archive, dest)

    sanitized = dest / "PlantDoc-Dataset-master" / "test" / "Bell_pepper leaf" / "IMG_1629.JPG_1507122477.jpg"
    assert sanitized.read_bytes() == b"illegal-name-bytes"
    assert (dest / "PlantDoc-Dataset-master" / "test" / "Bell_pepper leaf" / "normal.JPG").exists()
    assert (dest / download.EXTRACTION_MARKER).exists()
    assert renames == [
        (
            "PlantDoc-Dataset-master/test/Bell_pepper leaf/IMG_1629.JPG?1507122477.jpg",
            "PlantDoc-Dataset-master/test/Bell_pepper leaf/IMG_1629.JPG_1507122477.jpg",
        )
    ]
    assert any("renamed for filesystem safety" in r.getMessage() for r in caplog.records)
    # Deterministic: a second destination produces the identical layout.
    renames_two = download.safe_extract(archive, tmp_path / "out2")
    assert renames_two == renames
    assert (tmp_path / "out2" / "PlantDoc-Dataset-master" / "test" / "Bell_pepper leaf" / "IMG_1629.JPG_1507122477.jpg").read_bytes() == b"illegal-name-bytes"


def test_safe_extract_sanitization_clash_deduped_not_overwritten(tmp_path):
    """Two DISTINCT members mapping to one target (via sanitization): deterministic ~2
    dedup, both contents preserved, renames recorded — never a silent overwrite."""
    # sorted order: 'a/x?y.jpg' ('?'=0x3F) precedes 'a/x_y.jpg' ('_'=0x5F)
    archive = _make_zip(tmp_path / "clash.zip", {"a/x?y.jpg": b"one", "a/x_y.jpg": b"two"})
    dest = tmp_path / "out"
    renames = download.safe_extract(archive, dest)
    assert (dest / "a" / "x_y.jpg").read_bytes() == b"one"
    assert (dest / "a" / "x_y~2.jpg").read_bytes() == b"two"
    assert (dest / download.EXTRACTION_MARKER).exists()
    assert renames == [("a/x?y.jpg", "a/x_y.jpg"), ("a/x_y.jpg", "a/x_y~2.jpg")]


def test_safe_extract_case_only_clash_deduped(tmp_path):
    """The real Gate C failure: distinct members `CAR1.jpg` / `car1.jpg` collide on a
    case-insensitive filesystem. Sorted order: 'CAR1.jpg' ('C'=0x43) precedes 'car1.jpg'."""
    archive = _make_zip(tmp_path / "case.zip", {"k/car1.jpg": b"lower", "k/CAR1.jpg": b"upper"})
    dest = tmp_path / "out"
    renames = download.safe_extract(archive, dest)
    assert (dest / "k" / "CAR1.jpg").read_bytes() == b"upper"  # first in sorted order keeps the name
    assert (dest / "k" / "car1~2.jpg").read_bytes() == b"lower"  # later member deduped deterministically
    assert renames == [("k/car1.jpg", "k/car1~2.jpg")]
    # Deterministic: a second extraction yields the identical layout.
    renames_two = download.safe_extract(archive, tmp_path / "out2")
    assert renames_two == renames
    assert (tmp_path / "out2" / "k" / "CAR1.jpg").read_bytes() == b"upper"
    assert (tmp_path / "out2" / "k" / "car1~2.jpg").read_bytes() == b"lower"


def test_safe_extract_chain_of_clashes_all_preserved(tmp_path):
    """Every member wins a unique stable target; dedup counts climb deterministically."""
    archive = _make_zip(tmp_path / "t.zip", {"d/f.jpg": b"a", "d/F.jpg": b"b", "d/f~2.jpg": b"c"})
    dest = tmp_path / "out"
    renames = download.safe_extract(archive, dest)
    # sorted order: 'd/F.jpg' < 'd/f.jpg' < 'd/f~2.jpg'
    assert (dest / "d" / "F.jpg").read_bytes() == b"b"  # first keeps the name
    assert (dest / "d" / "f~2.jpg").read_bytes() == b"a"  # f.jpg deduped onto f~2 first...
    assert (dest / "d" / "f~2~2.jpg").read_bytes() == b"c"  # ...so the literal f~2 member bumps again
    assert renames == [("d/f.jpg", "d/f~2.jpg"), ("d/f~2.jpg", "d/f~2~2.jpg")]


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("k/CON", "k/_CON"), ("k/name.", "k/name"), ("k/aux.txt", "k/_aux.txt")],
)
def test_safe_extract_reserved_and_trailing_segments(tmp_path, raw: str, expected: str) -> None:
    archive = _make_zip(tmp_path / "r.zip", {raw: b"x"})
    download.safe_extract(archive, tmp_path / "out")
    assert (tmp_path / "out" / expected).read_bytes() == b"x"


def test_renamed_members_block_provenance_record() -> None:
    assert download._renamed_members_block([]) == {}
    renames = [("a/b?x.jpg", "a/b_x.jpg"), ("d/c:2.jpg", "d/c_2.jpg")]
    block = download._renamed_members_block(renames)
    assert block["extraction"]["renamed_count"] == 2
    assert block["extraction"]["renamed_examples"][0] == {"member": "a/b?x.jpg", "written_as": "a/b_x.jpg"}
    assert "deterministically" in block["extraction"]["policy"]
