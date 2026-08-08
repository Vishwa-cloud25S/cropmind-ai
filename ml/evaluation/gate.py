"""Gate C precondition validator (docs/08-eval-runbook.md).

    python -m ml.evaluation.gate --run-dir runs/<run_id> --dataset plantvillage [--archive PATH]

Validates a training run against the ACTUAL repository architecture. It never fabricates
files, never copies provenance into the run directory, and never modifies the run.

Architecture it binds together (three distinct kinds of evidence):

- Run artifacts (ml/training/train.py): ``checkpoint.pt``, ``checkpoint.sha256``,
  ``metrics.json``, ``config.yaml`` — model weights + run/training metadata only.
- Dataset provenance (ml/data/download.py): ``data/raw/<dataset>/PROVENANCE.json`` —
  source/license/acquisition metadata, incl. ``acquisition.archive_sha256``.
- Split manifest (ml/data/split.py): ``data/splits/<dataset>/<version>/split_manifest.json``
  — the executable record of the split content (``content_sha256``).

The binding: ``metrics.json["dataset"]`` is ``"<dataset>@<split_version>"`` and
``metrics.json["splits_content_sha256"]`` must equal the manifest's ``content_sha256``.

Checkpoint hashes and the save protocol (train.py, documented — never "corrected"):
train.py hashes the first ``torch.save``, writes ``checkpoint.sha256``, embeds the value
into ``checkpoint["meta"]["checkpoint_sha256"]`` and re-saves the file. The on-disk bytes
therefore can never hash to the recorded value. The validator enforces what is meaningful
(recorded value well-formed; embedded meta == recorded value — a real tamper signal) and
REPORTS the byte-hash comparison as informational evidence. Nothing is overwritten.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from ml.data.download import sha256_file

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATA_ROOT = REPO_ROOT / "data"

RUN_ARTIFACTS = ("checkpoint.pt", "checkpoint.sha256", "metrics.json", "config.yaml")

# Source archive basenames used for the OPTIONAL auto-probe in the operator's Downloads
# folder (generic per-user location, never a hardcoded user path). Values mirror the
# filenames documented in the dataset register (docs/datasets.md / ml/data/registry.py).
SOURCE_ARCHIVE_BASENAMES = {
    "plantvillage": ("Plant_leaf_diseases_dataset_without_augmentation.zip",),
}

_HEX64 = re.compile(r"^[0-9a-f]{64}$")

logger = logging.getLogger("cropmind.ml.evaluation.gate")


@dataclass
class Check:
    name: str
    status: str  # OK | FAIL | SKIP | INFO
    detail: str


def _ok(name: str, detail: str) -> Check:
    return Check(name, "OK", detail)


def _fail(name: str, detail: str) -> Check:
    return Check(name, "FAIL", detail)


def _read_json(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _check_run_artifacts(run_dir: Path) -> Check:
    if not run_dir.is_dir():
        return _fail("run-artifacts", f"run directory not found: {run_dir}")
    missing = [name for name in RUN_ARTIFACTS if not (run_dir / name).is_file()]
    if missing:
        nested = run_dir / run_dir.name
        hint = (
            f" (double nesting detected: {nested} — move the inner folder up one level)"
            if nested.is_dir()
            else " (fetch the run from Drive per runbook Step 1)"
        )
        return _fail("run-artifacts", f"missing {', '.join(missing)} in {run_dir}{hint}")
    return _ok("run-artifacts", "present: " + ", ".join(RUN_ARTIFACTS))


def _check_metrics(metrics_path: Path) -> tuple[Check, dict | None]:
    if not metrics_path.is_file():
        return _fail("metrics", f"not found: {metrics_path}"), None
    metrics = _read_json(metrics_path)
    if metrics is None:
        return _fail("metrics", f"malformed JSON: {metrics_path}"), None
    missing = [k for k in ("run_id", "dataset", "splits_content_sha256") if not metrics.get(k)]
    if missing:
        return _fail("metrics", f"missing keys {missing} in {metrics_path}"), None
    return _ok("metrics", f"run_id {metrics['run_id']}, dataset {metrics['dataset']}"), metrics


def _check_dataset_identity(metrics: dict, dataset: str) -> tuple[Check, str | None]:
    claimed = str(metrics["dataset"])
    match = re.fullmatch(r"([A-Za-z0-9_\-]+)@(.+)", claimed)
    if match is None:
        return _fail("dataset-identity", f"metrics dataset {claimed!r} is not in <dataset>@<version> form"), None
    name, version = match.group(1), match.group(2)
    if name != dataset:
        return (
            _fail("dataset-identity", f"metrics reference wrong dataset: {claimed!r} (gate invoked for {dataset!r})"),
            None,
        )
    return _ok("dataset-identity", f"metrics dataset {claimed!r} matches gate invocation"), version


def _check_dataset_provenance(data_root: Path, dataset: str) -> Check:
    prov_path = data_root / "raw" / dataset / "PROVENANCE.json"
    if not prov_path.is_file():
        return _fail(
            "dataset-provenance",
            f"not found: {prov_path} — import the dataset first (see datasets.md); provenance is never fabricated",
        )
    prov = _read_json(prov_path)
    if prov is None:
        return _fail("dataset-provenance", f"malformed JSON: {prov_path}")
    if prov.get("dataset") != dataset:
        return _fail("dataset-provenance", f"provenance dataset {prov.get('dataset')!r} != {dataset!r}")
    acquisition = prov.get("acquisition")
    sha = acquisition.get("archive_sha256") if isinstance(acquisition, dict) else None
    if not (isinstance(sha, str) and _HEX64.fullmatch(sha)):
        return _fail("dataset-provenance", f"acquisition.archive_sha256 missing or malformed in {prov_path}")
    method = acquisition.get("method", "unknown")
    return _ok("dataset-provenance", f"{prov_path} (method {method}, archive sha256 recorded)")


def _check_split_manifest(data_root: Path, dataset: str, version: str, metrics: dict) -> Check:
    manifest_path = data_root / "splits" / dataset / version / "split_manifest.json"
    if not manifest_path.is_file():
        return _fail("split-manifest", f"not found: {manifest_path} — run the split command for {dataset}@{version}")
    manifest = _read_json(manifest_path)
    if manifest is None:
        return _fail("split-manifest", f"malformed JSON: {manifest_path}")
    for key, expected in (("dataset", dataset), ("version", version)):
        if manifest.get(key) != expected:
            return _fail(
                "split-manifest",
                f"manifest {key} {manifest.get(key)!r} != {expected!r} ({manifest_path})",
            )
    manifest_sha = manifest.get("content_sha256")
    metrics_sha = metrics.get("splits_content_sha256")
    if not (isinstance(manifest_sha, str) and _HEX64.fullmatch(manifest_sha)):
        return _fail("split-manifest", f"content_sha256 missing or malformed in {manifest_path}")
    if metrics_sha != manifest_sha:
        return _fail(
            "split-manifest",
            "split content sha256 mismatch — metrics.json claims "
            f"{metrics_sha} but the split manifest records {manifest_sha}; "
            "the run did not train on the split currently on disk",
        )
    return _ok("split-manifest", f"metrics splits_content_sha256 == manifest content_sha256 ({manifest_sha[:16]}…)")


def _check_checkpoint(run_dir: Path) -> list[Check]:
    checks: list[Check] = []
    sha_path = run_dir / "checkpoint.sha256"
    recorded = ""
    if sha_path.is_file():
        content = sha_path.read_text(encoding="utf-8").strip()
        recorded = content.split()[0] if content else ""
        if _HEX64.fullmatch(recorded):
            checks.append(_ok("checkpoint-recorded-hash", "checkpoint.sha256 well-formed (64-hex)"))
        else:
            checks.append(_fail("checkpoint-recorded-hash", f"checkpoint.sha256 content is not a 64-hex sha256: {recorded!r}"))
            recorded = ""
    ckpt_path = run_dir / "checkpoint.pt"
    if not ckpt_path.is_file() or not recorded:
        checks.append(
            _fail("checkpoint-embedded-hash", "skipped: checkpoint.pt or a well-formed checkpoint.sha256 is missing")
        )
        return checks
    try:
        import torch

        blob = torch.load(ckpt_path, map_location="cpu")
    except Exception as exc:  # noqa: BLE001 — any loader failure means the artifact is broken
        checks.append(_fail("checkpoint-embedded-hash", f"checkpoint.pt unreadable: {exc}"))
        return checks
    embedded = ""
    if isinstance(blob, dict):
        meta = blob.get("meta")
        if isinstance(meta, dict):
            embedded = str(meta.get("checkpoint_sha256") or "")
    if not embedded:
        checks.append(_fail("checkpoint-embedded-hash", "meta.checkpoint_sha256 missing inside checkpoint.pt"))
    elif embedded != recorded:
        checks.append(
            _fail(
                "checkpoint-embedded-hash",
                f"embedded meta.checkpoint_sha256 {embedded} != recorded checkpoint.sha256 {recorded} "
                "— inconsistent artifacts (possible tampering or a corrupted save)",
            )
        )
    else:
        checks.append(_ok("checkpoint-embedded-hash", "embedded meta.checkpoint_sha256 == recorded checkpoint.sha256"))
    byte_sha = sha256_file(ckpt_path)
    if byte_sha == recorded:
        checks.append(_ok("checkpoint-byte-hash", f"checkpoint.pt byte sha256 == recorded ({byte_sha[:16]}…)"))
    else:
        checks.append(
            Check(
                "checkpoint-byte-hash",
                "INFO",
                f"checkpoint.pt byte sha256 {byte_sha} differs from recorded {recorded} — expected under the "
                "train.py save protocol (hash computed pre-embedding, file re-saved with the value embedded); "
                "documented in model card §2. Recorded as evidence; nothing is overwritten or corrected.",
            )
        )
    return checks


def _find_archive(archive: Path | None, dataset: str, downloads_dir: Path | None) -> tuple[Path | None, str | None]:
    """Return (path, problem). problem is set only for a definite lookup failure."""
    if archive is not None:
        if archive.is_file():
            return archive, None
        return None, f"--archive path not found: {archive}"
    if downloads_dir is not None:
        for basename in SOURCE_ARCHIVE_BASENAMES.get(dataset, ()):
            candidate = downloads_dir / basename
            if candidate.is_file():
                return candidate, None
    return None, None


def _check_archive_integrity(
    archive: Path | None, dataset: str, data_root: Path, downloads_dir: Path | None
) -> Check:
    prov = _read_json(data_root / "raw" / dataset / "PROVENANCE.json") or {}
    acquisition = prov.get("acquisition") if isinstance(prov.get("acquisition"), dict) else {}
    expected = acquisition.get("archive_sha256") or ""
    path, problem = _find_archive(archive, dataset, downloads_dir)
    if problem is not None:
        return _fail("archive-integrity", problem)
    if path is None:
        return Check(
            "archive-integrity",
            "SKIP",
            f"no local {dataset} archive found (probed {downloads_dir}): pass --archive PATH, or use the certutil "
            "one-liner in runbook Step 2 and report match/mismatch — recorded archive sha256 is "
            f"{expected[:16]}… (from PROVENANCE.json)",
        )
    actual = sha256_file(path)
    if actual != expected:
        return _fail(
            "archive-integrity",
            f"archive sha256 mismatch — {path} hashes to {actual} but PROVENANCE.json recorded {expected}; "
            "the integrity chain is broken: STOP and report per runbook Step 2",
        )
    return _ok("archive-integrity", f"{path} sha256 == acquisition.archive_sha256 ({actual[:16]}…)")


def run_gate_checks(
    run_dir: Path,
    dataset: str,
    archive: Path | None = None,
    data_root: Path = DEFAULT_DATA_ROOT,
    downloads_dir: Path | None = None,
) -> list[Check]:
    """Run all Gate C checks. Any status FAIL ⇒ preconditions not met. Pure reads."""
    if downloads_dir is None:
        downloads_dir = Path.home() / "Downloads"  # generic per-user probe, never a hardcoded path
    checks: list[Check] = [_check_run_artifacts(run_dir)]
    if checks[0].status == "FAIL":
        return checks
    metrics_check, metrics = _check_metrics(run_dir / "metrics.json")
    checks.append(metrics_check)
    if metrics is None:
        return checks
    identity_check, version = _check_dataset_identity(metrics, dataset)
    checks.append(identity_check)
    checks.append(_check_dataset_provenance(data_root, dataset))
    if version is not None:
        checks.append(_check_split_manifest(data_root, dataset, version, metrics))
    checks.extend(_check_checkpoint(run_dir))
    if any(c.name == "dataset-provenance" and c.status == "OK" for c in checks):
        checks.append(_check_archive_integrity(archive, dataset, data_root, downloads_dir))
    else:
        checks.append(
            _fail("archive-integrity", "skipped: dataset provenance check did not pass")
        )
    return checks


def gate_passed(checks: list[Check]) -> bool:
    return all(c.status != "FAIL" for c in checks)


def print_report(run_dir: Path, dataset: str, checks: list[Check]) -> None:
    print(f"Gate C preconditions — run {run_dir.name}, dataset {dataset}")
    for check in checks:
        print(f"[{check.status:>4}] {check.name}: {check.detail}")
    if gate_passed(checks):
        print("RESULT: PASS — formal evaluation may proceed")
    else:
        failed = [c.name for c in checks if c.status == "FAIL"]
        print(f"RESULT: FAIL ({len(failed)} failing: {', '.join(failed)}) — resolve before evaluating")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--run-dir", required=True, type=Path, help="training run directory (runs/<run_id>)")
    parser.add_argument("--dataset", required=True, help="dataset the run claims, e.g. plantvillage")
    parser.add_argument("--archive", type=Path, default=None, help="optional explicit path to the source archive zip")
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT, help="repo data/ root (raw + splits)")
    parser.add_argument("--out-json", type=Path, default=None, help="optional machine-readable record path")
    args = parser.parse_args(argv)

    checks = run_gate_checks(
        run_dir=args.run_dir,
        dataset=args.dataset,
        archive=args.archive,
        data_root=args.data_root,
    )
    print_report(args.run_dir, args.dataset, checks)
    ok = gate_passed(checks)

    if args.out_json is not None:
        record = {
            "run_dir": str(args.run_dir),
            "dataset": args.dataset,
            "checked_utc": datetime.now(UTC).isoformat(timespec="seconds"),
            "result": "PASS" if ok else "FAIL",
            "checks": [asdict(c) for c in checks],
        }
        args.out_json.parent.mkdir(parents=True, exist_ok=True)
        args.out_json.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        print(f"record written: {args.out_json}")

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
