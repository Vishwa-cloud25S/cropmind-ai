"""Database engine, session factory, FastAPI dependency, readiness check."""

import logging
from collections.abc import Iterator
from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

logger = logging.getLogger("cropmind.db")


@lru_cache
def get_engine() -> Engine:
    url = get_settings().database_url
    connect_args = {"connect_timeout": 2} if url.startswith("postgresql") else {}
    return create_engine(url, pool_pre_ping=True, connect_args=connect_args)


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False)


def _db_session() -> Iterator[Session]:
    """FastAPI dependency: one session per request, rollback on error, always closed."""
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


DbSession = Annotated[Session, Depends(_db_session)]


def check_database() -> bool:
    """Cheap liveness check used by /health/ready. Never raises."""
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except SQLAlchemyError as exc:  # pragma: no cover - exercised via 503 test
        logger.warning("database check failed: %s", exc.__class__.__name__)
        return False
