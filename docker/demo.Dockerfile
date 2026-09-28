# Public-demo all-in-one image (Phase 12).
#
# Local/dev truth (ADR-004) stays split: torch-free API + torch-carrying worker.
# Free-tier hosts (Render free web service) cannot run a separate background
# worker, so THIS image runs both loops in one process — demo topology only,
# plainly documented in docs/12-deployment.md. It carries torch because the
# in-process poller runs inference.
#
# No real checkpoint is ever shipped here (AD-008): the sample checkpoint itself IS
# baked into the image at build time (below) as the honest default. AD-009 (Phase 14)
# amends SERVING only: at runtime the worker may fetch the real checkpoint out-of-band
# (MODEL_URL + read-only token, sync:false dashboard env — docs/12 §8). Predictions
# then record demo=false for the real weights; every label is derived from /model-info.
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

# Bake the DEMO sample checkpoint at BUILD time. Runtime generation on a free
# 512 MB instance starves/OOM-loops the container for minutes at the very first
# analysis (observed live 2026-09-28 — sustained 503 waves); at build time the
# RAM/CPU cost is free, and at runtime mlbridge._ensure_sample_checkpoint sees
# the file and skips generation entirely. This is the SYNTHETIC plumbing model
# (0.0.0-sample, meta says so) — never a real run, demo flags unchanged.
RUN OMP_NUM_THREADS=1 python -m ml.training.sample_model \
    && test -f /app/ml/models/pretrained/sample-mobilenetv3.pt

ENV ML_CONFIG_DIR=/app/ml/configs \
    UPLOAD_DIR=/data/uploads \
    APP_ENV=production

# Render injects $PORT (10000 by default); the start script binds it.
CMD ["sh", "/app/demo-start.sh"]
