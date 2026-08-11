#!/bin/sh
# Single-process demo topology (Phase 12, free tier only — NOT the production shape).
# Migrate → seed → start the queue poller in-process → serve HTTP on $PORT.
# Rationale and limits are documented in docs/12-deployment.md; local dev keeps
# the ADR-004 split (torch-free API + separate worker container).
set -e

echo "demo-start: alembic upgrade head"
python -m alembic upgrade head

echo "demo-start: seed reference data (idempotent)"
python -m app.db.seed

echo "demo-start: launching in-process analysis worker poller"
python -m app.workers.analysis_worker &

echo "demo-start: serving API on port ${PORT:-10000}"
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-10000}"
