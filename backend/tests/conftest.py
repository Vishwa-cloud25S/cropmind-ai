"""Backend test fixtures — fully isolated per test, no Postgres needed.

Every test gets: a fresh SQLite file as DATABASE_URL, a fresh uploads dir, DEMO_MODE,
and all 14 tables created via ``Base.metadata.create_all``. Settings/engine/session
caches are cleared so nothing leaks between tests. The mlbridge demo-model cache is
cleared too — no test here ever loads the real predictor (handle stubs instead).
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.db import models
from app.db.session import get_engine, get_session_factory


@pytest.fixture(autouse=True)
def isolated_env(tmp_path, monkeypatch) -> Iterator[None]:
    db_path = (tmp_path / "test.db").as_posix()
    monkeypatch.setenv("DATABASE_URL", f"sqlite+pysqlite:///{db_path}")
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("DEMO_MODE", "true")
    get_settings.cache_clear()
    get_engine.cache_clear()
    get_session_factory.cache_clear()
    models.Base.metadata.create_all(get_engine())
    yield
    get_engine().dispose()
    from app.services import mlbridge

    mlbridge.reset_cache()


@pytest.fixture()
def db_session_factory(isolated_env) -> sessionmaker[Session]:
    return get_session_factory()


@pytest.fixture()
def client(isolated_env) -> Iterator[TestClient]:
    from app.main import create_app

    with TestClient(create_app()) as test_client:
        yield test_client
