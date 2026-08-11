"""Phase 12 — deployment artifact integrity.

The public demo is declared in files (render.yaml, docker/demo.*, docs/12) — files
win, so the tests pin the files: the blueprint must reference real, parseable
artifacts, and the demo-only invariants (DEMO_MODE=true, no real checkpoint,
psycopg URL normalization, single-process start) must hold textually. A drift
here means the demo URL silently diverged from the documentation.
"""

from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]


def _read(rel: str) -> str:
    path = REPO_ROOT / rel
    assert path.is_file(), f"deploy artifact missing: {rel}"
    return path.read_text(encoding="utf-8")


def test_render_blueprint_parses_and_references_real_files() -> None:
    doc = yaml.safe_load(_read("render.yaml"))
    services = doc.get("services") or []
    assert len(services) == 1, "demo topology is exactly one free web service (docs/12 §1)"
    svc = services[0]
    assert svc["plan"] == "free"
    assert svc["type"] == "web"
    assert svc["healthCheckPath"] == "/health/ready"
    # every path the blueprint names must exist
    assert (REPO_ROOT / svc["dockerfilePath"]).is_file()
    assert svc["dockerContext"] == "."
    dbs = doc.get("databases") or []
    assert dbs and dbs[0]["plan"] == "free"


def test_demo_service_is_demo_mode_and_database_is_wired() -> None:
    doc = yaml.safe_load(_read("render.yaml"))
    env = {e["key"]: e for e in doc["services"][0]["envVars"]}
    assert env["DEMO_MODE"]["value"] == "true"  # public URL never serves unflagged output
    assert "MODEL_CHECKPOINT" not in env  # no real checkpoint on free hosting (AD-008)
    assert env["DATABASE_URL"]["fromDatabase"]["name"] == doc["databases"][0]["name"]
    assert env["JWT_SECRET_KEY"]["generateValue"] is True  # never a committed secret
    assert env["CORS_ORIGINS"]["sync"] is False  # operator sets the actual Vercel origin


def test_demo_image_runs_migrate_seed_worker_api_in_one_process() -> None:
    dockerfile = _read("docker/demo.Dockerfile")
    start = _read("docker/demo-start.sh")
    assert 'CMD ["sh", "/app/demo-start.sh"]' in dockerfile
    for step in ("alembic upgrade head", "app.db.seed", "app.workers.analysis_worker", "uvicorn app.main:app"):
        assert step in start, f"demo start script lost its step: {step}"
    # single-process topology is demo-only — the start script must say so itself
    assert "NOT the production shape" in start


def test_deploy_doc_records_free_tier_limits_and_fallbacks() -> None:
    doc = _read("docs/12-deployment.md")
    for fact in ("15 min", "30 days", "750 free hours", "512 MB", "DEMO_MODE=true"):
        assert fact in doc, f"docs/12 must keep stating the free-tier fact: {fact}"
    assert "pending first deploy" in doc  # deploy log starts empty, not invented
