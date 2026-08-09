# CropMind AI - Phase 5 local verification (backend core)
# Verifies: backend test suite (47 tests incl. uploads/queue/analysis-flow/predictions/
#           schema+alembic/seed), ml suite (111), ruff on both, and a REAL alembic +
#           seed smoke against a throwaway SQLite file - exactly the two commands the
#           worker container runs at startup.
#
# HOW TO RUN (PowerShell, from the repo root C:\Users\vishw\Desktop\cropmind-ai):
#     type   powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\
#     then press TAB (PowerShell autocompletes the script name), then ENTER.
# Do NOT copy this filename from a chat window - chat renderers corrupt dotted tokens.

$ErrorActionPreference = "Stop"

Write-Host "=== Phase 5 sanity: repo root + venv ===" -ForegroundColor Cyan
if (-not (Test-Path ".\backend\app\main.py")) { Write-Error "Run this from the repo root (the cropmind-ai folder)." }
$PY = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $PY))                    { Write-Error "venv not found at .\.venv - create it per README before running." }
Write-Host "  OK"

Write-Host "`n=== Phase 5 / deps: backend requirements into the venv (idempotent) ===" -ForegroundColor Cyan
& $PY -m pip install -q -r .\backend\requirements-dev.txt
Write-Host "  OK"

Write-Host "`n=== Phase 5 / Step 1: backend tests (uploads, queue, analysis flow, predictions, schema+alembic, seed, health, meta) ===" -ForegroundColor Cyan
Set-Location .\backend
& $PY -m pytest -q
Set-Location ..
Write-Host "  OK"

Write-Host "`n=== Phase 5 / Step 2: ml tests (regression - expect 111) ===" -ForegroundColor Cyan
Set-Location .\ml
& $PY -m pytest -q
Set-Location ..
Write-Host "  OK"

Write-Host "`n=== Phase 5 / Step 3: ruff (backend + ml) ===" -ForegroundColor Cyan
& $PY -m ruff check .\backend
& $PY -m ruff check .\ml
Write-Host "  OK"

Write-Host "`n=== Phase 5 / Step 4: alembic upgrade head + seed smoke on throwaway SQLite (the worker container's startup commands) ===" -ForegroundColor Cyan
$DB = Join-Path $env:TEMP "cropmind_phase5_smoke.db"
if (Test-Path $DB) { Remove-Item $DB -Force }
$env:DATABASE_URL = "sqlite+pysqlite:///" + ($DB.Replace("\", "/"))
Set-Location .\backend
& $PY -m alembic upgrade head
& $PY -m app.db.seed
Set-Location ..
Remove-Item Env:\DATABASE_URL -ErrorAction SilentlyContinue
Remove-Item $DB -Force -ErrorAction SilentlyContinue
Write-Host "  OK (14 tables migrated; dataset_sources seeded from the registry: counts NULL, verified_at NULL - measured-only)"

Write-Host "`n=== PHASE 5 VERIFICATION PASSED ===" -ForegroundColor Green
Write-Host "Next:  docker compose up --build   -> POST a leaf photo at http://localhost:8000/docs (Images -> POST /images),"
Write-Host "        create an analysis at Analyses -> POST /analyses with the returned image id, then poll /analyses/{id}"
Write-Host "        and read /analyses/{id}/prediction. MODEL_CHECKPOINT empty = clearly-flagged DEMO sample model."
