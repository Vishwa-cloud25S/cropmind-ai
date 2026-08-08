import json

import pytest

from ml.data import split, stats, verify


@pytest.fixture()
def manifest(tmp_path, toy_images_root):
    out_dir = tmp_path / "splits" / "plantvillage" / "v1"
    return split.split_dataset(toy_images_root, out_dir, "plantvillage", seed=7), out_dir


def test_split_is_deterministic_for_same_seed(tmp_path, toy_images_root):
    m1 = split.split_dataset(toy_images_root, tmp_path / "a", "plantvillage", seed=7)
    m2 = split.split_dataset(toy_images_root, tmp_path / "b", "plantvillage", seed=7)
    assert m1["content_sha256"] == m2["content_sha256"]
    assert m1["splits"] == m2["splits"]


def test_split_changes_with_different_seed(tmp_path, toy_images_root):
    m1 = split.split_dataset(toy_images_root, tmp_path / "a", "plantvillage", seed=7)
    m2 = split.split_dataset(toy_images_root, tmp_path / "b", "plantvillage", seed=99)
    assert m1["content_sha256"] != m2["content_sha256"]


def test_stratification_and_totals(tmp_path, toy_images_root, manifest):
    m, _ = manifest
    classes = m["splits"]["train"]["classes"]
    assert set(classes) == {"tomato_early_blight", "potato_early_blight"}
    totals = {name: m["splits"][name]["count"] for name in ("train", "val", "test")}
    assert sum(totals.values()) == 20  # 12 + 8 usable images
    for name in ("train", "val", "test"):
        assert set(m["splits"][name]["classes"]) == {"tomato_early_blight", "potato_early_blight"}


def test_skipped_classes_are_recorded(tmp_path, toy_images_root, manifest):
    m, _ = manifest
    assert m["skipped"]["excluded"] == {"Background_without_leaves": 3}
    assert m["skipped"]["unmapped"] == {"Bell_pepper leaf": 4}


def test_verify_passes_on_fresh_split(manifest):
    _, out_dir = manifest
    assert verify.verify_splits(out_dir) == []


def test_verify_detects_leakage(manifest):
    _, out_dir = manifest
    (out_dir / "val.txt").write_text(
        (out_dir / "val.txt").read_text() + (out_dir / "train.txt").read_text().splitlines()[0] + "\n",
        encoding="utf-8",
    )
    problems = verify.verify_splits(out_dir)
    assert any("LEAKAGE" in p for p in problems)


def test_verify_provenance_required_keys(tmp_path):
    prov = {"dataset": "plantvillage", "license_id": "CC0-1.0"}
    path = tmp_path / "PROVENANCE.json"
    path.write_text(json.dumps(prov))
    problems = verify.verify_provenance(path)
    assert "provenance missing key: page_url" in problems
    assert "provenance missing key: downloaded_utc" in problems


def test_stats_generates_markdown_and_csv(manifest, tmp_path):
    _, out_dir = manifest
    summary = stats.generate_stats(out_dir, tmp_path / "reports")
    assert summary["grand_total"] == 20
    md = (tmp_path / "reports" / "plantvillage-stats.md").read_text()
    assert "| tomato_early_blight |" in md
    assert (tmp_path / "reports" / "plantvillage-stats.csv").exists()
