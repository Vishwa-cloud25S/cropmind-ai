# 14 — Development Roadmap

**Status as of 2026-08-08: Phase 0 complete.** Phases map 1:1 to the master spec (§73).
Rule: after every phase → run tests, fix errors, update README + docs, commit, explain what was
built and how to test it. Do not skip ahead.

## Phase plan

| Phase | Scope | Exit criteria | Status |
|------:|-------|---------------|:------|
| **0** | Requirements & architecture; dataset research; repo init | PRD v0.1, architecture v0.1, dataset register verified, roadmap, initial README, git history started | ✅ done 2026-08-08 |
| **1** | Repository & runnable architecture | `docker compose up` serves: Next.js landing (+route stubs) on :3000, FastAPI `/health` + `/docs` on :8000, worker + Postgres up; `/supported-crops` + `/model-info` report honest "NOT_TRAINED"; CI (ruff, pytest, eslint, tsc, next build, docker compose config + build) green; README quickstart verified | ✅ done 2026-08-08 |
| **2** | Dataset pipeline | Download scripts (PlantVillage, PlantDoc) with PROVENANCE.json; **license re-check done (Mendeley page fetched live → CC0 1.0 confirmed; PlantDoc CC BY 4.0 LICENSE fetched verbatim)**; deterministic 70/15/15 splits, seed 42 recorded; taxonomy + model config in `ml/configs/`; stats report in `reports/datasets/`; leakage verify + 18 unit tests green | ✅ done 2026-08-08 |
| **3** | ML baseline | MobileNetV3-Small transfer baseline trained on PlantVillage subset; inference module with confidence bands from `model.yaml`; Grad-CAM overlay; visual-severity proxy; sample checkpoint for demo (not in git); inference unit tests | ⬜ |
| **4** | ML evaluation | Held-out + PlantDoc out-of-domain eval; per-class P/R/F1, confusion matrix, latency; auto-generated `reports/model_evaluation/`; model card v1 + data card v1; **M1 vertical-slice gates measured** | ⬜ |
| **5** | Backend core | FastAPI: auth-ready schema, 14-table Alembic migration, uploads pipeline (validation, thumbnails, EXIF), analysis job queue + worker, `/images`, `/analyses`, `/predictions` wired to real ML module; observability (request IDs, `/health`); API tests | ⬜ |
| **6** | Frontend core | Landing, dashboard, farms/fields CRUD, upload flow, analysis view (prediction + confidence + Grad-CAM + severity), history; design tokens (light agro-industrial, no gradient soup); accessibility pass on core flows; component tests | ⬜ |
| **7** | Geospatial mapping | Leaflet/OSM field map; boundary drawing; detection regions overlay; intervention-zone generation, approve/reject; GeoJSON/CSV export ("simulation"-labelled); decision-support panel (risk level, review priority) | ⬜ |
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
