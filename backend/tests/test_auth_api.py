"""Auth & roles (Phase 10 — FR-01/02/23).

Pins the security posture: bcrypt hashes (never plaintext), no enumeration,
first-user-ADMIN bootstrap, real logout (denylist), malformed/expired/revoked
401s with WWW-Authenticate, role 403s with reasons, per-user scoping (404 for
out-of-scope rows), and the anonymous demo path working ONLY where documented.
"""

from __future__ import annotations

from sqlalchemy import select

from app.db import models
from app.services import security
from tests.conftest import TEST_PASSWORD, create_user, token_for


def _register(client, email="new@example.test", password="S3cure-pass1") -> dict:
    return client.post("/auth/register", json={"email": email, "password": password})


# ── registration + bootstrap ───────────────────────────────────────────────────


def test_first_registration_becomes_admin_then_farmer(anon_client) -> None:
    first = _register(anon_client, "vishwa@example.test")
    assert first.status_code == 201, first.text
    body = first.json()
    assert body["user"]["role"] == "ADMIN"
    assert "first registered account becomes ADMIN" in body["role_note"]
    assert body["token_type"] == "bearer" and body["access_token"]
    assert body["expires_in_s"] == 720 * 60

    second = _register(anon_client, "grower@example.test")
    assert second.status_code == 201
    assert second.json()["user"]["role"] == "FARMER"
    assert "FARMER" in second.json()["role_note"]


def test_password_is_bcrypt_hashed_never_stored_plain(anon_client, db_session_factory) -> None:
    assert _register(anon_client).status_code == 201
    with db_session_factory() as db:
        user = db.execute(select(models.User).where(models.User.email == "new@example.test")).scalar_one()
    assert user.password_hash.startswith("$2b$")
    assert "S3cure-pass1" not in user.password_hash
    assert security.verify_password("S3cure-pass1", user.password_hash)


def test_password_policy_is_enforced_and_stated(anon_client) -> None:
    too_short = _register(anon_client, password="Ab1")
    assert too_short.status_code == 422
    assert "at least 10 characters" in too_short.json()["detail"]["unmet_rules"]
    no_digit = _register(anon_client, password="abcdefghijkl")
    assert no_digit.status_code == 422
    assert "at least one digit" in no_digit.json()["detail"]["unmet_rules"]
    no_letter = _register(anon_client, password="123456789012")
    assert no_letter.status_code == 422


def test_registration_validation_and_conflict(anon_client) -> None:
    assert _register(anon_client, email="not-an-email").status_code == 422
    assert _register(anon_client).status_code == 201
    conflict = _register(anon_client)
    assert conflict.status_code == 409
    assert "already exists" in conflict.json()["detail"]


# ── login ──────────────────────────────────────────────────────────────────────


def test_login_success_and_generic_failure(anon_client, db_session_factory) -> None:
    create_user("grower@example.test", "FARMER")
    ok = anon_client.post("/auth/login", json={"email": "grower@example.test", "password": TEST_PASSWORD})
    assert ok.status_code == 200
    assert ok.json()["user"]["email"] == "grower@example.test"

    # wrong password AND unknown email get the SAME generic 401 — no enumeration
    bad_pw = anon_client.post("/auth/login", json={"email": "grower@example.test", "password": "wrong-pass-1a"})
    unknown = anon_client.post("/auth/login", json={"email": "ghost@example.test", "password": "wrong-pass-1a"})
    assert bad_pw.status_code == unknown.status_code == 401
    assert bad_pw.json()["detail"] == unknown.json()["detail"] == "invalid email or password"
    assert bad_pw.headers.get("WWW-Authenticate") == "Bearer"

    with db_session_factory() as db:
        actions = db.execute(select(models.AuditLog.action)).scalars().all()
    assert "AUTH_LOGIN_SUCCESS" in actions and "AUTH_LOGIN_FAILED" in actions


def test_me_returns_session_truth(anon_client) -> None:
    token = _register(anon_client).json()["access_token"]
    me = anon_client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    body = me.json()
    assert body["user"]["role"] == "ADMIN"
    assert body["session"]["revocation"].startswith("server-side denylist")
    assert anon_client.get("/auth/me").status_code == 401


# ── logout = real revocation ───────────────────────────────────────────────────


def test_logout_revokes_the_token_server_side(anon_client) -> None:
    token = _register(anon_client).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    out = anon_client.post("/auth/logout", headers=headers)
    assert out.status_code == 200
    assert "revoked server-side" in out.json()["detail"]
    replay = anon_client.get("/auth/me", headers=headers)
    assert replay.status_code == 401
    assert replay.json()["detail"]["auth"] == "revoked"


def test_malformed_expired_tampered_tokens_all_401(client, anon_client, admin_user) -> None:
    assert anon_client.get("/auth/me", headers={"Authorization": "Token abc"}).status_code == 401  # not Bearer
    tampered = anon_client.get("/auth/me", headers={"Authorization": "Bearer not-a-jwt"})
    assert tampered.status_code == 401 and tampered.json()["detail"]["auth"] == "invalid"

    expired_token, _ = security.mint_token(admin_user, ttl_minutes=-1)  # already expired
    resp = anon_client.get("/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
    assert resp.status_code == 401 and resp.json()["detail"]["auth"] == "expired"

    ghost = create_user("ghost@example.test", "FARMER")
    ghost_token = token_for(ghost)
    # delete the user row, keep the token: closed, not open
    from app.db.session import get_session_factory

    with get_session_factory()() as db:
        db.delete(db.get(models.User, ghost.id))
        db.commit()
    assert anon_client.get("/auth/me", headers={"Authorization": f"Bearer {ghost_token}"}).status_code == 401


# ── protected surface: 401 anonymous, demo path only where documented ──────────


def test_anonymous_writes_are_401_except_the_flagged_demo_path(anon_client) -> None:
    assert anon_client.post("/farms", json={"name": "x"}).status_code == 401
    assert anon_client.post("/images", files={"file": ("a.jpg", b"xx", "image/jpeg")}).status_code == 401  # no demo flag
    no_demo = anon_client.post("/analyses", json={"image_id": "nope"})
    assert no_demo.status_code == 401  # the auth gate fires before any resource lookup
    # the demo path: flagged upload works without an account (DEMO_MODE on)
    import io

    from PIL import Image as PILImage

    buf = io.BytesIO()
    PILImage.new("RGB", (32, 32), (10, 120, 40)).save(buf, "JPEG")
    demo = anon_client.post("/images?demo=true", files={"file": ("leaf.jpg", buf.getvalue(), "image/jpeg")})
    assert demo.status_code == 201, demo.text
    image = demo.json()["image"]
    assert image["source_type"] == "DEMO"
    assert image["uploader_id"] is None
    assert "demo" in image["demo_note"]


def test_anonymous_reads_open_only_in_demo_mode(anon_client, monkeypatch) -> None:
    # DEMO_MODE on (suite default): legacy/demo reads work
    assert anon_client.get("/analyses").status_code == 200
    assert anon_client.get("/predictions").status_code == 200
    assert anon_client.get("/reports").status_code == 200

    # demo OFF: anonymous reads 401 clearly
    monkeypatch.setenv("DEMO_MODE", "false")
    from app.core.config import get_settings

    get_settings.cache_clear()
    try:
        assert anon_client.get("/analyses").status_code == 401
    finally:
        monkeypatch.setenv("DEMO_MODE", "true")
        get_settings.cache_clear()


# ── scoping ────────────────────────────────────────────────────────────────────


def test_farmer_sees_own_plus_legacy_rows_admin_sees_all(client, farmer_client, db_session_factory) -> None:
    mine = farmer_client.post("/farms", json={"name": "Farmer Farm"}).json()["farm"]
    assert mine["owner_id"] is not None
    admins = client.post("/farms", json={"name": "Admin Farm"}).json()["farm"]

    farmer_list = farmer_client.get("/farms").json()
    names = {f["name"] for f in farmer_list["farms"]}
    assert "Farmer Farm" in names and "Admin Farm" not in names
    assert "scope_note" in farmer_list

    # out-of-scope rows answer 404 — existence isn't confirmed
    assert farmer_client.get(f"/farms/{admins['id']}").status_code == 404
    assert farmer_client.patch(f"/farms/{admins['id']}", json={"name": "steal"}).status_code == 404
    assert client.get(f"/farms/{mine['id']}").status_code == 200  # admin sees all


def test_agronomist_reads_everything_but_cannot_write_farms(client, agronomist_client) -> None:
    farm = client.post("/farms", json={"name": "Review Target"}).json()["farm"]
    assert agronomist_client.get(f"/farms/{farm['id']}").status_code == 200
    blocked = agronomist_client.post("/farms", json={"name": "nope"})
    assert blocked.status_code == 403
    detail = blocked.json()["detail"]
    assert detail["your_role"] == "AGRONOMIST"
    assert "requires role" in detail["detail"]


def test_demo_rows_visible_to_signed_in_workspace(client, anon_client, tmp_path) -> None:
    import io

    from PIL import Image as PILImage

    from app.workers.analysis_worker import tick
    from tests.test_analysis_flow import StubPredictor, _contract, _handle

    buf = io.BytesIO()
    PILImage.new("RGB", (32, 32), (12, 90, 30)).save(buf, "JPEG")
    up = anon_client.post("/images?demo=true", files={"file": ("l.jpg", buf.getvalue(), "image/jpeg")}).json()["image"]
    created = anon_client.post("/analyses", json={"image_id": up["id"], "demo": True})
    assert created.status_code == 202, created.text
    analysis_id = created.json()["analysis_id"]
    assert tick("w", handle=_handle(StubPredictor(_contract()), tmp_path)) == 1

    # legacy/demo NULL-owner rows are visible to a signed-in farmer too (shared workspace)
    assert client.get(f"/analyses/{analysis_id}").status_code == 200
    assert client.get(f"/analyses/{analysis_id}/prediction").status_code == 200
