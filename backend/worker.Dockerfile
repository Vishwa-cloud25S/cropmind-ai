# Analysis-worker image (ADR-004): same codebase as the API plus the torch CPU
# runtime and the full ml/ tree — the worker is the only process that imports torch
# (the API never does). Startup: migrate -> seed dataset_sources -> poll the queue.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY backend/requirements.txt ./requirements.txt
RUN pip install -r requirements.txt

# CPU-only torch for the inference bridge (kept out of the API image on purpose).
RUN pip install --index-url https://download.pytorch.org/whl/cpu torch torchvision

COPY backend/app ./app
COPY backend/alembic ./alembic
COPY backend/alembic.ini ./alembic.ini
COPY ml ./ml

ENV ML_CONFIG_DIR=/app/ml/configs \
    UPLOAD_DIR=/data/uploads \
    APP_ENV=production

# MODEL_CHECKPOINT unset => the clearly-flagged DEMO sample model is generated once
# (deterministic, seeded) into /app/ml/models/pretrained/ — mount that path to reuse it.
CMD ["sh", "-c", "python -m alembic upgrade head && python -m app.db.seed && python -m app.workers.analysis_worker"]
