"""DB-backed job queue (ADR-004) — LocalDbQueue now, CeleryQueue/RQQueue drop-in later.

Job lifecycle: PENDING -> RUNNING (claim) -> COMPLETED | FAILED (terminal, attempts
exhausted) | back to PENDING (retry, run_after backoff). RUNNING jobs whose heartbeat
goes silent past the timeout are reaped by the next worker sweep.
Portable: FOR UPDATE SKIP LOCKED on PostgreSQL; single-transaction claim on SQLite
(tests/dev). The analysis row is the API-visible mirror of job transitions.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.db import models

logger = logging.getLogger("cropmind.queue")


class JobQueue(Protocol):
    def enqueue(
        self, analysis_id: str, *, max_attempts: int, session: Session | None = None
    ) -> models.AnalysisJob: ...
    def claim(self, worker_id: str) -> models.AnalysisJob | None: ...
    def heartbeat(self, job_id: str, worker_id: str) -> None: ...
    def complete(self, job_id: str, worker_id: str) -> None: ...
    def fail(self, job_id: str, worker_id: str, error: dict, backoff_s: float) -> None: ...
    def reap_stale(self, timeout_s: int, backoff_s: float) -> int: ...


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _naive(dt: datetime) -> datetime:
    """Comparisons against DB timestamps run in naive-UTC (SQLite drops tzinfo)."""
    return dt.replace(tzinfo=None) if dt.tzinfo else dt


class LocalDbQueue:
    def __init__(self, session_factory: sessionmaker[Session]):
        self._sf = session_factory

    def enqueue(
        self, analysis_id: str, *, max_attempts: int = 3, session: Session | None = None
    ) -> models.AnalysisJob:
        """Create a PENDING job.

        With ``session=`` the job row is added to the caller's transaction (the API
        path, where the parent Analysis row is flushed but not yet committed — a
        separate session would violate the FK under Postgres read-committed).
        Without it, the queue manages its own short transaction (worker/scripts path).
        """
        job = models.AnalysisJob(
            analysis_id=analysis_id, max_attempts=max_attempts, run_after=_naive(_utcnow())
        )
        if session is not None:
            session.add(job)
            session.flush()
            return job
        with self._sf.begin() as own_session:
            own_session.add(job)
            own_session.flush()
            own_session.refresh(job)
            return job

    def claim(self, worker_id: str) -> models.AnalysisJob | None:
        now_n = _naive(_utcnow())
        with self._sf.begin() as session:
            stmt = (
                select(models.AnalysisJob)
                .where(models.AnalysisJob.status == "PENDING", models.AnalysisJob.run_after <= now_n)
                .order_by(models.AnalysisJob.created_at)
                .limit(1)
            )
            if session.get_bind().dialect.name == "postgresql":
                stmt = stmt.with_for_update(skip_locked=True)  # worker concurrency (ADR-004)
            job = session.execute(stmt).scalars().first()
            if job is None:
                return None
            job.status, job.locked_by, job.locked_at = "RUNNING", worker_id, now_n
            job.started_at = job.started_at or now_n
            job.heartbeat_at, job.attempts = now_n, job.attempts + 1
            if job.analysis is not None:
                job.analysis.status, job.analysis.started_at = "PROCESSING", job.analysis.started_at or now_n
            session.flush()
            session.expunge(job)
            return job

    def heartbeat(self, job_id: str, worker_id: str) -> None:
        with self._sf.begin() as session:
            job = session.get(models.AnalysisJob, job_id)
            if job is not None and job.status == "RUNNING" and job.locked_by == worker_id:
                job.heartbeat_at = _naive(_utcnow())

    def complete(self, job_id: str, worker_id: str) -> None:
        now_n = _naive(_utcnow())
        with self._sf.begin() as session:
            job = session.get(models.AnalysisJob, job_id)
            if job is None or job.locked_by != worker_id:
                return
            job.status, job.finished_at = "COMPLETED", now_n
            if job.analysis is not None:
                job.analysis.status, job.analysis.completed_at = "COMPLETED", now_n

    def fail(self, job_id: str, worker_id: str, error: dict, backoff_s: float = 10.0) -> None:
        """Attempts-aware: retry with backoff until max_attempts, then terminal FAILED."""
        now_n = _naive(_utcnow())
        with self._sf.begin() as session:
            job = session.get(models.AnalysisJob, job_id)
            if job is None:
                return
            job.error_json = {**error, "attempts": job.attempts, "utc": now_n.isoformat(timespec="seconds")}
            if job.attempts < job.max_attempts:
                job.status = "PENDING"
                job.locked_by = None
                job.run_after = now_n + timedelta(seconds=backoff_s * job.attempts * job.attempts)
                job.finished_at = now_n
                if job.analysis is not None:
                    job.analysis.status = "QUEUED"  # honest: the queue will retry it
            else:
                job.status, job.finished_at = "FAILED", now_n
                if job.analysis is not None:
                    job.analysis.status, job.analysis.completed_at = "FAILED", now_n
                    job.analysis.error = f"{error.get('type', 'Error')}: {error.get('message', '')}"[:2000]

    def reap_stale(self, timeout_s: int, backoff_s: float = 10.0) -> int:
        """RUNNING jobs whose heartbeat went silent => retry-or-fail. Returns reaped count."""
        cutoff = _naive(_utcnow()) - timedelta(seconds=timeout_s)
        reaped = 0
        with self._sf.begin() as session:
            stale = session.execute(
                select(models.AnalysisJob).where(
                    models.AnalysisJob.status == "RUNNING",
                    (models.AnalysisJob.heartbeat_at.is_(None)) | (models.AnalysisJob.heartbeat_at < cutoff),
                )
            ).scalars().all()
            for job in stale:
                owner = job.locked_by or "unknown"
                logger.warning("reaping stale job %s (locked_by=%s, attempts=%d)", job.id, owner, job.attempts)
                job.locked_by = None
                self._fail_in_session(session, job, {"type": "StaleJob", "message": f"worker {owner} heartbeat lost"}, backoff_s)
                reaped += 1
        return reaped

    def _fail_in_session(self, session: Session, job: models.AnalysisJob, error: dict, backoff_s: float) -> None:
        now_n = _naive(_utcnow())
        job.error_json = {**error, "attempts": job.attempts, "utc": now_n.isoformat(timespec="seconds")}
        if job.attempts < job.max_attempts:
            job.status = "PENDING"
            job.run_after = now_n + timedelta(seconds=backoff_s * job.attempts * job.attempts)
            if job.analysis is not None:
                job.analysis.status = "QUEUED"
        else:
            job.status, job.finished_at = "FAILED", now_n
            if job.analysis is not None:
                job.analysis.status, job.analysis.completed_at = "FAILED", now_n
                job.analysis.error = f"{error.get('type')}: {error.get('message')}"[:2000]

    def depth(self) -> dict:
        """Observability: queue depth by status (docs/02 §10)."""
        from sqlalchemy import func

        with self._sf() as session:
            rows = session.execute(
                select(models.AnalysisJob.status, func.count()).group_by(models.AnalysisJob.status)
            ).all()
            return {status: count for status, count in rows}
