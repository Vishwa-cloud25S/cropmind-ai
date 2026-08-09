"""Analysis worker (ADR-004): separate process/container, same codebase.

Loop: reap stale RUNNING jobs -> claim -> process via the shipped Predictor
(lazily loaded; MODEL_CHECKPOINT unset clearly means DEMO sample model) ->
complete/fail with attempts-aware backoff. Heartbeats during execution make the
stale detector safe to run. `--once` exists for tests/CI.
"""

from __future__ import annotations

import argparse
import logging
import socket
import time
from pathlib import Path

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.session import get_session_factory
from app.services import analysis as analysis_svc
from app.services.mlbridge import ModelHandle, get_predictor
from app.services.queue import LocalDbQueue

logger = logging.getLogger("cropmind.worker")

REPO_ROOT = Path(__file__).resolve().parents[3]


def tick(worker_id: str, *, handle: ModelHandle | None = None) -> int:
    """One sweep: reap stale jobs, then claim+process one job. Returns jobs processed."""
    settings = get_settings()
    queue = LocalDbQueue(get_session_factory())
    reaped = queue.reap_stale(settings.job_heartbeat_timeout_s, settings.job_retry_backoff_s)
    if reaped:
        logger.info("reaped %d stale job(s)", reaped)
    job = queue.claim(worker_id)
    if job is None:
        return 0
    logger.info("claimed job %s (analysis %s, attempt %d)", job.id, job.analysis_id, job.attempts)
    try:
        handle = handle or get_predictor(settings.model_checkpoint, REPO_ROOT, device="cpu")
        queue.heartbeat(job.id, worker_id)
        analysis_svc.process_analysis(
            get_session_factory(), job.analysis_id, handle=handle, upload_dir=Path(settings.upload_dir)
        )
        queue.complete(job.id, worker_id)
        logger.info("job %s COMPLETED (analysis %s)", job.id, job.analysis_id)
    except Exception as exc:
        logger.exception("job %s failed", job.id)
        queue.fail(job.id, worker_id, {"type": exc.__class__.__name__, "message": str(exc)[:1000]}, settings.job_retry_backoff_s)
    return 1


def run_forever(worker_id: str, interval_s: float) -> None:
    logger.info("worker %s online (poll %.1fs)", worker_id, interval_s)
    while True:
        try:
            tick(worker_id)
        except Exception:
            logger.exception("tick error — continuing")
        time.sleep(interval_s)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true", help="single sweep (tests/CI)")
    parser.add_argument("--worker-id", default=f"{socket.gethostname()}-{int(time.time())}")
    args = parser.parse_args()
    configure_logging("INFO")
    if args.once:
        return 0 if tick(args.worker_id) >= 0 else 1
    run_forever(args.worker_id, get_settings().worker_poll_interval_s)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
