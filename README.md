# CropMind AI

<p>
  <img src="docs/assets/logo.svg" alt="CropMind AI logo" width="56" height="56" align="left" />
  <strong>See the problem before you spray the field.</strong><br/>
  CropMind AI converts crop-health imagery into explainable, geospatially localized
  intervention zones for precision crop protection — helping farmers and agronomists
  review suspected issues and target treatment areas instead of blanket-spraying whole fields.
</p>

<br clear="left"/>

![CI](https://github.com/Vishwa-cloud25S/cropmind-ai/actions/workflows/ci.yml/badge.svg)

> **Status: Phases 0–4 done — formal M1 gates measured 2026-08-09 (Gate C, operator CPU).**
> Baseline run `20260808-180238-0.1.0`: in-domain held-out top-1 **0.9959** ✅ (≥ 0.80) ·
> CPU latency **110.4 ms p95** ✅ (≤ 2,500 ms) · PlantDoc field OOD top-1 **0.2349** 🔶
> (SHORTFALL vs 0.50 target — published as-is; both accuracy numbers travel together, always).
> Details: docs/06-model-card.md §4.2.
> The stack boots today (API + worker + frontend + Postgres), the landing page and API health/
> model-truth endpoints are live, and CI runs lint + typecheck + tests + docker builds.
> See [`docs/14-roadmap.md`](docs/14-roadmap.md) for the phase plan and what lands next.

---

## What it is

A full-stack precision-agriculture MVP:

smartphone/drone image → AI detection → confidence & uncertainty → localization →
severity estimate → explainability → field/GPS mapping → precision intervention zones →
estimated input-savings simulation → human review → PDF field report.

## What it is not (honest scope)

- It does **not** diagnose with certainty — every output is a *suspected* condition with a confidence score.
- It does **not** prescribe pesticide products, brands, or dosages. Decision support only; a farmer/agronomist must verify.
- Estimated savings are **model-based simulations**, not field-validated results.
- V1 supports a small, explicit set of crops/conditions (see *Supported crops* once Phase 3 lands) — not every crop disease.
- The drone/spraying workflow is **simulated**. No hardware is required or controlled.

## Repository layout

```
cropmind-ai/
├── backend/          # FastAPI + SQLAlchemy 2 + Alembic (Phase 1, 5, 10)
├── frontend/         # Next.js + TypeScript + Tailwind + Leaflet (Phase 1, 6, 7)
├── ml/               # data / preprocessing / training / evaluation / inference /
│                     # explainability / models / configs / notebooks
├── data/             # raw / processed / annotations / splits  (never committed)
├── simulation/       # drone + precision-spray simulators (Phase 8)
├── docs/             # product, architecture, datasets, model/data cards, roadmap
├── business/         # business plan, market, pricing, financial model (Phase 14)
├── endorsement/      # evidence package for Innovator Founder Visa (Phase 14)
├── reports/          # generated model-evaluation reports
└── .github/          # CI workflows (Phase 1)
```

## Quickstart

Requires Docker (everything: frontend, API, worker, Postgres):

```bash
cp .env.example .env          # local dev defaults, no secrets needed for local
docker compose up --build
```

- Web app → http://localhost:3000
- API + OpenAPI docs → http://localhost:8000/docs
- `GET /health`, `GET /health/ready`, `GET /supported-crops`, `GET /model-info`

Local dev without Docker (needs local Postgres for `/health/ready` to go green):

```bash
cd backend  && python -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
uvicorn app.main:app --reload          # → :8000

cd frontend && npm install && npm run dev   # → :3000
```

Tests and lint:

```bash
cd backend  && python -m pytest -q && ruff check .
cd frontend && npm run lint && npm run typecheck && npm run build
cd ml       && python -m pytest -q
```

## Dataset setup (Phase 2 pipeline)

Public, licensed datasets — never committed to git
(see [`docs/datasets.md`](docs/datasets.md) for the audited license register and
Windows PowerShell instructions):

**PlantVillage (CC0)** — the authoritative source currently refuses automated clients
(HTTP 403), so use the manual route: download
[`Plant_leaf_diseases_dataset_without_augmentation.zip`](https://data.mendeley.com/datasets/tywbtsjrjv/1)
(~828 MB) in your browser, then:

```bash
python -m ml.data.cli import --dataset plantvillage --archive <path-to-zip> --accept-license
python -m ml.data.cli split --dataset plantvillage && \
python -m ml.data.cli verify --dataset plantvillage && \
python -m ml.data.cli stats --dataset plantvillage
```

Already-extracted folder instead? `--directory <path>` verifies it in place (no copy).

**PlantDoc (CC BY 4.0)** — automated route works:

```bash
pip install -r ml/requirements.txt
python -m ml.data.cli pipeline --dataset plantdoc --accept-license
```

Every route enforces the license gate, structural verification, `PROVENANCE.json`
(source, DOI, license, access date, acquisition method, checksums), deterministic 70/15/15
splits (seed 42, recorded), leakage checks, and `reports/datasets/*-stats.md`.

## Train / run the model (Phase 3 pipeline)

```bash
pip install -r ml/requirements.txt

# 1) Generate the sample checkpoint (pipeline plumbing; synthetic data; gitignored).
python -m ml.training.sample_model
#    Lets you exercise inference + explainability without a GPU or the real dataset.

# 2) Real training run (after `ml.data.cli import + split). CPU or CUDA via `device: auto`;
#    designed for free Colab/Kaggle GPU. Every run writes runs/<run_id>/ {config, metrics.json,
#    checkpoint.pt, checkpoint.sha256}.  Free-GPU route: notebooks/train_colab.ipynb.
python -m ml.training.train --config ml/configs/train_v1.yaml

# 3) Evaluation report (Phase 4): held-out + PlantDoc OOD, per-class P/R/F1, confusion matrices,
#    Grad-CAM exemplars, latency p50/p95, M1 gate table — generated, never hand-edited.
python -m ml.evaluation.cli report --run-dir runs/<run_id> --device cpu
```

Every prediction from `ml/inference/predictor.py` carries confidence band (from
`ml/configs/model.yaml` — never hardcoded), uncertainty, estimated visual severity, Grad-CAM
overlay, and model/dataset/threshold versions; below the LOW band the answer is **INCONCLUSIVE**
with retake/review advice. The sample model may say INCONCLUSIVE a lot — that's the honesty gate
working, not a bug.

## Product principles (non-negotiable)

1. Open source and publicly licensed data first; no paid APIs where avoidable.
2. Distinguish *experimentally validated results* from *estimates* everywhere in UI and docs.
3. Never fabricate efficacy claims, metrics, customers, interviews, approvals, or testimonials.
4. Store confidence, uncertainty, model version and dataset provenance for every prediction.
5. Human review is part of the workflow by design.
6. Runnable locally without paid cloud services, with a free-tier deployment path.

## Documentation

| Doc | Status |
|---|---|
| [01 — Product requirements](docs/01-product-requirements.md) | ✅ Phase 0 |
| [02 — System architecture](docs/02-system-architecture.md) | ✅ Phase 0 |
| [Datasets & license register](docs/datasets.md) | ✅ Phase 0 |
| [14 — Development roadmap](docs/14-roadmap.md) | ✅ Phase 0, updated through Phase 4 |
| [Taxonomy & model config](ml/configs) — what the model does/doesn't support | ✅ Phase 1 (live via `/supported-crops`, `/model-info`) |
| [05 — ML pipeline](docs/05-ml-pipeline.md) · [06 — Model card](docs/06-model-card.md) · [07 — Data card](docs/07-data-card.md) | ✅ Phases 3–4 (v1; formal gates measured from the operator's eval report) |
| API, security, privacy, testing, deployment, user guide, limitations, responsible-AI | Planned (Phases 5–13 per roadmap) |

## License

Source code license to be confirmed by the founder before public release (default candidate: MIT).
Datasets are **not** redistributed by this repository; each retains its own license — see
[docs/datasets.md](docs/datasets.md). Third-party dependency licenses will be tracked in
`THIRD_PARTY_LICENSES.md` (Phase 11).
