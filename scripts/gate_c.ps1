# CropMind AI - Gate C runner (see docs/08-eval-runbook.md)
# Performs: run-dir check -> PlantDoc OOD pipeline -> formal CPU evaluation -> output listing.
#
# HOW TO RUN (PowerShell, from the repo root C:\Users\vishw\Desktop\cropmind-ai):
#     type   .\scripts\   then press TAB (PowerShell autocompletes the name), then ENTER.
# Do NOT copy this filename from a chat window - chat renderers corrupt dotted tokens.

$ErrorActionPreference = "Stop"

Write-Host "=== Gate C sanity: repo root + venv ===" -ForegroundColor Cyan
if (-not (Test-Path ".\ml\data\cli.py"))        { Write-Error "Run this from the repo root (the cropmind-ai folder)." }
$PY = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $PY))                        { Write-Error "venv not found at .\.venv - create it per README before running Gate C." }
Write-Host "  OK"

Write-Host "`n=== Gate C / Step 1: training run directory must be local ===" -ForegroundColor Cyan
$RUN = ".\runs\20260808-180238-0.1.0"
foreach ($f in @("checkpoint.pt", "metrics.json", "config.yaml", "provenance.json")) {
    if (Test-Path "$RUN\$f") { Write-Host "  OK    $RUN\$f" }
    else                     { Write-Error "  MISSING $RUN\$f -> download the run folder from Drive (My Drive/cropmind/runs) into .\runs\ - see runbook Step 1, and beware double-nested zip extraction." }
}
if (Test-Path "$RUN\20260808-180238-0.1.0")      { Write-Error "  Double nesting detected ($RUN\20260808-180238-0.1.0) - move the inner folder up one level." }

Write-Host "`n=== Gate C / Step 2: dataset hash cross-check ===" -ForegroundColor Cyan
Write-Host "  Optional but recommended: runbook Step 2 (one certutil line) - report match/mismatch."

Write-Host "`n=== Gate C / Step 3: PlantDoc out-of-domain pipeline ===" -ForegroundColor Cyan
Write-Host "  Expect: 'reusing existing archive' -> 're-extracting' -> a few quiet minutes -> verify/stats."
& $PY -m ml.data.cli pipeline --dataset plantdoc --accept-license
if ($LASTEXITCODE -ne 0) { Write-Error "PlantDoc pipeline failed (exit $LASTEXITCODE)." }

Write-Host "`n=== Gate C / Step 4: formal evaluation (CPU; 10-30 min; progress every 250 images) ===" -ForegroundColor Cyan
& $PY -m ml.evaluation.cli report --run-dir "runs\20260808-180238-0.1.0" --device cpu
if ($LASTEXITCODE -ne 0) { Write-Error "Evaluation failed (exit $LASTEXITCODE)." }

Write-Host "`n=== Gate C / Step 5: report artifacts ===" -ForegroundColor Cyan
Get-ChildItem .\reports\model_evaluation
Write-Host "`nDONE. Paste back: (a) the gate table printed above, (b) the OOD top-1 and latency lines, (c) the certutil match/mismatch from Step 2." -ForegroundColor Green
