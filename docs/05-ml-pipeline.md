# 05 — ML Pipeline

**Status:** Data stage implemented (Phase 2, 2026-08-08). Training/evaluation/inference interfaces
land in Phases 3–4 per the roadmap; their design is recorded here so later work follows it.

---

## 1. Overview

```mermaid
flowchart LR
    DL[Download<br/>ml/data/download.py] --> PV[PROVENANCE.json<br/>license, sha256, counts]
    DL --> SP[Split<br/>ml/data/split.py]
    SP --> MF[split_manifest.json<br/>seed, ratios, skipped]
    SP --> VE[Verify<br/>ml/data/verify.py]
    VE --> ST[Stats<br/>reports/datasets/]
    ST --> TR[Training<br/>Phase 3]
    TR --> EV[Evaluation<br/>Phase 4<br/>reports/model_evaluation/]
    EV --> MG{Metric gates<br/>honest threshold}
    MG -->|pass| INF[Inference service<br/>Phase 3–5]
    MG -->|fail| KB[Report archived<br/>model NOT promoted]
```

## 2. Data stage (implemented)

| Step | Module | Contract |
|---|---|---|
| Registry | `ml/data/registry.py` | Machine mirror of docs/datasets.md: license id/url, page url, candidate download urls, notes. Downloads refuse URLs not in the registry. |
| Class mapping | `ml/data/classmap.py` | Normalizes mirror folder conventions → `disease_id` from `ml/configs/taxonomy.yaml`. Targets validated against the taxonomy in tests. Excluded (e.g. `Background_without_leaves`) and out-of-scope classes are recorded, never silently dropped. |
| Download | `ml/data/download.py` | License gate (`--accept-license`), ordered candidate URLs, PK-signature check, path-traversal-safe extraction, nested *without-augmentation* archive preference, `PROVENANCE.json`. Idempotent (caches archive). |
| Split | `ml/data/split.py` | Stratified, image-level, seed-audited (default 42, recorded), ratios recorded (default 70/15/15). Same seed ⇒ byte-identical `train/val/test.txt` + content sha. |
| Verify | `ml/data/verify.py` | Provenance required-keys, split counts vs manifest, file existence, duplicate detection, **cross-split leakage detection**. Non-zero exit on any problem. |
| Stats | `ml/data/stats.py` | Markdown + CSV per dataset in `reports/datasets/`: class × split counts, skipped folders, largest/smallest classes. Feeds docs/07-data-card.md. |

CLI: `python -m ml.data.cli {download|split|verify|stats|pipeline} --dataset …` (see `docs/datasets.md` for exact commands).

### Leakage posture (explicit decisions)

1. **Source-level:** training uses the without-augmentation PlantVillage archive only, because
   the augmented archive contains transformed duplicates that would contaminate val/test.
2. **Runtime-level (Phase 3):** augmentation happens inside the training transform on GPU/CPU,
   applied to the training split only; nothing is written back to `data/`.
3. **Check-level:** `verify_splits` fails CI if any path appears in more than one split.

## 3. Training stage (Phase 3 — interface contract)

- **Model:** MobileNetV3-Small (torchvision weights, ImageNet init) with a replaced classifier
  head → 21-class softmax (taxonomy-driven class list).
- **Runs:** `ml/training/train.py --config ml/configs/train_v1.yaml`; every run writes
  `runs/<run_id>/` with config copy, metrics history, confusion data, and a checkpoint
  (checkpoint stays out of git; sha256 recorded).
- **Hardware posture:** must run on free Colab/Kaggle GPU **and** CPU (slow but possible);
  batch/accumulation in config, not code.
- **Uncertainty:** predictive entropy + max-softmax recorded per sample at eval time.

## 4. Evaluation stage (Phase 4 — contract)

- Held-out PlantVillage test split: top-1, per-class P/R/F1, confusion matrix PNG.
- Out-of-domain PlantDoc evaluation (honesty metric, never tuned on).
- Latency: CPU inference time distribution (p50/p95) at 224px.
- Failure exemplars: top false positives/negatives saved for the model card.
- Output: `reports/model_evaluation/<model_version>/` — machine JSON + markdown + charts.
- Gates (M1, PRD §6): top-1 ≥ 0.80 in-domain; OOD number reported as-is; CPU p50 ≤ 2.5 s.

## 5. Inference stage (Phases 3–5 — contract)

`ml/inference/predictor.py` exposes:

```python
class Predictor:
    def predict(self, image: Path) -> Prediction: ...
    # Prediction: crop, condition(disease_id), confidence, band(HIGH/MEDIUM/LOW),
    # uncertainty(predictive entropy), estimated_visual_severity,
    # gradcam_overlay_path, regions[], model_version, dataset_version,
    # threshold_version, latency_ms, timestamp
```

Bands come from `ml/configs/model.yaml`; below the LOW band the API answers
*inconclusive — retake/review advised*. The worker (`backend/app/workers/`) calls this module;
the API never loads model weights directly.

## 6. Explainability stage (Phase 3)

Grad-CAM over the last conv block (pytorch-grad-cam or in-house), saved as an overlay image.
UI text is fixed and honest: *"Highlighted regions indicate areas that contributed strongly to
the model's prediction. They are not a guarantee of disease location."*

## 7. Versioning & reproducibility

Every prediction carries model name/version, dataset version, threshold version and timestamp
(spec §51) joined to the `model_versions`/`dataset_sources` tables (Phase 5) and to files under
`data/` via the provenance records above. Any reported metric must be reproducible from
`seed + taxonomy + manifest + checkpoint sha256`.

## Changelog

- v0.1 (2026-08-08): data stage implemented + future stage contracts written (Phase 2).
