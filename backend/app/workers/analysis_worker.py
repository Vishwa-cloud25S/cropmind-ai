"""Analysis worker skeleton.

Runs the same codebase as the API but in a separate process/container. Polls the
`analysis_jobs` table (created in Phase 5 migrations). Exists now so the queue
abstraction (ADR-004) is exercised from day one and swapping to Celery/RQ stays
a config decision, not a rewrite.
"""

import logging
import time

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.logging import configure_logging
from app.db.session import get_engine

logger = logging.getLogger("cropmind.worker")

POLL_INTERVAL_S = 2.0


def poll_once() -> None:
    with get_engine().connect() as conn:
        conn.execute(text("SELECT id FROM analysis_jobs WHERE status = 'PENDING' LIMIT 1"))
        # Job dispatch lands in Phase 5 with the uploads + inference pipeline.


def main() -> None:
    configure_logging()
    logger.info("analysis worker online (queue=local-db, interval=%ss)", POLL_INTERVAL_S)
    while True:
        try:
            poll_once()
        except SQLAlchemyError as exc:
            # Expected until Phase 5 migrations create the jobs table.
            logger.debug("queue not ready (%s) - waiting", exc.__class__.__name__)
        time.sleep(POLL_INTERVAL_S)


if __name__ == "__main__":
    main()
