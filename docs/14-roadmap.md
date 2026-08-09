# 14 — Development Roadmap

**Status as of 2026-08-09: Phases 0–5 complete.** Phases map 1:1 to the master spec (§73).
Rule: after every phase → run tests, fix errors, update README + docs, commit, explain what was
built and how to test it. Do not skip ahead.

## Phase plan

| Phase | Scope | Exit criteria | Status |
|------:|-------|---------------|:------|
| **0** | Requirements & architecture; dataset research; repo init | PRD v0.1, architecture v0.1, dataset register verified, roadmap, initial README, git history started | ✅ done 2026-08-08 |
| **1** | Repository & runnable architecture | `docker compose up` serves: Next.js landing (+route stubs) on :3000, FastAPI `/health` + `/docs` on :8000, worker + Postgres up; `/supported-crops` + `/model-info` report honest "NOT_TRAINED"; CI (ruff, pytest, eslint, tsc, next build, docker compose config + build) green; README quickstart verified | ✅ done 2026-08-08 |
| **2** | Dataset pipeline | Download scripts (PlantVillage, PlantDoc) with PROVENANCE.json; **license re-check done (Mendeley page fetched live → CC0 1.0 confirmed; PlantDoc CC BY 4.0 LICENSE fetched verbatim)**; deterministic 70/15/15 splits, seed 42 recorded; taxonomy + model config in `ml/configs/`; stats report in `reports/datasets/`; leakage verify + 18 unit tests green | ✅ done 2026-08-08 |
| **3** | ML baseline | MobileNetV3-Small transfer trainer (config-driven, seed/versions embedded, runs write metrics.json + sha'd checkpoint); inference `Predictor` with bands from `model.yaml`, INCONCLUSIVE gate, normalized-entropy uncertainty, Grad-CAM overlay + region/severity proxy; sample checkpoint generator (gitignored); 37 ml tests green | ✅ done 2026-08-08 |
| **4** | ML evaluation | `ml/evaluation/` pipeline driving the shipped Predictor over the held-out test split + PlantDoc OOD (auto-discovered, NOT_RUN-honest when absent); REPORT.md + summary.json + confusion PNGs + Grad-CAM exemplars + latency p50/p95 generated to `reports/model_evaluation/`; model card v1 + data card v1 published; 54 ml tests green. **Formal M1 gates measured on operator CPU 2026-08-09 vs run 20260808-180238-0.1.0: in-domain top-1 PASS 0.9959 · CPU latency PASS 110.4 ms p95 · PlantDoc OOD SHORTFALL 0.2349 (model card §4.2)** | ✅ 2026-08-09 |
| **5** | Backend core | FastAPI: 14-table schema (auth-ready `users`/`requested_by`) with Alembic migration `0001` (+ upgrade/downgrade/upgrade test); uploads pipeline (streaming size cap, **magic-byte** sniffing, declared/magic mismatch 400, Pillow verify, EXIF-orientation normalize + GPS-capture note only, JPEG re-encode + 384px thumbnail, sha256 dedupe); DB-backed analysis queue (ADR-004: claim/heartbeat/attempts²-backoff/stale-reap; SKIP LOCKED on Postgres) + worker (separate torch-carrying container; `MODEL_CHECKPOINT` unset → clearly-flagged DEMO sample model, checkpoints mounted via `./runs:/runs`); `/images` `/analyses` `/predictions` APIs shipping the predictor contract verbatim (phrasing/bands/INCONCLUSIVE/regions/raw_json; demo flags never silent); `dataset_sources` seeded from the registry (counts measured-only, `verified_at` pending); observability (request IDs, audited writes, `/health` `/health/ready`); docs/04-api-design.md; **47 backend tests green** (uploads/queue/analysis-flow/predictions/schema+alembic/seed + existing health/meta) | ✅ 2026-08-09 |
| **6** | Frontend core | Real app routes — `/dashboard` (live counts + model-truth strip), `/analyze` (upload→analysis wizard: 25 MB precheck, magic-bytes honesty note, farm/field pickers, dedupe surfaced, STATUS polling), `/analyses` history (status filter, failures kept visible), `/analyses/{id}` (verbatim phrasing + bands + INCONCLUSIVE explainer + Grad-CAM figure + raw contract), `/farms` + `/farms/{id}` CRUD (delete-409 counts surfaced), `/model-information` (live registry: bands, 21 conditions, `model_available:false` footnote). Browser-side API client (typed; ApiError unwraps backend honesty payloads; network failure never invents a status). New backend surface: farms/fields CRUD (`crop_id` taxonomy-validated), analyses list + filter, Grad-CAM download; migration `0002` (farm owner nullable pre-auth). Chips/text always accompany colour (a11y); polling aria-live. **61 backend + 112 ml tests, 31 vitest component tests, eslint + tsc + next build green** | ✅ 2026-08-09 |
| **7** | Geospatial mapping | `/map` (Leaflet/OSM): user-drawn WGS84 field boundaries validated client+server (closed ring, lon/lat ranges — the ONLY geography, since image GPS is privacy-stripped at upload); intervention zones generated per SUSPECTED analysis in **evidence space** (`image-normalized-xyxy`, `georeference_source: "none"` — never invented locations), INCONCLUSIVE analyses get none by design; risk = documented deterministic rule (band + severity proxy), priority 1–4; review PATCH with audited OLD→NEW transitions + kept-on-regenerate guarantee; Sim-labelled GeoJSON/CSV exports (filename + body); decision-support strip ("review order, not an agronomic risk score"); SVG image-space zone overlays on stored imagery; migration `0003`. **71 backend + 112 ml pytest, 47 vitest, eslint/tsc/next build green** | ✅ 2026-08-09 |
| **8** | Intervention simulator | `simulation/` drone + spray simulators behind provider Protocols; interactive spray sim UI (field size, zones, spray width, speed → route, treated/untreated area, time); savings calculator — all labelled **SIMULATION** | ⬜ |
| **9** | Reports | ReportLab PDF field report (all spec fields + limitations + review status + report ID); `/reports/{id}/download`; report tests | ⬜ |
| **10** | Auth & roles | JWT register/login/logout, bcrypt, roles (FARMER/AGRONOMIST/ADMIN), protected routes frontend+API, feedback capture flow, admin panel v1, audit logging, rate limiting; auth/integration tests | ⬜ |
| **11** | Testing hardening | e2e critical flow (register→…→report) in CI; security doc; privacy doc; THIRD_PARTY_LICENSES.md; testing doc; coverage targets documented honestly | ⬜ |
| **12** | Deployment | Free-tier deploy (frontend Vercel; backend+DB Render/Supabase or documented alternative) with **deploy date + fallback notes**; deploy doc; demo URL recorded; app still fully runnable locally | ⬜ |
| **13** | Documentation completion | Full numbered doc set (01–16) finalized incl. user guide, limitations, responsible-AI; README "exceptional" pass with real screenshots; API design doc synced with implementation | ⬜ |
| **14** | Business package | business/ documents: plan, lean canvas, markets, competitors (sourced), UK strategy, pricing ("indicative for validation"), financial model w/ sourced assumptions, data/IP strategy, risk register; endorsement/ evidence framework with honest placeholders only | ⬜ |
| **15** | Demo preparation | Demo mode polish (3–5 samples, sample data labelled); 3-min demo script; 3–5 min end-to-end walkthrough rehearsed; pitch-deck outline; final acceptance checklist sweep | ⬜ |

## Milestones

- **M1 — Vertical slice (end of Phase 4):** image → prediction + explainability + severity + version + PDF, with honest eval numbers. See PRD §6 for quantitative gates.
- **M2 — Product slice (end of Phase 10):** full authenticated workflow w/ maps, zones, simulator, reports, feedback.
- **M3 — Presentable MVP (end of Phase 15):** demo URL, acceptance checklist green, evidence framework ready for real validation data.

## Product roadmap (post-MVP, from spec §62)

1. Computer-vision MVP ← *this roadmap*
2. Pilot testing with real farms (evidence replaces placeholders)
3. Human-verified agricultural dataset (feedback loop → versioned data)
4. Improved disease/pest models (incl. pest module if IP licensing resolved)
5. Drone integration (real `DroneProvider` adapter; hardware partners)
6. Real precision-spraying integration (`SprayingMachineProvider` adapter)
7. Multi-crop expansion (UK-relevant crops first)
8. UK commercial pilots
9. International expansion
