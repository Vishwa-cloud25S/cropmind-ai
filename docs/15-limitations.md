# 15 — Known Limitations

**Status:** ✅ Phase 13 (2026-09-28) — final
**Read with:** [06 — Model card](06-model-card.md), [16 — Responsible AI](16-responsible-ai.md), [12 — Deployment](12-deployment.md)

This register exists because precision-agriculture software fails *dangerously* when its
limits are implicit. Every limitation below is also disclosed where a user meets it
(UI labels, payload fields, PDF sections). If a limitation here is wrong or missing, that
is a bug — file it like one.

---

## 1. Model limitations (measured, not asserted)

| # | Limitation | Evidence / numbers | Consequence for users |
|---|---|---|---|
| M1 | **Domain gap.** Trained on PlantVillage *lab-style* leaf imagery; real field photos behave differently | In-domain held-out top-1 **0.9959**; PlantDoc field OOD top-1 **0.2349** (SHORTFALL vs 0.50 target — published as-is in the [model card](06-model-card.md) §4.2; the two numbers always travel together) | Field photos will hit INCONCLUSIVE or errors more often; treat output as triage, not diagnosis |
| M2 | **Closed world.** 4 crops × 21 conditions only (taxonomy v0.3: tomato, potato, corn, apple) | `/supported-crops` is the live truth | Anything outside is honestly unsupported — never silently guessed |
| M3 | **Severity is a visual proxy.** `estimated_visual_severity` = Grad-CAM area ratio, an experimental heuristic | Labelled "Estimated visual severity" everywhere; config documents the intended replacement | Do not plan treatment intensity from it |
| M4 | **Localization is interim.** `gradcam_threshold_regions` until a detector is trained (ADR-005); PlantDoc boxes are whole-leaf | Payload `coordinate_space`, docs/02 | Regions approximate *where the model looked*, not verified lesion boundaries |
| M5 | **Single-leaf framing.** No plant/canopy/field-level fusion; one image per analysis | Architecture (docs/02) | A healthy-looking leaf does not clear the block; INCONCLUSIVE ≠ healthy |
| M6 | **No calibration guarantee per class.** Confidence bands are global config, applied uniformly | `ml/configs/model.yaml` | Band = communication aid, not a per-class probability guarantee |
| M7 | **Latency measured on one operator machine** | CPU 110.4 ms p95 (eval report; hardware recorded in docs/08) | Your hardware will differ; re-measure before capacity claims |

## 2. Data limitations

- **Single training source** (PlantVillage, CC0) → lab-condition bias dominates (M1 is the measured symptom).
- **No farmer/user data in training.** Feedback is stored for gated future evaluation only; nothing auto-retrains (docs/08 pipeline or nothing).
- **No independent external validation** of the model by any third party, ever claimed.
- Provenance, splits, and leakage checks are reproducible (deterministic seed 42, recorded) — see [07 — Data card](07-data-card.md).

## 3. Product / geospatial limitations

- **Zones are not geo-referenced.** Photo GPS is privacy-stripped at upload; zones live in
  image space with `georeference_source: "none"`; `est_area_ha` is null when scale is
  unknowable. Anything else would be invented precision.
- **Simulations are labelled arithmetic**, not field-validated savings. No input-rate
  suggestion exists anywhere. No hardware (drone/sprayer) is integrated or controlled.
- **No offline mode**; intermittent-connectivity realities (P1 persona) are not yet addressed.
- **English-language UI only** — an acknowledged adoption barrier for the primary persona.
- Review "risk levels" are a **deterministic display rule**, explicitly *not* an agronomic
  risk score.

## 4. Platform / deployment limitations

| # | Limitation | Where documented |
|---|---|---|
| P1 | **Amended 2026-09-28 (AD-009):** the public deployment may serve the real checkpoint delivered out-of-band (weights still never travel via git/image; fetched at runtime from a private repo — runbook docs/12 §8). Which weights serve is always public at `/model-info` → `serving.weights_origin`, and every prediction/report carries its true weight identity: sample = DEMO banner; real weights via the demo path = DEMO TRIAL banner with both evaluation figures. Before 2026-09-28 the public demo ran the DEMO sample model only — plumbing evidence, never performance | docs/12 §1 + §8, model card |
| P2 | **Free-tier hosting**: instance sleeps after ~15 min idle (~1 min cold start, client retries honestly); 512 MB RAM ceiling with a measured-tight demo stack and a documented paid fallback; demo Postgres is size- and lifetime-limited | docs/12 §2, §5 |
| P3 | **Single-process demo topology** collapses API+worker into one container (ADR-004 split stays in local/production compose); no horizontal scaling, no multi-instance rate limiting (in-memory store seam is single-node) | docs/12 §1, docs/09 |
| P4 | **JWT in `localStorage`** is XSS-readable; mitigations (server-side revocation, 12 h expiry, proactive expiry) documented — the API is the enforcement boundary | docs/04 §3.10, docs/09 |
| P5 | **No penetration test, no uptime SLO, no backup schedule** on the demo deployment; audit log is in the same database as the data | docs/09 (own it, don't hide it) |

## 5. Business / evidence limitations

- No customers, interviews, revenue, or field trials exist or are claimed. Any business
  document (Phase 14) marks projections as *indicative for validation* with sourced
  assumptions, and placeholders stay placeholders.
- The personas in docs/03 are design hypotheses, plainly labelled unvalidated.

## 6. What would be required before any production/field claim

1. An agronomist-labelled **field-condition dataset** for the target geography, with a gated
   re-evaluation (docs/08) — OOD number must move honestly, not by threshold tuning.
2. **Independent field trials** before any efficacy/savings statement (changing the M1/registry
   facts and the model card, in the open).
3. Regulatory review with qualified agronomists before anything resembling prescription
   support; chemical guidance remains out of scope regardless.
4. Security: third-party pen test, production secrets/backup/DR plan, multi-instance rate
   limiting and audit shipping.
5. Real detector training (ADR-005 path) before presenting regions as lesion polygons.

Until then, the product is — and presents itself as — an **honest, open-source MVP and
evidence package**, not a validated agronomic product.
