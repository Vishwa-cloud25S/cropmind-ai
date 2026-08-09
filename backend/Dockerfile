# API image — deliberately torch-free (ADR-004): the worker image (worker.Dockerfile)
# carries the ML runtime; this one serves HTTP + runs Alembic migrations at startup.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app ./app
COPY backend/alembic ./alembic
COPY backend/alembic.ini ./alembic.ini
COPY ml/configs ./ml_configs
COPY simulation ./simulation

ENV ML_CONFIG_DIR=/app/ml_configs \
    UPLOAD_DIR=/data/uploads \
    APP_ENV=production

EXPOSE 8000
CMD ["sh", "-c", "python -m alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
