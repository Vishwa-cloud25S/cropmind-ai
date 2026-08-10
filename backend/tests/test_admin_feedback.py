"""Feedback capture + admin surface + rate limiting (Phase 10 — FR-18/21).

Feedback is per-account (401 anonymous), needs a completed prediction (409),
and is audited. Admin endpoints are ADMIN-only (403 with the reason for other
roles), role changes are audited OLD → NEW, and the auth rate limit returns an
honest 429 with Retry-After.
"""

from __future__ import annotations

from sqlalchemy import select

from app.db import models
from app.workers.analysis_worker import tick
from tests.test_analysis_flow import StubPredictor, _contract, _handle, _upload


def _completed(client, tmp_path, demo=False) -> str:
    image_id = _upload(client)
    analysis_id = client.post("/analyses", json={"image_id": image_id, "demo": demo}).json()["analysis_id"]
    assert tick("fb-worker", handle=_handle(StubPredictor(_contract()), tmp_path)) == 1
    return analysis_id


# ── feedback ───────────────────────────────────────────────────────────────────


def test_feedback_happy_path_is_audited(client, tmp_path, db_session_factory) -> None:
    analysis_id = _completed(client, tmp_path)
    resp = client.post(
        f"/analyses/{analysis_id}/feedback",
        json={"correctness": "YES", "actual_condition": "Northern Leaf Blight", "notes": "matches scouting", "image_quality": "GOOD"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["feedback"]["correctness"] == "YES"
    assert "no automatic retraining" in body["note"]

    mine = client.get(f"/analyses/{analysis_id}/feedback").json()
    assert mine["count"] == 1
    assert mine["feedback"][0]["user_id"] is not None

    with db_session_factory() as db:
        actions = db.execute(
            select(models.AuditLog.action).where(models.AuditLog.entity == "feedback")
        ).scalars().all()
    assert actions == ["FEEDBACK_SUBMITTED"]


def test_feedback_gates(anon_client, client, tmp_path) -> None:
    analysis_id = _completed(client, tmp_path)
    # anonymous: 401 — feedback is per-account by design
    assert anon_client.post(f"/analyses/{analysis_id}/feedback", json={"correctness": "YES"}).status_code == 401
    # invalid enum: 422
    assert client.post(f"/analyses/{analysis_id}/feedback", json={"correctness": "SORT_OF"}).status_code == 422
    # not-completed analysis: 409
    image_id = _upload(client)
    pending_id = client.post("/analyses", json={"image_id": image_id}).json()["analysis_id"]
    not_ready = client.post(f"/analyses/{pending_id}/feedback", json={"correctness": "NO", "actual_condition": "unknown"})
    assert not_ready.status_code == 409
    # unknown analysis: 404
    assert client.post("/analyses/nope/feedback", json={"correctness": "YES"}).status_code == 404


def test_feedback_ownership_scoping(farmer_client, agronomist_client, tmp_path) -> None:
    analysis_id = _completed(farmer_client, tmp_path)
    farmer_client.post(f"/analyses/{analysis_id}/feedback", json={"correctness": "NOT_SURE", "notes": "retake later"})

    own = farmer_client.get(f"/analyses/{analysis_id}/feedback").json()
    assert own["count"] == 1
    assert "user_email" not in own["feedback"][0]  # attribution hidden outside the reviewer surface
    reviewer = agronomist_client.get(f"/analyses/{analysis_id}/feedback").json()
    assert reviewer["count"] == 1
    assert reviewer["feedback"][0]["user_email"] == "farmer@example.test"  # reviewers see attribution


# ── admin surface ──────────────────────────────────────────────────────────────


def test_admin_requires_admin_role(client, farmer_client, agronomist_client) -> None:
    assert client.get("/admin/users").status_code == 200
    for non_admin in (farmer_client, agronomist_client):
        resp = non_admin.get("/admin/users")
        assert resp.status_code == 403
        assert resp.json()["detail"]["requires"] == ["ADMIN"]
    for endpoint in ("/admin/feedback", "/admin/audit-logs", "/admin/overview"):
        assert farmer_client.get(endpoint).status_code == 403


def test_admin_users_list_and_role_change_with_audit(client, farmer_client, db_session_factory) -> None:
    users = client.get("/admin/users").json()
    assert users["count"] == 2
    bootstrap = next(u for u in users["users"] if u["email"] == "admin@example.test")
    assert bootstrap["bootstrap_note"]  # first-user admin note travels
    farmer = next(u for u in users["users"] if u["email"] == "farmer@example.test")

    changed = client.patch(f"/admin/users/{farmer['id']}/role", json={"role": "AGRONOMIST"})
    assert changed.status_code == 200, changed.text
    assert changed.json()["role_transition"] == "FARMER → AGRONOMIST"

    with db_session_factory() as db:
        row = db.execute(
            select(models.AuditLog).where(
                models.AuditLog.action == "AUTH_ROLE_CHANGED", models.AuditLog.entity_id == farmer["id"]
            )
        ).scalar_one()
        assert row.user_id == users["users"][0]["id"]  # the admin acted

    # admin cannot change their OWN role (no-admins-left footgun blocked)
    me = client.get("/auth/me").json()["user"]
    self_change = client.patch(f"/admin/users/{me['id']}/role", json={"role": "FARMER"})
    assert self_change.status_code == 409
    assert "your own role" in self_change.json()["detail"]

    # invalid role: 422; unknown user: 404
    assert client.patch(f"/admin/users/{farmer['id']}/role", json={"role": "SUPERUSER"}).status_code == 422
    assert client.patch("/admin/users/nope/role", json={"role": "FARMER"}).status_code == 404


def test_admin_feedback_overview_and_audit_tail(client, tmp_path) -> None:
    analysis_id = _completed(client, tmp_path)
    client.post(f"/analyses/{analysis_id}/feedback", json={"correctness": "NO", "actual_condition": "healthy leaf"})

    feedback = client.get("/admin/feedback").json()
    assert feedback["total"] == 1
    assert feedback["by_correctness"] == {"NO": 1}
    assert feedback["feedback"][0]["user_email"] == "admin@example.test"

    overview = client.get("/admin/overview").json()["overview"]
    assert overview["users"] == 1 and overview["analyses"] == 1
    assert overview["predictions_by_status"] == {"SUSPECTED": 1}
    assert overview["feedback"] == 1

    logs = client.get("/admin/audit-logs").json()
    assert logs["count"] >= 1
    actions = {row["action"] for row in logs["audit_logs"]}
    assert "FEEDBACK_SUBMITTED" in actions


# ── rate limiting ──────────────────────────────────────────────────────────────


def test_auth_rate_limit_returns_honest_429(anon_client, monkeypatch) -> None:
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")
    monkeypatch.setenv("RATE_LIMIT_AUTH_PER_MINUTE", "3")
    from app.core.config import get_settings
    from app.services import ratelimit

    get_settings.cache_clear()
    ratelimit.reset_limiter()

    results = [
        anon_client.post("/auth/login", json={"email": "rate@example.test", "password": "whatever-1a"})
        for _ in range(5)
    ]
    statuses = [r.status_code for r in results]
    assert statuses[:3] == [401, 401, 401]
    assert statuses[3] == 429
    limited = results[3].json()["detail"]
    assert "rate limit exceeded" in limited["detail"]
    assert limited["retry_after_s"] >= 1
    assert results[3].headers["Retry-After"]
