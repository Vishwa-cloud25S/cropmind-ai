# Final acceptance sweep (Phase 15) — evidence-mapped, honestly marked

**Date:** 2026-09-28 · **Scope:** every FR/NFR in `docs/01-product-requirements.md` and every
item in its §7 master checklist. **Legend:** ✅ shipped & evidenced · 🔄 shipped with a
recorded honest caveat · ⬜ not shipped (with the reason).

**Deployment under test:** frontend `https://cropmind-ai-theta.vercel.app` · API
`https://cropmind-demo-api.onrender.com` · real model **v0.1.0 serving in production**
via integrity-pinned out-of-band delivery (AD-009, executed 2026-09-28 12:20 UTC).
**Gate state at this sweep:** backend **152 passed + 3 live-only** (the 3 `live`-marked
tests below ran green against production), ml **113 passed**, simulation **10 passed**,
frontend **88/88 vitest**, eslint `--max-warnings 0` clean, `tsc --noEmit` clean,
`next build` clean, ruff clean (`backend ml simulation`).

## Functional requirements

| ID | Verdict | Evidence |
|----|:---:|---|
| FR-01 auth | ✅ | `backend/app/api/v1/auth.py`; tests green; live reviewer account active |
| FR-02 roles | ✅ | FARMER/AGRONOMIST/ADMIN enforced; role tests; two live ADMIN accounts |
| FR-03 farm CRUD | ✅ | `/farms` API + FarmsManager UI; tests |
| FR-04 field CRUD + boundary | ✅ | map boundary drawing; area computed; shown on PDF ("Field area (drawn boundary)") |
| FR-05 upload | ✅ | validation + thumbnails + EXIF; **global content dedupe observed live** (honest 409; demo/rehearsal-notes.md) |
| FR-06 analysis jobs | ✅ | PENDING→PROCESSING→COMPLETED worker; live 4–38 s warm/cold cycle measured |
| FR-07 inference | ✅ | condition+confidence+uncertainty+model_version+latency on every prediction |
| FR-08 localization | 🔄 | heatmap-derived regions → boxes shipped; **detector head not trained** (docs/06, honestly deferred) |
| FR-09 severity | ✅ | experimental "Estimated visual severity" label everywhere incl. PDF |
| FR-10 Grad-CAM | ✅ | overlay + caveat caption ("not a disease-location guarantee") in UI and PDF |
| FR-11 field map | ✅ | Leaflet: boundary, regions, zones, observations, toggles (Phase 7) |
| FR-12 zones | ✅ | generate/approve/reject + GeoJSON+CSV export labelled simulation; live ledger verified |
| FR-13 zone decision support | ✅ | risk/condition/confidence/est. area/review priority per zone |
| FR-14 savings calculator | ✅ | labelled "Simulation" (Phase 8) |
| FR-15 spray simulator | ✅ | route + treated/untreated area + time; `simulation/` suite 10/10 |
| FR-16 dashboard | ✅ | fields/analyses/issues/high-risk zones/charts (Phase 6) |
| FR-17 history + compare | ✅ | per-field history; field comparison view |
| FR-18 feedback | ✅ | YES/NO/NOT_SURE + actual condition + notes + image quality |
| FR-19 PDF report | ✅ | full ledger report; **verified live** — `CMA-20260928-9A9684`: banner, paired figures, verbatim 91%, sha-256 receipt, zone ledger |
| FR-20 demo mode | ✅ | **this phase** — no-account flow, 4 bundled labelled samples (`demo/media/`, `frontend/public/demo-samples/`), wizard picker, end-to-end live-tested |
| FR-21 admin panel | ✅ | users/analyses/model versions/feedback/datasets/reports/audit/health |
| FR-22 health/logging | ✅ | `/health`, request IDs, structured logs, inference timing (latency on PDF) |
| FR-23 audit log | ✅ | security-relevant events logged (Phase 10) |
| FR-24 model-info | ✅ | `/model-info` serving block live: `remote-checkpoint · downloaded · sha256-pinned` + evaluation pair; Model Truth panel renders from it |

## Non-functional requirements

| ID | Verdict | Evidence / honest note |
|----|:---:|---|
| NFR-01 local docker | ✅ | `docker compose up` path; CI docker job green |
| NFR-02 free deploy | ✅ | Vercel + Render; deploy log `docs/12-deployment.md` §7 (append-only), first deploy + flip dated |
| NFR-03 CPU latency | ✅ | p95 **110.4 ms** at training resolution on the eval rig; live demo adds free-tier queue reality (4–38 s) — both published, never blended |
| NFR-04 upload ceiling | ✅ | 25 MB default, configurable; dedupe behaviour documented |
| NFR-05 no secrets in git | ✅ | `.env.example` only; checkpoint+tokens out-of-band (AD-009); fine-grained PAT rotation practised 2026-09-28 |
| NFR-06 accessibility | 🔄 | semantic HTML + keyboard-reachable core flows shipped; **no formal WCAG audit yet** — recorded, not claimed |
| NFR-07 mobile responsive | ✅ | responsive dashboard/map (Phase 6+) |
| NFR-08 e2e critical flow | ✅ | Phase-11 e2e green in CI; Phase-15 `live`-marked trio re-proves it against production on demand |
| NFR-09 dataset-license gate | ✅ | `docs/datasets.md` + `/dataset-sources` seeding; demo samples provenance-pinned (CC0 / CC BY 4.0), redistribution narrowed to ≤5 attributed demo photos |

## docs/01 §7 master checklist — final state

| Item | Verdict | Evidence |
|---|:---:|---|
| App accessible; demo without account | ✅ | live URL; FR-20 bundle + rehearsal R1 |
| Upload → prediction + confidence + model version | ✅ | live verdicts `Suspected Tomato - Early blight - 91% confidence`, model v0.1.0 shown |
| Explainability + severity displayed | ✅ | Grad-CAM card + caveats; severity proxy labelled |
| Farm/field CRUD; analysis linked to field | ✅ | rehearsal field `1a6c103a…` (Tomato Block A) analyses |
| Map; zones approvable/rejectable; GeoJSON export | ✅ | flagship zone `f88528c5…` APPROVED with review note; PDF ledger |
| Simulation; PDF report; history; feedback; persistence | ✅ | report `CMA-20260928-9A9684` + earlier `CMA-20260928-2CDDF0`; history live |
| Auth + OpenAPI docs; tests pass in CI | ✅ | `/openapi.json` live; CI 4/4 green (backend/frontend/ml/docker) |
| README, deployment, model card, data card, responsible-AI | ✅ | docs/01–16 + LICENSE + README current |
| Business plan, pitch outline, financial model, endorsement framework | ✅ | `business/` 01–10 (placeholders honestly marked, 0 paying users, £0 revenue, pre-incorporation) |

## Known limits carried (never hidden)

1. **Field/OOD top-1 = 0.2349** — printed everywhere the 0.9959 in-domain figure appears.
2. **No leaf-gate**: synthetic non-leaf imagery can land a LOW-band guess at 25–45% (rehearsal R3); mitigations on record (abstain-below-LOW, OOD figure published, Phase-16+ pre-gate proposal).
3. **Free-tier reality**: cold worker ≈38–60 s; rehearsal notes prescribe a warm-up analysis before a live demo.
4. **Ephemeral demo disk**: pushes/restarts wipe stored media/PDFs; rows survive and admit "stored PDF missing — regenerate" honestly.
5. **Formal accessibility audit** not yet performed (NFR-06 🔄).
6. **Detector head** (FR-08 second half) untrained; localization is heatmap-derived and labelled as such.
