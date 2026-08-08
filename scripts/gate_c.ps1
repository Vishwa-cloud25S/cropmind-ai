# CropMind AI - Gate C runner (see docs/08-eval-runbook.md)
# Performs: artifact check -> provenance/consistency validation -> PlantDoc OOD pipeline
#           -> formal CPU evaluation -> output listing.
#
# Architecture this respects (nothing is fabricated or copied between locations):
#   - run artifacts (train.py):   runs\<run_id>\checkpoint.pt, checkpoint.sha256,
#                                 metrics.json, config.yaml   (model + run metadata)
#   - dataset provenance:         data\raw\<dataset>\PROVENANCE.json
#                                 (acquisition, license, archive integrity)
#   - split manifest:             data\splits\<dataset>\<version>\split_manifest.json
# All cross-checks live in ml/evaluation/gate.py (unit-tested) and run under Step 2.
#
# HOW TO RUN (PowerShell, from the repo root C:\Users\vishw\Desktop\cropmind-ai):
#     type   .\scripts\   then press TAB (PowerShell autocompletes the name), then ENTER.
# Do NOT copy this filename from a chat window - chat renderers corrupt dotted tokens.
# Optional: set $env:CROPMIND_ARCHIVE to the zip path if it is NOT in your Downloads folder.

$ErrorActionPreference = "Stop"

Write-Host "=== Gate C sanity: repo root + venv ===" -ForegroundColor Cyan
if (-not (Test-Path ".\ml\data\cli.py"))        { Write-Error "Run this from the repo root (the cropmind-ai folder)." }
$PY = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $PY))                        { Write-Error "venv not found at .\.venv - create it per README before running Gate C." }
Write-Host "  OK"

Write-Host "`n=== Gate C / Step 1: training run artifacts must be local ===" -ForegroundColor Cyan
$RUN = ".\runs\20260808-180238-0.1.0"
foreach ($f in @("checkpoint.pt", "checkpoint.sha256", "metrics.json", "config.yaml")) {
    if (Test-Path "$RUN\$f") { Write-Host "  OK    $RUN\$f" }
    else                     { Write-Error "  MISSING $RUN\$f -> download the run folder from Drive (My Drive/cropmind/runs) into .\runs\ - runbook Step 1." }
}
if (Test-Path "$RUN\20260808-180238-0.1.0")      { Write-Error "  Double nesting detected ($RUN\20260808-180238-0.1.0) - move the inner folder up one level." }
if (-not (Test-Path ".\data\raw\plantvillage\PROVENANCE.json")) {
    Write-Error "  MISSING .\data\raw\plantvillage\PROVENANCE.json -> import the PlantVillage dataset first (docs/datasets.md)."
}

Write-Host "`n=== Gate C / Step 2: provenance + consistency validation (ml.evaluation.gate) ===" -ForegroundColor Cyan
$gateArgs = @("--run-dir", "runs\20260808-180238-0.1.0", "--dataset", "plantvillage",
              "--out-json", ".\reports\gate_c_precheck.json")
if ($env:CROPMIND_ARCHIVE) { $gateArgs += @("--archive", "$env:CROPMIND_ARCHIVE") }
& $PY -m ml.evaluation.gate @gateArgs
if ($LASTEXITCODE -ne 0) { Write-Error "Gate C preconditions FAILED (exit $LASTEXITCODE) - resolve before evaluating." }

Write-Host "`n=== Gate C / Step 3: PlantDoc out-of-domain pipeline ===" -ForegroundColor Cyan
Write-Host "  Expect: 'reusing existing archive' -> 're-extracting' -> a few quiet minutes -> verify/stats."
& $PY -m ml.data.cli pipeline --dataset plantdoc --accept-license
if ($LASTEXITCODE -ne 0) { Write-Error "PlantDoc pipeline failed (exit $LASTEXITCODE)." }

Write-Host "`n=== Gate C / Step 4: formal evaluation (CPU; 10-30 min; progress every 250 images) ===" -ForegroundColor Cyan
& $PY -m ml.evaluation.cli report --run-dir "runs\20260808-180238-0.1.0" --device cpu
if ($LASTEXITCODE -ne 0) { Write-Error "Evaluation failed (exit $LASTEXITCODE)." }

Write-Host "`n=== Gate C / Step 5: report artifacts ===" -ForegroundColor Cyan
Get-ChildItem .\reports\model_evaluation
Write-Host "`nDONE. Paste back: (a) the gate table printed above, (b) the OOD top-1 and latency lines, (c) the Step 2 validator output (also saved to reports\gate_c_precheck.json)." -ForegroundColor Green
