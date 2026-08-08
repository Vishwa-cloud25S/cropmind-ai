"""Database engine + readiness check. ORM models & Alembic migrations land in Phase 5."""

import logging
from functools import lru_cache

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings

logger = logging.getLogger("cropmind.db")


@lru_cache
def get_engine() -> Engine:
    url = get_settings().database_url
    connect_args = {"connect_timeout": 2} if url.startswith("postgresql") else {}
    return create_engine(url, pool_pre_ping=True, connect_args=connect_args)


def check_database() -> bool:
    """Cheap liveness check used by /health/ready. Never raises."""
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except SQLAlchemyError as exc:  # pragma: no cover - exercised via 503 test
        logger.warning("database check failed: %s", exc.__class__.__name__)
        return False
