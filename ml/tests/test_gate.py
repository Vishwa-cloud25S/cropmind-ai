"""Tests for ml/evaluation/gate.py — Gate C precondition validation (runbook Step 2).

Every structure is built synthetically under tmp_path: no real datasets, no real
checkpoints beyond tiny torch saves. The validator must fail loudly on each broken
condition and must NEVER fabricate, copy, or overwrite anything.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
import torch

from ml.evaluation import gate

DATASET = "plantvillage"
VERSION = "v1"
CONTENT_SHA = hashlib.sha256(b"synthetic split content").hexdigest()
ARCHIVE_BYTES = b"synthetic plantvillage archive bytes"
ARCHIVE_SHA = hashlib.sha256(ARCHIVE_BYTES).hexdigest()
# A well-formed but arbitrary recorded checkpoint hash (stands in for the pre-embedding
# save hash that train.py writes — the byte hash of the final file will differ, and that
# is expected per the documented save protocol).
RECORDED_CKPT_SHA = hashlib.sha256(b"pre-embedding serialization").hexdigest()


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _make_tree(
    tmp_path: Path,
    *,
    embedded_sha: str | None = RECORDED_CKPT_SHA,
    recorded_sha: str | None = RECORDED_CKPT_SHA,
    metrics_dataset: str = f"{DATASET}@{VERSION}",
    metrics_sha: str = CONTENT_SHA,
    manifest_version: str = VERSION,
    manifest_at_version: str = VERSION,
    manifest_sha: str = CONTENT_SHA,
    provenance_dataset: str = DATASET,
    provenance_sha: str | None = ARCHIVE_SHA,
    artifacts: tuple[str, ...] = gate.RUN_ARTIFACTS,
) -> tuple[Path, Path, Path]:
    """Build run dir + data root + downloads dir; return (run_dir, data_root, downloads)."""
    run_dir = tmp_path / "runs" / "run-test"
    data_root = tmp_path / "data"
    downloads = tmp_path / "Downloads"
    run_dir.mkdir(parents=True)
    downloads.mkdir(parents=True)

    if "checkpoint.pt" in artifacts:
        meta = {} if embedded_sha is None else {"checkpoint_sha256": embedded_sha}
        torch.save({"state_dict": {"w": torch.zeros(2)}, "meta": meta}, run_dir / "checkpoint.pt")
    if "checkpoint.sha256" in artifacts:
        text = "" if recorded_sha is None else recorded_sha + "\n"
        (run_dir / "checkpoint.sha256").write_text(text, encoding="utf-8")
    if "metrics.json" in artifacts:
        _write_json(
            run_dir / "metrics.json",
            {"run_id": "run-test", "dataset": metrics_dataset, "splits_content_sha256": metrics_sha},
        )
    if "config.yaml" in artifacts:
        (run_dir / "config.yaml").write_text("data:\n  dataset: plantvillage\n", encoding="utf-8")

    acquisition = {}
    if provenance_sha is not None:
        acquisition = {"method": "manual-archive", "archive_sha256": provenance_sha}
    _write_json(
        data_root / "raw" / DATASET / "PROVENANCE.json",
        {"dataset": provenance_dataset, "version": "mendeley-v1", "acquisition": acquisition},
    )
    _write_json(
        data_root / "splits" / DATASET / manifest_at_version / "split_manifest.json",
        {"dataset": DATASET, "version": manifest_version, "content_sha256": manifest_sha},
    )
    return run_dir, data_root, downloads


def _run(run_dir: Path, data_root: Path, downloads: Path, **kwargs) -> list[gate.Check]:
    return gate.run_gate_checks(
        run_dir=run_dir, dataset=DATASET, data_root=data_root, downloads_dir=downloads, **kwargs
    )


def _statuses(checks: list[gate.Check]) -> dict[str, str]:
    return {c.name: c.status for c in checks}


def test_happy_path_no_archive(tmp_path: Path) -> None:
    run_dir, data_root, downloads = _make_tree(tmp_path)
    checks = _run(run_dir, data_root, downloads)
    statuses = _statuses(checks)
    assert gate.gate_passed(checks)
    assert statuses["run-artifacts"] == "OK"
    assert statuses["metrics"] == "OK"
    assert statuses["dataset-identity"] == "OK"
    assert statuses["dataset-provenance"] == "OK"
    assert statuses["split-manifest"] == "OK"
    assert statuses["checkpoint-embedded-hash"] == "OK"
    assert statuses["archive-integrity"] == "SKIP"


def test_no_hardcoded_values(tmp_path: Path) -> None:
    """A different arbitrary manifest sha drives the check — nothing is hardcoded."""
    other = hashlib.sha256(b"some other split content").hexdigest()
    run_dir, data_root, downloads = _make_tree(tmp_path, metrics_sha=other, manifest_sha=other)
    assert gate.gate_passed(_run(run_dir, data_root, downloads))


@pytest.mark.parametrize("missing", ["checkpoint.pt", "checkpoint.sha256", "metrics.json", "config.yaml"])
def test_missing_run_artifact_fails(tmp_path: Path, missing: str) -> None:
    artifacts = tuple(a for a in gate.RUN_ARTIFACTS if a != missing)
    run_dir, data_root, downloads = _make_tree(tmp_path, artifacts=artifacts)
    checks = _run(run_dir, data_root, downloads)
    artifacts_check = next(c for c in checks if c.name == "run-artifacts")
    assert artifacts_check.status == "FAIL"
    assert missing in artifacts_check.detail
    assert not gate.gate_passed(checks)


def test_run_dir_missing_fails(tmp_path: Path) -> None:
    checks = _run(tmp_path / "runs" / "nope", tmp_path / "data", tmp_path / "Downloads")
    assert _statuses(checks)["run-artifacts"] == "FAIL"


def test_metrics_malformed_fails(tmp_path: Path) -> None:
    run_dir, data_root, downloads = _make_tree(tmp_path)
    (run_dir / "metrics.json").write_text("{not json", encoding="utf-8")
    checks = _run(run_dir, data_root, downloads)
    assert _statuses(checks)["metrics"] == "FAIL"
    assert not gate.gate_passed(checks)


def test_wrong_dataset_in_metrics_fails(tmp_path: Path) -> None:
    run_dir, data_root, downloads = _make_tree(tmp_path, metrics_dataset="plantdoc@v1")
    checks = _run(run_dir, data_root, downloads)
    check = next(c for c in checks if c.name == "dataset-identity")
    assert check.status == "FAIL"
    assert "wrong dataset" in check.detail


def test_version_mismatch_metrics_vs_manifest_fails(tmp_path: Path) -> None:
    # metrics claims v2; a manifest exists at v2 but declares version v1 -> mismatch.
    run_dir, data_root, downloads = _make_tree(
        tmp_path, metrics_dataset=f"{DATASET}@v2", manifest_at_version="v2", manifest_version="v1"
    )
    checks = _run(run_dir, data_root, downloads)
    assert _statuses(checks)["split-manifest"] == "FAIL"


def test_split_content_sha_mismatch_fails(tmp_path: Path) -> None:
    different = hashlib.sha256(b"regenerated split").hexdigest()
    run_dir, data_root, downloads = _make_tree(tmp_path, manifest_sha=different)
    checks = _run(run_dir, data_root, downloads)
    check = next(c for c in checks if c.name == "split-manifest")
    assert check.status == "FAIL"
    assert "did not train on the split currently on disk" in check.detail


def test_provenance_missing_fails(tmp_path: Path) -> None:
    run_dir, data_root, downloads = _make_tree(tmp_path)
    (data_root / "raw" / DATASET / "PROVENANCE.json").unlink()
    checks = _run(run_dir, data_root, downloads)
    assert _statuses(checks)["dataset-provenance"] == "FAIL"
    assert not gate.gate_passed(checks)


def test_provenance_malformed_fails(tmp_path: Path) -> None:
    run_dir, data_root, downloads = _make_tree(tmp_path)
    (data_root / "raw" / DATASET / "PROVENANCE.json").write_text("{nope", encoding="utf-8")
    assert _statuses(_run(run_dir, data_root, downloads))["dataset-provenance"] == "FAIL"


def test_provenance_missing_archive_sha_fails(tmp_path: Path) -> None:
    run_dir, data_root, downloads = _make_tree(tmp_path, provenance_sha=None)
    assert _statuses(_run(run_dir, data_root, downloads))["dataset-provenance"] == "FAIL"


def test_provenance_dataset_mismatch_fails(tmp_path: Path) -> None:
    run_dir, data_root, downloads = _make_tree(tmp_path, provenance_dataset="plantdoc")
    assert _statuses(_run(run_dir, data_root, downloads))["dataset-provenance"] == "FAIL"


def test_archive_match_ok(tmp_path: Path) -> None:
    run_dir, data_root, downloads = _make_tree(tmp_path)
    (downloads / gate.SOURCE_ARCHIVE_BASENAMES[DATASET][0]).write_bytes(ARCHIVE_BYTES)
    assert _statuses(_run(run_dir, data_root, downloads))["archive-integrity"] == "OK"


def test_archive_explicit_path_match_ok(tmp_path: Path) -> None:
    run_dir, data_root, downloads = _make_tree(tmp_path)
    explicit = tmp_path / "elsewhere" / "my-archive.zip"
    explicit.parent.mkdir()
    explicit.write_bytes(ARCHIVE_BYTES)
    checks = _run(run_dir, data_root, downloads, archive=explicit)
    assert _statuses(checks)["archive-integrity"] == "OK"


def test_archive_mismatch_fails(tmp_path: Path) -> None:
    run_dir, data_root, downloads = _make_tree(tmp_path)
    (downloads / gate.SOURCE_ARCHIVE_BASENAMES[DATASET][0]).write_bytes(b"tampered bytes")
    checks = _run(run_dir, data_root, downloads)
    check = next(c for c in checks if c.name == "archive-integrity")
    assert check.status == "FAIL"
    assert "integrity chain is broken" in check.detail


def test_archive_explicit_path_missing_fails(tmp_path: Path) -> None:
    run_dir, data_root, downloads = _make_tree(tmp_path)
    checks = _run(run_dir, data_root, downloads, archive=tmp_path / "missing.zip")
    assert _statuses(checks)["archive-integrity"] == "FAIL"


def test_checkpoint_embedded_mismatch_fails(tmp_path: Path) -> None:
    other = hashlib.sha256(b"someone tampered").hexdigest()
    run_dir, data_root, downloads = _make_tree(tmp_path, embedded_sha=other)
    checks = _run(run_dir, data_root, downloads)
    assert _statuses(checks)["checkpoint-embedded-hash"] == "FAIL"
    assert not gate.gate_passed(checks)


def test_checkpoint_byte_hash_differs_is_info_not_fail(tmp_path: Path) -> None:
    """Recorded sha is the pre-embedding save hash by construction; the byte hash of the
    final checkpoint must therefore differ -> INFO evidence, never a failure, never
    'corrected'."""
    run_dir, data_root, downloads = _make_tree(tmp_path)
    checks = _run(run_dir, data_root, downloads)
    check = next(c for c in checks if c.name == "checkpoint-byte-hash")
    assert check.status == "INFO"
    assert "save protocol" in check.detail
    assert gate.gate_passed(checks)


def test_checkpoint_recorded_sha_malformed_fails(tmp_path: Path) -> None:
    run_dir, data_root, downloads = _make_tree(tmp_path, recorded_sha="not-a-hash")
    checks = _run(run_dir, data_root, downloads)
    assert _statuses(checks)["checkpoint-recorded-hash"] == "FAIL"
    assert not gate.gate_passed(checks)


def test_cli_exit_codes_and_out_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    run_dir, data_root, _downloads = _make_tree(tmp_path)
    out_json = tmp_path / "reports" / "gate.json"
    # Explicit archive (matching) keeps the CLI deterministic regardless of host machine.
    archive = tmp_path / "downloads" / gate.SOURCE_ARCHIVE_BASENAMES[DATASET][0]
    archive.parent.mkdir(parents=True, exist_ok=True)
    archive.write_bytes(ARCHIVE_BYTES)
    argv = ["--run-dir", str(run_dir), "--dataset", DATASET, "--data-root", str(data_root), "--archive", str(archive)]

    rc_ok = gate.main([*argv, "--out-json", str(out_json)])
    assert rc_ok == 0
    record = json.loads(out_json.read_text(encoding="utf-8"))
    assert record["result"] == "PASS"
    assert record["dataset"] == DATASET
    assert {c["name"] for c in record["checks"]} >= {"run-artifacts", "metrics", "split-manifest"}

    (run_dir / "config.yaml").unlink()
    rc_fail = gate.main(argv)
    assert rc_fail == 1
    out = capsys.readouterr().out
    assert "RESULT: FAIL" in out
