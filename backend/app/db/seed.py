"""Seed dataset_sources from the dataset registry (ml/data/registry.py).

Data honesty rules (NFR-09 / ADR-002):
- Only license-verified, provenance-recorded datasets appear here — the registry
  mirrors the audited human record in docs/datasets.md.
- image_count stays NULL until measured from real data — it is never invented.
- verified_at stays NULL: seeding copies the registry's recorded verification
  (license_observed lives in docs/datasets.md); it is not itself a re-verification.
Idempotent: rows are keyed on (name, version); re-running updates in place.

Runs in the worker/api container at startup (`python -m app.db.seed`) and imports
only ml.data.registry — pure Python, no torch.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from sqlalchemy import select

from app.db import models
from app.db.session import get_session_factory

# Repo root on sys.path for `ml.*` when invoked outside the repo root (e.g. backend/).
_REPO_ROOT = Path(__file__).resolve().parents[3]
if (_REPO_ROOT / "ml").is_dir() and str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from ml.data.registry import REGISTRY

logger = logging.getLogger("cropmind.seed")


def seed_dataset_sources() -> dict[str, int]:
    """Upsert one DatasetSource row per registry entry. Returns {'created': n, 'updated': n}."""
    created = updated = 0
    with get_session_factory().begin() as session:
        for key, spec in REGISTRY.items():
            row = session.execute(
                select(models.DatasetSource).where(
                    models.DatasetSource.name == spec.name,
                    models.DatasetSource.version == spec.version,
                )
            ).scalars().first()
            if row is None:
                session.add(
                    models.DatasetSource(
                        name=spec.name,
                        version=spec.version,
                        source_url=spec.page_url,
                        license_id=spec.license_id,
                        license_url=spec.license_url,
                        image_count=None,  # never invented — measured only
                        limitations=spec.notes or None,
                    )
                )
                created += 1
                logger.info("seeded dataset_source '%s' (%s)", key, spec.version)
            else:
                row.source_url = spec.page_url
                row.license_id = spec.license_id
                row.license_url = spec.license_url
                row.limitations = spec.notes or None
                updated += 1
                logger.info("dataset_source '%s' (%s) already present — refreshed", key, spec.version)
    return {"created": created, "updated": updated}


def main() -> int:
    from app.core.logging import configure_logging

    configure_logging("INFO")
    result = seed_dataset_sources()
    print(f"dataset_sources seeded: created={result['created']} updated={result['updated']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
