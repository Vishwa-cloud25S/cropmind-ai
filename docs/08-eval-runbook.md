# 08 — Evaluation Runbook: Gate C (formal M1 measurement)

**Status:** operator procedure · v1 (2026-08-09)
**Audience:** the project operator (Windows workstation) re-running the formal evaluation of the
Colab-trained baseline run `20260808-180238-0.1.0`.

This runbook turns the exploratory training result into the **formal, auditable Gate C evidence**
the model card cites (docs/06 §4.2). Nothing here trains a model or touches network services.

---

## Step 0 — Sync the repo

```powershell
cd C:\Users\vishw\Desktop\cropmind-ai
git pull origin main
```

> **Fast path:** once Steps 0–1 are done, `scripts\gate_c.ps1` runs Steps 3–5 for you
> (with the run-dir checks built in): from the repo root, type `.\scripts\` then press
> **TAB** to autocomplete the script name, then **Enter**. Steps 1–2 below stay manual.

## Step 1 — Bring the Colab run directory local

The run lives in your Google Drive at `My Drive/cropmind/runs/20260808-180238-0.1.0/`
(plus a `*.zip` copy if you chose the download path in the notebook).

1. Open Google Drive in the browser → `My Drive/cropmind/runs/`
2. Right-click the `20260808-180238-0.1.0` folder → **Download** (Drive zips it)
3. Extract so the repo contains **exactly**:

```
C:\Users\vishw\Desktop\cropmind-ai\runs\20260808-180238-0.1.0\
    checkpoint.pt
    checkpoint.sha256
    config.yaml
    metrics.json
    provenance.json
```

PowerShell alternative (if you downloaded the zip to Downloads):

```powershell
Expand-Archive -LiteralPath "$env:USERPROFILE\Downloads\20260808-180238-0.1.0.zip" -DestinationPath "C:\Users\vishw\Desktop\cropmind-ai\runs" -Force
```

Sanity check — this must list the five files:

```powershell
Get-ChildItem C:\Users\vishw\Desktop\cropmind-ai\runs\20260808-180238-0.1.0
```

> Beware double nesting (`runs\20260808-180238-0.1.0\20260808-180238-0.1.0\…`) — if you see
> that, move the inner folder up one level.

## Step 2 — Dataset integrity cross-check (recommended, one command)

The training run recorded the dataset archive's sha256 in
`runs\20260808-180238-0.1.0\provenance.json` (field `dataset_sha256`). Recompute the hash of the
**local** without-augmentation zip and compare:

```powershell
certutil -hashfile "C:\path\to\Plant_leaf_diseases_dataset_without_augmentation.zip" SHA256
```

- **Match** → the audited integrity chain (local archive → Drive → Colab) is confirmed;
  report "match" so the data card attestation can be flipped from recorded to verified.
- **Mismatch** → STOP and report it before evaluating; the provenance chain is broken and the
  formal report would be built on an unverified dataset.

## Step 3 — Build the PlantDoc out-of-domain set (uses the cached 832 MB zip, no re-download)

```powershell
.\.venv\Scripts\python.exe -m ml.data.cli pipeline --dataset plantdoc --accept-license
```

Expected: `reusing existing archive` → `incomplete extraction (no .extracted-ok) — re-extracting`
→ a few silent minutes → verify/stats output with 17 mapped classes. If the archive is
(re)downloaded it will take a few minutes on 888 MB.

## Step 4 — Run the formal evaluation (CPU, full product path incl. Grad-CAM)

```powershell
.\.venv\Scripts\python.exe -m ml.evaluation.cli report --run-dir runs\20260808-180238-0.1.0 --device cpu
```

- Auto-discovers `checkpoint.pt`, `metrics.json`, `config.yaml` from the run directory.
- Evaluates the held-out PlantVillage test split (4,119 images) and, because Step 3 wrote
  `data\raw\plantdoc\PROVENANCE.json`, the PlantDoc OOD set automatically.
- Prints progress every 250 images. Budget **10–30 min** on CPU (this is the full production
  inference path — classification + confidence bands + Grad-CAM per image — which is also what
  makes the latency number the honest product latency).

## Step 5 — Report back

Paste (or attach) from `reports\model_evaluation\`:

1. the **gate table** printed at the end (or the `gates` block of `summary.json`),
2. the OOD top-1 line and latency p50/p95 lines,
3. the per-class support-eligibility list.

The model card §4.2 gates table and the class-support decision are backfilled from these measured
numbers — the taxonomy flip (`supported_by_model`) stays a **separate, reviewed commit** after
the support rule has been applied to them.

## Troubleshooting

| Symptom | Cause → fix |
|---|---|
| `run dir not found` / checkpoint discovery error | double nesting from zip extraction — see Step 1 note |
| PlantDoc shows NOT_RUN | Step 3 not completed — `data\raw\plantdoc\PROVENANCE.json` must exist |
| `No module named ...` | wrong shell/venv — run everything from the repo root with `.\.venv\Scripts\python.exe` |
| Very slow first minutes | expected — torch CPU import + dataset indexing; progress prints each 250 images |
