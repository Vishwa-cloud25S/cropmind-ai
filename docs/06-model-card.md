# 06 — Model Card (v1, 2026-08-08)

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
MobileNetV3-Small weights and loads identically under both. Training-side hash pinning of the
dataset archive: recorded in the run's `provenance.json` (`dataset_sha256`); cross-verification
against the operator's local archive is tracked in `docs/08-eval-runbook.md` Step 2.

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

Run status: **PENDING operator execution** of
`python -m ml.evaluation.cli report --run-dir runs/20260808-180238-0.1.0 --device cpu`
(outputs `reports/model_evaluation/REPORT.md` + `summary.json`; this card is backfilled from
that report — numbers are generated, never hand-edited).

| Gate | Requirement | Status |
|---|---|---|
| M1-in-domain-top1 | ≥ 0.80 held-out | Pre-registered PASS at 0.9959 (training-reported); formal status from eval reproduction |
| M1-ood-top1 (PlantDoc) | reported as-is, target ≥ 0.50 | PENDING — no field-level claims until published |
| M1-latency-cpu | p95 ≤ 2,500 ms/image on reference CPU | PENDING (measured in the same report) |

## 5. Support rule for classes

A class becomes *eligible* for `supported_by_model: true` only when the **evaluation report**
shows F1 ≥ 0.90 with support ≥ 20 on the held-out split (rule enforced in
`ml/evaluation/core.py`). Eligibility is computed by the report; the actual taxonomy/model-config
flip is a **separate reviewed commit** with the report on record — nothing self-certifies.

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
