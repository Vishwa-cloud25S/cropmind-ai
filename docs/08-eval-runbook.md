# 08 — Evaluation Runbook: Gate C (formal M1 measurement)

**Status:** operator procedure · v2 (2026-08-09)
**Audience:** the project operator (Windows workstation) re-running the formal evaluation of the
Colab-trained baseline run `20260808-180238-0.1.0`.

This runbook turns the training result into the **formal, auditable Gate C evidence** the model
card cites (docs/06 §4.2). Nothing here trains a model, modifies run artifacts, or touches
network services.

## Where each kind of evidence lives (read once)

| Kind | Location | Contains |
|---|---|---|
| **Run artifacts** (model + run metadata) | `runs/<run_id>/` | `checkpoint.pt`, `checkpoint.sha256`, `metrics.json`, `config.yaml` — only what `ml/training/train.py` writes |
| **Dataset provenance** (acquisition / license / archive integrity) | `data/raw/<dataset>/PROVENANCE.json` | source, version, DOI, license, acquisition method, `acquisition.archive_sha256` — written by `ml/data/download.py` at import |
| **Split manifest** (what the split actually is) | `data/splits/<dataset>/<version>/split_manifest.json` | `content_sha256`, seed, per-class counts |

The binding between them: `metrics.json["dataset"]` is `"<dataset>@<split_version>"` (e.g.
`plantvillage@v1`) and `metrics.json["splits_content_sha256"]` must equal the manifest's
`content_sha256`. There is intentionally **no** `provenance.json` inside the run directory —
dataset provenance stays in `data/raw/<dataset>/` and is cross-referenced, never copied.
Gate C enforces all of this (Step 2) and refuses to evaluate on a broken chain.

---

## Step 0 — Sync the repo

```powershell
cd C:\Users\vishw\Desktop\cropmind-ai
git pull origin main
```

> **Fast path:** once Step 1 is done, `scripts\gate_c.ps1` runs Steps 2–5 for you: from the
> repo root, type `.\scripts\` then press **TAB** to autocomplete the script name, then
> **Enter**. If the PlantVillage zip is **not** in your Downloads folder, first run
> `$env:CROPMIND_ARCHIVE = "C:\full\path\to\the\zip"` in the same window.

## Step 1 — Bring the Colab run directory local

The run lives in your Google Drive at `My Drive/cropmind/runs/20260808-180238-0.1.0/`.

1. Open Google Drive in the browser → `My Drive/cropmind/runs/`
2. Right-click the `20260808-180238-0.1.0` folder → **Download** (Drive zips it)
3. Extract so the repo contains **exactly these four artifacts** (plus nothing required else):

```
C:\Users\vishw\Desktop\cropmind-ai\runs\20260808-180238-0.1.0\
    checkpoint.pt
    checkpoint.sha256
    metrics.json
    config.yaml
```

PowerShell alternative (if you downloaded the zip to Downloads):

```powershell
Expand-Archive -LiteralPath "$env:USERPROFILE\Downloads\20260808-180238-0.1.0.zip" -DestinationPath "C:\Users\vishw\Desktop\cropmind-ai\runs" -Force
```

> Beware double nesting (`runs\20260808-180238-0.1.0\20260808-180238-0.1.0\…`) — the Step 1
> check in `scripts\gate_c.ps1` detects it and tells you to move the inner folder up.
>
> The PlantVillage import from Phase 2 must also still be present
> (`data\raw\plantvillage\PROVENANCE.json` + the splits under `data\splits\`); it normally is.

## Step 2 — Provenance & consistency validation (automated)

```powershell
.\.venv\Scripts\python.exe -m ml.evaluation.gate --run-dir runs\20260808-180238-0.1.0 --dataset plantvillage --out-json reports\gate_c_precheck.json
```

Add `--archive "C:\path\to\the\zip"` only if the PlantVillage archive is not in Downloads
(the validator auto-probes `<your-user>\Downloads` for the documented source filename —
a generic per-user location, never a hardcoded path).

The validator (`ml/evaluation/gate.py`, unit-tested) checks and prints each verdict:

1. **run-artifacts** — the four files above are present (FAILS if any are missing).
2. **metrics / dataset-identity** — `metrics.json` parses and claims `plantvillage@v1`;
   FAILS if it references any other dataset.
3. **dataset-provenance** — `data\raw\plantvillage\PROVENANCE.json` exists, parses, agrees on
   the dataset id, and carries a well-formed `acquisition.archive_sha256`
   (expected recorded value per data card: `ac343245…90ff0`).
4. **split-manifest** — `data\splits\plantvillage\v1\split_manifest.json` exists and its
   `content_sha256` equals `metrics.json`'s `splits_content_sha256`
   (expected on both sides: `276dc3e9…30e7`, per data card). FAILS on mismatch — that would
   mean the split on disk is not the split the model trained on. Nothing is hardcoded in the
   validator: both values are read from disk and compared.
5. **checkpoint-integrity** — see the checkpoint-hashes note below.
6. **archive-integrity** — if the source archive is available locally, its sha256 must equal
   `acquisition.archive_sha256` from provenance (FAILS on mismatch = broken integrity chain:
   STOP and report). If it is not available, the check is reported SKIP with instructions —
   the rest of the gate still stands, and you can close the loop manually with:

```powershell
certutil -hashfile "C:\path\to\Plant_leaf_diseases_dataset_without_augmentation.zip" SHA256
```

Compare with `acquisition.archive_sha256` in `data\raw\plantvillage\PROVENANCE.json` and
report `match`/`mismatch`.

Exit code: 0 = **PRECONDITIONS PASS**, 1 = FAIL (failing checks listed). A machine-readable
record lands at `reports\gate_c_precheck.json`.

### Known observation: the two checkpoint hashes (recorded — never "corrected")

`train.py` saves the checkpoint, hashes it, writes `checkpoint.sha256`, embeds that hash
into the checkpoint's metadata, then **re-saves the file**. So the recorded value
(`8af96dcfd32c…86b7f`) is the hash of the *first* serialization, while the bytes on disk
(independently recomputed: `77d6e020179e…fe2be`) are the *second* save. These can never
match — it is a property of the save protocol, **not** corruption. The validator therefore
enforces what is meaningful — `checkpoint.sha256` well-formed **and** the embedded
`meta.checkpoint_sha256` equal to it (a real tamper signal if unequal) — and reports the
byte-hash comparison as **INFO evidence**. `checkpoint.sha256` is not overwritten, not
silently corrected, and the run is not re-hashed in place.

## Step 3 — Build the PlantDoc out-of-domain set (uses the cached 832 MB zip, no re-download)

```powershell
.\.venv\Scripts\python.exe -m ml.data.cli pipeline --dataset plantdoc --accept-license
```

Expected: `reusing existing archive` → `incomplete extraction (no .extracted-ok) — re-extracting`
→ a few quiet minutes → verify/stats output with 17 mapped classes.

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

Paste (or attach):

1. the **Step 2 validator output** (or `reports\gate_c_precheck.json`),
2. the **gate table** from the eval output (or the `gates` block of `summary.json`),
3. the OOD top-1 line and latency p50/p95 lines,
4. the per-class support-eligibility list.

The model card §4.2 gates table and the class-support decision are backfilled from these
measured numbers — the taxonomy flip (`supported_by_model`) stays a **separate, reviewed
commit** after the support rule has been applied to them.

## Troubleshooting

| Symptom | Cause → fix |
|---|---|
| `run directory not found` / artifact FAIL | double nesting from zip extraction — see Step 1 note |
| `dataset-provenance` FAIL | PlantVillage import missing/broken — re-import per datasets.md; provenance is never fabricated |
| `split-manifest` FAIL on content hash | the split on disk is not the training split — do **not** evaluate; restore/regenerate `split v1` per datasets.md |
| `archive-integrity` FAIL on mismatch | broken integrity chain — STOP and report before evaluating |
| `archive-integrity` SKIP | archive not in Downloads — pass `--archive PATH` or set `$env:CROPMIND_ARCHIVE`, or use the certutil line |
| `[INFO] checkpoint-byte-hash …differs` | expected — the documented train.py save protocol (see the checkpoint-hashes note) |
| PlantDoc shows NOT_RUN | Step 3 not completed — `data\raw\plantdoc\PROVENANCE.json` must exist |
| `WARNING … renamed for filesystem safety` during Step 3 | expected for a handful of PlantDoc files whose names contain characters Windows forbids (e.g. `IMG_1629.JPG?1507122477.jpg`); each rename is recorded in `data\raw\plantdoc\PROVENANCE.json` under `extraction` |
| `No module named ...` | wrong shell/venv — run everything from the repo root with `.\.venv\Scripts\python.exe` |
