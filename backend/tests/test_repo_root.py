"""find_repo_root must resolve the repo root in BOTH deployment layouts.

Regression for the live container failure caught on the first Docker acceptance run
(2026-08-09): a hardcoded parents[3] lands on the filesystem root inside the worker
image (/app/app/... has one level less than backend/app/...), and the DEMO sample-model
subprocess then exits instantly with "No module named ml" — every analysis FAILED.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.services.mlbridge import find_repo_root


def test_checkout_layout_backend_app(tmp_path) -> None:
    root = tmp_path / "cropmind-ai"
    workers = root / "backend" / "app" / "workers"
    workers.mkdir(parents=True)
    (root / "ml" / "configs").mkdir(parents=True)
    assert find_repo_root(workers / "analysis_worker.py") == root


def test_container_layout_app_app(tmp_path) -> None:
    root = tmp_path / "app"
    workers = root / "app" / "workers"  # Dockerfile: COPY backend/app ./app
    workers.mkdir(parents=True)
    (root / "ml" / "configs").mkdir(parents=True)
    assert find_repo_root(workers / "analysis_worker.py") == root


def test_accepts_a_directory_as_start(tmp_path) -> None:
    root = tmp_path / "app"
    (root / "app" / "db").mkdir(parents=True)
    (root / "ml" / "configs").mkdir(parents=True)
    assert find_repo_root(root / "app" / "db") == root


def test_no_marker_raises_loudly(tmp_path) -> None:
    orphan = tmp_path / "x.py"
    orphan.write_text("", encoding="utf-8")
    with pytest.raises(RuntimeError, match="repo root not found"):
        find_repo_root(orphan)


def test_current_module_file_resolves_this_repo() -> None:
    # Wherever the test runs from, mlbridge's own file must find the REAL repo root.
    import app.services.mlbridge as mb

    assert (find_repo_root(Path(mb.__file__)) / "ml" / "configs" / "taxonomy.yaml").is_file()
