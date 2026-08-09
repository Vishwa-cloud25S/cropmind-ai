"""DB-queue lifecycle tests: claim/heartbeat/complete, attempts-aware retry backoff,
terminal failure with analysis mirroring, and stale-job reaping."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.db import models
from app.services.queue import LocalDbQueue


def _utcnow_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _make_analysis(db_session_factory) -> models.Analysis:
    """One Image + one Analysis (flushed parents before children: UUID default rule)."""
    with db_session_factory.begin() as session:
        image = models.Image(
            path="ab/leaf.jpg", sha256="0" * 64, width=64, height=48, byte_size=1234,
        )
        session.add(image)
        session.flush()
        analysis = models.Analysis(image_id=image.id)
        session.add(analysis)
        session.flush()
        session.refresh(analysis)
        session.expunge(analysis)
        return analysis


def test_enqueue_claim_complete_flow(db_session_factory) -> None:
    analysis = _make_analysis(db_session_factory)
    queue = LocalDbQueue(db_session_factory)

    job = queue.enqueue(analysis.id, max_attempts=3)
    assert job.status == "PENDING" and job.max_attempts == 3

    job = queue.claim("worker-1")
    assert job is not None and job.status == "RUNNING"
    assert job.attempts == 1 and job.locked_by == "worker-1"
    assert queue.claim("worker-2") is None  # nothing else pending

    with db_session_factory() as session:  # analysis mirror is honest about running
        assert session.get(models.Analysis, analysis.id).status == "PROCESSING"

    queue.heartbeat(job.id, "worker-1")
    queue.complete(job.id, "worker-1")
    with db_session_factory() as session:
        row = session.get(models.AnalysisJob, job.id)
        assert row.status == "COMPLETED" and row.finished_at is not None
        mirrored = session.get(models.Analysis, analysis.id)
        assert mirrored.status == "COMPLETED" and mirrored.completed_at is not None


def test_fail_retries_with_backoff_then_terminal(db_session_factory) -> None:
    analysis = _make_analysis(db_session_factory)
    queue = LocalDbQueue(db_session_factory)
    job = queue.enqueue(analysis.id, max_attempts=2)

    # Attempt 1: claim, fail → back to PENDING with run_after in the future.
    job = queue.claim("w")
    queue.fail(job.id, "w", {"type": "ValueError", "message": "boom"}, backoff_s=10.0)
    with db_session_factory() as session:
        row = session.get(models.AnalysisJob, job.id)
        assert row.status == "PENDING"
        assert row.run_after > _utcnow_naive()  # attempts² · backoff
        assert row.error_json["type"] == "ValueError"
        assert session.get(models.Analysis, analysis.id).status == "QUEUED"  # honest: will retry
        row.run_after = _utcnow_naive() - timedelta(seconds=1)  # fast-forward the backoff
        session.commit()

    # Attempt 2: claim (attempts=2), fail → terminal FAILED (attempts exhausted).
    job = queue.claim("w")
    assert job.attempts == 2
    queue.fail(job.id, "w", {"type": "ValueError", "message": "boom again"}, backoff_s=10.0)
    with db_session_factory() as session:
        row = session.get(models.AnalysisJob, job.id)
        assert row.status == "FAILED"
        mirrored = session.get(models.Analysis, analysis.id)
        assert mirrored.status == "FAILED"
        assert "ValueError: boom again" in mirrored.error
    assert queue.claim("w") is None  # terminal jobs are never re-claimed


def test_complete_by_wrong_worker_is_ignored(db_session_factory) -> None:
    analysis = _make_analysis(db_session_factory)
    queue = LocalDbQueue(db_session_factory)
    queue.enqueue(analysis.id, max_attempts=3)
    job = queue.claim("worker-A")
    assert job is not None
    queue.complete(job.id, "worker-B")  # not the lock owner → no-op
    with db_session_factory() as session:
        assert session.get(models.AnalysisJob, job.id).status == "RUNNING"


def test_reap_stale_resets_heartbeatless_jobs(db_session_factory) -> None:
    analysis = _make_analysis(db_session_factory)
    queue = LocalDbQueue(db_session_factory)
    queue.enqueue(analysis.id, max_attempts=3)
    job = queue.claim("dead-worker")
    assert job is not None
    with db_session_factory.begin() as session:  # simulate a silent heartbeat
        row = session.get(models.AnalysisJob, job.id)
        row.heartbeat_at = _utcnow_naive() - timedelta(hours=1)

    reaped = queue.reap_stale(timeout_s=120, backoff_s=10.0)
    assert reaped == 1
    with db_session_factory() as session:
        row = session.get(models.AnalysisJob, job.id)
        assert row.status == "PENDING"  # attempts 1 < max 3 → retryable
        assert row.locked_by is None
        assert row.error_json["type"] == "StaleJob"


def test_reap_terminal_when_attempts_exhausted(db_session_factory) -> None:
    analysis = _make_analysis(db_session_factory)
    queue = LocalDbQueue(db_session_factory)
    queue.enqueue(analysis.id, max_attempts=3)
    job = queue.claim("dead-worker")
    assert job is not None
    with db_session_factory.begin() as session:
        row = session.get(models.AnalysisJob, job.id)
        row.heartbeat_at = _utcnow_naive() - timedelta(hours=1)
        row.attempts = row.max_attempts  # already at the ceiling

    queue.reap_stale(timeout_s=120, backoff_s=10.0)
    with db_session_factory() as session:
        assert session.get(models.AnalysisJob, job.id).status == "FAILED"
        assert session.get(models.Analysis, analysis.id).status == "FAILED"


def test_queue_depth_report(db_session_factory) -> None:
    analysis = _make_analysis(db_session_factory)
    queue = LocalDbQueue(db_session_factory)
    queue.enqueue(analysis.id, max_attempts=3)
    depth = queue.depth()
    assert depth.get("PENDING") == 1
