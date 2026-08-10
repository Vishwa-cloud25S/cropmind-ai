"""Backend test fixtures — fully isolated per test, no Postgres needed.

Every test gets: a fresh SQLite file as DATABASE_URL, a fresh uploads dir, DEMO_MODE,
and all 16 tables created via ``Base.metadata.create_all``. Settings/engine/session
caches are cleared so nothing leaks between tests. The mlbridge demo-model cache is
cleared too — no test here ever loads the real predictor (handle stubs instead).

Auth (Phase 10): the default ``client`` is authenticated as a freshly-registered
ADMIN (first user = bootstrap admin), so pre-auth tests keep exercising the full
surface. ``anon_client`` has no credentials; ``farmer_client``/``agronomist_client``
cover the role matrix. A fixed suite-only JWT secret keeps minted tokens valid for
the test's lifetime; the shared password hash is precomputed once (bcrypt work is
real but paid once, not per test); rate limiting is OFF by default here and
switched on inside its own dedicated tests.
"""

from __future__ import annotations

from collections.abc import Iterator

import bcrypt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.db import models
from app.db.session import get_engine, get_session_factory

TEST_PASSWORD = "Passw0rd-1234"  # suite-only credential against the throwaway per-test DB
TEST_PASSWORD_HASH = bcrypt.hashpw(TEST_PASSWORD.encode(), bcrypt.gensalt()).decode()  # computed once


@pytest.fixture(autouse=True)
def isolated_env(tmp_path, monkeypatch) -> Iterator[None]:
    db_path = (tmp_path / "test.db").as_posix()
    monkeypatch.setenv("DATABASE_URL", f"sqlite+pysqlite:///{db_path}")
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("JWT_SECRET_KEY", "test-suite-fixed-secret-not-a-real-key")
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "false")  # dedicated rate-limit tests re-enable
    get_settings.cache_clear()
    get_engine.cache_clear()
    get_session_factory.cache_clear()
    models.Base.metadata.create_all(get_engine())
    yield
    get_engine().dispose()
    from app.services import mlbridge, ratelimit

    mlbridge.reset_cache()
    ratelimit.reset_limiter()


@pytest.fixture()
def db_session_factory(isolated_env) -> sessionmaker[Session]:
    return get_session_factory()


def create_user(email: str, role: str = "FARMER") -> models.User:
    """Create a user directly (suite fixtures; password is TEST_PASSWORD)."""
    with get_session_factory()() as db:
        user = models.User(email=email, password_hash=TEST_PASSWORD_HASH, role=role)
        db.add(user)
        db.commit()
        db.refresh(user)
        db.expunge(user)
        return user


def token_for(user: models.User) -> str:
    from app.services import security

    token, _ = security.mint_token(user)
    return token


@pytest.fixture()
def admin_user(isolated_env) -> models.User:
    return create_user("admin@example.test", "ADMIN")


@pytest.fixture()
def client(isolated_env, admin_user) -> Iterator[TestClient]:
    """Authenticated as the bootstrap ADMIN — the full pre-auth test surface keeps working."""
    from app.main import create_app

    with TestClient(create_app()) as test_client:
        test_client.headers["Authorization"] = f"Bearer {token_for(admin_user)}"
        yield test_client


@pytest.fixture()
def anon_client(isolated_env) -> Iterator[TestClient]:
    """No credentials — for 401/demo-path tests."""
    from app.main import create_app

    with TestClient(create_app()) as test_client:
        yield test_client


@pytest.fixture()
def farmer_client(isolated_env, admin_user) -> Iterator[TestClient]:
    """Second account, FARMER role (the default for non-bootstrap registrations)."""
    from app.main import create_app

    farmer = create_user("farmer@example.test", "FARMER")
    with TestClient(create_app()) as test_client:
        test_client.headers["Authorization"] = f"Bearer {token_for(farmer)}"
        yield test_client


@pytest.fixture()
def agronomist_client(isolated_env, admin_user) -> Iterator[TestClient]:
    from app.main import create_app

    agronomist = create_user("agronomist@example.test", "AGRONOMIST")
    with TestClient(create_app()) as test_client:
        test_client.headers["Authorization"] = f"Bearer {token_for(agronomist)}"
        yield test_client
