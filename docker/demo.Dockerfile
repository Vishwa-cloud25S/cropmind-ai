# Public-demo all-in-one image (Phase 12).
#
# Local/dev truth (ADR-004) stays split: torch-free API + torch-carrying worker.
# Free-tier hosts (Render free web service) cannot run a separate background
# worker, so THIS image runs both loops in one process — demo topology only,
# plainly documented in docs/12-deployment.md. It carries torch because the
# in-process poller runs inference.
#
# No real checkpoint is ever shipped here (AD-008): the public URL runs the
# deterministic DEMO sample model; every prediction is flagged demo=true.
FROM python:3.12-slim

# Comments are NOT legal inside a continued ENV statement (Render build 2026-08-11
# failed exactly there) — keep them above the instruction.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    OMP_NUM_THREADS=1

# OMP_NUM_THREADS=1 above: single shared vCPU on free tier — keep torch single-threaded.

WORKDIR /app

COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# CPU-only torch for the in-process inference poller.
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch torchvision

COPY backend/app ./app
COPY backend/alembic ./alembic
COPY backend/alembic.ini ./alembic.ini
COPY ml ./ml
COPY simulation ./simulation
COPY docker/demo-start.sh ./demo-start.sh

ENV ML_CONFIG_DIR=/app/ml/configs \
    UPLOAD_DIR=/data/uploads \
    APP_ENV=production

# Render injects $PORT (10000 by default); the start script binds it.
CMD ["sh", "/app/demo-start.sh"]
