# 06 — Model Card (v1.1, 2026-08-09)

**Model:** `cropmind-classifier` · **model_version `0.1.0`** (baseline) · Architecture: **MobileNetV3-Small**
(torchvision, ImageNet init) with replaced head → **21-class softmax** over the canonical sorted
`disease_id` list (embedded in every checkpoint; see `ml/training/classes.py`).

> Every number below says where it was measured. In-domain figures come from clean, lab-style
> PlantVillage imagery and are **not** field-performance claims. The out-of-domain PlantDoc figure
> is the honest signal for real-world expectations and is published as measured.

## 1. Intended use & explicit non-uses

| Intended | Explicitly NOT |
|---|---|
| Decision **support** for triaging suspected leaf disease on Tomato, Potato, Corn (maize), Apple | Definitive diagnosis; spray/no-spray decisions; **chemical product or dosage advice** (none exists anywhere in the product); predictions on crops/conditions outside the documented 21-class scope |
| Priority/risk feed for human review (agronomist workflows) | Standalone automation without a human in the loop for material interventions |

Below the LOW confidence band the product answers **INCONCLUSIVE** with retake/review advice — by
design (`ml/configs/model.yaml` bands, never hardcoded).

## 2. Training configuration (exact, reproducible)

From `ml/configs/train_v1.yaml` (copied into the run directory by every run):

| Setting | Value | Setting | Value |
|---|---|---|---|
| arch | mobilenet_v3_small | optimizer | AdamW (dual LR: head 1e-3, features 1e-4) |
| image size | 224 | weight decay | 0.01 |
| epochs | 12 (run completed all 12; early stop patience 4 not triggered) | label smoothing | 0.1 |
| batch size | 32 | scheduler | cosine + warmup 1 |
| seed | 42 | augmentation (train split only) | rand-resized crop 0.7–1.0, hflip 0.5, rotation 15°, color jitter 0.2/0.2/0.15 |
| device policy | `auto` (cuda else cpu); AMP on CUDA only | run artifacts | `runs/20260808-180238-0.1.0/` (config copy, metrics.json, checkpoint.pt, checkpoint.sha256) |

**Training runtime actually executed (recorded by the notebook's audit cell, run
2026-08-08):** Google Colab, T4 GPU, torch 2.13.0+cu134, torchvision 0.28.0+cu134,
numpy 2.11.0, Pillow 12.1.1. The pinned-supported CPU environment for reproduction/Gate C is
`ml/requirements-ml-lock.txt` (torch 2.10.0+cpu); the checkpoint is plain torchvision
MobileNetV3-Small weights and loads identically under both.

**Integrity & provenance (accurate as of 2026-08-09):** run directories contain *model and
run metadata only* (`checkpoint.pt`, `checkpoint.sha256`, `metrics.json`, `config.yaml`).
Dataset provenance — acquisition, license, and the archive's recorded
`acquisition.archive_sha256` — lives at `data/raw/plantvillage/PROVENANCE.json`, and the
executable split record at `data/splits/plantvillage/v1/split_manifest.json`; Gate C
(`docs/08-eval-runbook.md` Step 2, `ml/evaluation/gate.py`) cross-checks that
`metrics.json` references exactly this dataset (`plantvillage@v1`) and split content hash,
and verifies the local archive against the recorded hash when the archive is available.
**Checkpoint hashes — recorded, not "corrected":** `train.py`'s save protocol hashes the
first serialization (`checkpoint.sha256` = `8af96dcfd32c…86b7f`), embeds that value in
`meta.checkpoint_sha256`, then re-saves; the bytes on disk therefore hash differently
(independently recomputed 2026-08-09: `77d6e020179e…fe2be`). Both values are recorded
here; the validator enforces embedded == recorded and reports the byte hash as evidence.
A save-protocol improvement (hash of the final artifact) is queued as a separate reviewed
change — it does not touch this run.

## 3. Data

Held-out split provenance: **PlantVillage, Mendeley mirror v1** (`mendeley-v1`, DOI
10.17632/tywbtsjrjv.1, CC0 1.0 — verified per `docs/datasets.md`): the 21-class V1 subset of the
without-augmentation archive, 27,335 images → deterministic 70/15/15 split, seed 42
(train 19,126 / val 4,090 / **test 4,119**). Split content sha256
`276dc3e9f21bf497b8996b089946281616857128e24436870331527af42130e7`. Full data card: `docs/07-data-card.md`.

## 4. Measured performance

### 4.1 Training-reported, held-out test split (operator run, GitHub-visible artifacts)

Source: `runs/20260808-180238-0.1.0/metrics.json` (2026-08-08, CUDA). These are **training-reported**;
the evaluation pipeline (`ml/evaluation/`) reproduces them independently per image.

| Metric | Value |
|---|---|
| **Held-out test top-1** | **0.9959** (4,119 images) |
| Best validation top-1 | 0.9944 |
| Mean across-class F1 | 8 classes at F1 = 1.000; weakest: corn Cercospora/gray leaf spot F1 0.974 (n=78), corn northern leaf blight F1 0.977 (n=149), potato healthy F1 0.980 (n=24, small-sample) |

### 4.2 Formal M1 gates (docs/01 §6) — measured by the evaluation report

Run status: **MEASURED AND VERIFIED 2026-08-09** — operator Windows workstation, CPU, evaluator
`ml/evaluation/` at `main`; preconditions validator PASS with audit record
`reports/gate_c_precheck.json` (run ↔ dataset ↔ split manifest ↔ archive hash all bound).
Artifacts: `reports/model_evaluation/{REPORT.md, summary.json, confusion_*.png, exemplars/}`.
**The console-transcribed values were cross-checked against the generated `summary.json` and
`REPORT.md`: all gates matched; the file values are the ones recorded below (files win, always).**

| Gate | Requirement | Status | Measured |
|---|---|---|---|
| M1-in-domain-top1 | ≥ 0.80 held-out | ✅ **PASS** | **0.9959** (4,119 images; matches training-reported 0.99587, consistency drift ≈ 0.0000 ≤ 0.02) |
| M1-ood-top1 (PlantDoc) | published as-is, target ≥ 0.50 | 🔶 **SHORTFALL** | **0.2349** (real field imagery) |
| M1-latency-cpu | p95 ≤ 2,500 ms/image | ✅ **PASS** | **110.4 ms p95** (classification path: preprocess + forward + bands; Grad-CAM runs only for exemplars and is excluded from the gate per the report's definition) |

Notes: the OOD pass iterated the raw extracted PlantDoc **train/** tree (the images-root the
pipeline selected — the tree with the 28 class folders): 17 folders map to V1 classes and the
11 unmapped folders (865 images across other crops/conditions) are recorded as skipped —
counted, never claimed as supported. **The eval count 1,477 is verified: it equals the exact
sum of the 17 per-class OOD supports in `summary.json`.** The operator splits/stats report
over the same 17 classes totals 1,474; that residual 3-image delta is an open reconciliation
item (candidates: split tiny-class policy / an excluded-or-unreadable file; the plantdoc
`split_manifest.json` closes it line-for-line — file values win either way). 93 archive
members were renamed at extraction for filesystem safety/clash, recorded verbatim in the
plantdoc `PROVENANCE.json` under `extraction`. The SHORTFALL status is the designed honesty
checkpoint for the domain gap (see §6 limitations): a published fact, not a failed
certification — and it motivates the roadmap's field-data work.

### 4.3 Measured detail (verified from `summary.json` / `REPORT.md`, 2026-08-09)

**In-domain (4,119 images).** Mean normalized-entropy uncertainty **0.2099**. Confidence-band
distribution under the current thresholds: HIGH 4,064 (**98.7%**) · MEDIUM 43 (1.0%) · LOW 12
(0.3%) · INCONCLUSIVE 0. Top confusions: corn Cercospora/gray leaf spot → corn northern leaf
blight (×3) and tomato spider mites → tomato target spot (×3). 12 worst-error exemplars with
Grad-CAM overlays preserved in `reports/model_evaluation/exemplars/` (heatmaps are
correlation, not lesion-location proof).

**Out-of-domain (PlantDoc field imagery, 1,477 images, coverage 17/21 classes).** Top-1 0.2349.
Band distribution: HIGH 214 (**14.5%**) · MEDIUM 198 (13.4%) · LOW 495 (33.5%) · INCONCLUSIVE
570 (**38.6%**). The abstention machinery fires exactly where accuracy collapses: on field
imagery the product predominantly refuses confident answers instead of hallucinating them.
Per-class OOD extremes: best corn northern leaf blight F1 0.498 (n=180); tomato mosaic virus
F1 0.000 (n=44 — predictions absorbed by other classes); tomato spider mites n=2 (thin
coverage). Latency reference: OOD p95 216.5 ms/image (max 622.4) — also far under the gate.
No PlantDoc folder exists for apple_black_rot, corn_healthy, potato_healthy (a recorded
dataset limitation) or tomato_target_spot — hence coverage 17/21, never rounded up.

## 5. Support rule for classes

A class becomes *eligible* for `supported_by_model: true` only when the **evaluation report**
shows F1 ≥ 0.90 with support ≥ 20 on the held-out split (rule enforced in
`ml/evaluation/core.py`). Eligibility is computed by the report; the actual taxonomy/model-config
flip is a **separate reviewed commit** with the report on record — nothing self-certifies.

**Outcome (2026-08-09, report on record):** all **21 classes are eligible** — weakest
in-domain F1 0.974 ≥ 0.90 (corn Cercospora/gray leaf spot, n=78); smallest support 24 ≥ 20
(potato healthy); watchlist empty. The reviewed flip was executed as its own commit
**`c9f454f`** (operator-approved, referencing `reports/model_evaluation/summary.json`):
all 21 `supported_by_model` flags are now `true` in `ml/configs/taxonomy.yaml` v0.2, and
`ml/configs/model.yaml` registers the baseline as **EVALUATED 0.1.0** — *not* PROMOTED
(serving wiring is Phase 5), and `model_available` stays false until then.

## 6. Limitations (travel with the model, wherever it is cited)

1. **Domain gap:** trained on uniform-background leaf imagery; PlantDoc field imagery is the
   published honesty check — marketed accuracy must always quote both numbers.
2. **Class scope reflects data availability**, not agronomic importance; 4 crops / 21 conditions only.
3. **Severity** shown anywhere is a labelled visual proxy (no severity ground truth in the data).
4. **Grad-CAM** regions are correlation, not proof of lesion location.
5. **Class imbalance** (~33:1, e.g. potato healthy support 24 in the test split) → small-sample
   variance on thin classes; per-class numbers are published, never hidden behind the aggregate.
6. No pesticide product/dosage guidance exists in the product. Decision support only.

## 7. Attribution

Images: PlantVillage collection (CC0 1.0) per `docs/datasets.md` citation; backbone:
torchvision MobileNetV3 (BSD 3-clause); evaluation imagery: PlantDoc (CC BY 4.0, attribution in
`docs/07-data-card.md`). Changelog: v1 2026-08-08 — first trained baseline + formal-gate scaffolding.
