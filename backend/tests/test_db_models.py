"""Schema tests: ORM create_all, the Alembic 0001 chain, and registry seeding.

Both paths to the schema are exercised — metadata create_all (tests/dev) and
alembic upgrade head (containers/production) — and required to agree on tables.
"""

from __future__ import annotations

import logging
from pathlib import Path

import sqlalchemy as sa
from alembic.config import Config

from alembic import command
from app.core.config import get_settings
from app.db import models
from app.db.seed import seed_dataset_sources
from app.db.session import get_engine

BACKEND_ROOT = Path(__file__).resolve().parents[1]


def _table_names(url: str) -> set[str]:
    engine = sa.create_engine(url)
    try:
        return set(sa.inspect(engine).get_table_names())
    finally:
        engine.dispose()


def test_all_fourteen_tables_created(db_session_factory) -> None:
    assert set(sa.inspect(get_engine()).get_table_names()) == set(models.ALL_TABLES)
    assert len(models.ALL_TABLES) == 15  # +simulation_runs (Phase 8, migration 0004)


def test_basic_insert_roundtrip(db_session_factory) -> None:
    with db_session_factory.begin() as session:
        # UUID primary keys are client-side defaults: they materialize at flush(),
        # so parents must be flushed before children reference them.
        user = models.User(email="farmer@example.com", password_hash="x" * 60)
        session.add(user)
        session.flush()
        farm = models.Farm(owner_id=user.id, name="Dell Farm")
        session.add(farm)
        session.flush()
        field = models.Field(farm_id=farm.id, name="North 40", crop_id="corn", area_ha=4.2)
        session.add(field)
        session.flush()
        assert user.role == "FARMER"  # client-side default
        assert field.farm is farm
        assert farm.owner is user
        assert farm.id in [f.id for f in user.farms]


def _alembic_cfg() -> Config:
    cfg = Config(str(BACKEND_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    return cfg


def test_alembic_upgrade_downgrade_upgrade(tmp_path, monkeypatch) -> None:
    url = f"sqlite+pysqlite:///{(tmp_path / 'alembic.db').as_posix()}"
    monkeypatch.setenv("DATABASE_URL", url)
    get_settings.cache_clear()  # engine for this test not yet created

    # Alembic env runs fileConfig(alembic.ini), whose [logger_root] claims the root
    # logger's level for the rest of this process (in production, alembic CLI and the
    # app are separate processes — containers — so this only matters in-tests).
    root = logging.getLogger()
    saved_level, saved_handlers = root.level, root.handlers[:]
    try:
        command.upgrade(_alembic_cfg(), "head")
        tables = _table_names(url)
        assert set(models.ALL_TABLES) <= tables
        assert "alembic_version" in tables

        command.downgrade(_alembic_cfg(), "base")
        remaining = _table_names(url)
        assert set(models.ALL_TABLES).isdisjoint(remaining)

        command.upgrade(_alembic_cfg(), "head")  # idempotent re-run
        assert set(models.ALL_TABLES) <= _table_names(url)
    finally:
        root.setLevel(saved_level)
        root.handlers[:] = saved_handlers


def test_seed_dataset_sources_from_registry(db_session_factory) -> None:
    result = seed_dataset_sources()
    assert result["created"] == 2  # plantvillage + plantdoc (registry entries)
    with db_session_factory() as session:
        rows = session.query(models.DatasetSource).all()
        assert {r.license_id for r in rows} == {"CC0-1.0", "CC-BY-4.0"}
        for row in rows:
            # Honesty rules: counts are measured-only, seeding is not a re-verification.
            assert row.image_count is None
            assert row.verified_at is None
            assert row.source_url and row.license_url
    again = seed_dataset_sources()  # idempotent
    assert again["created"] == 0 and again["updated"] == 2
