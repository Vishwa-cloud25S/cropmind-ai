# 01 — Business Plan

**Prepared:** 2026-09-28 · **Author:** Vishwa Odduri · **Companion detail:** market sizing in [03](03-market-research.md), competitors in [04](04-competitor-landscape.md), finances in [07](07-financial-model.md), risks in [09](09-risk-register.md).

## 1. Executive summary

CropMind AI is an open-source precision-agriculture web product that turns leaf and field
imagery into **explainable, reviewable intervention zones**. A trained vision model reports
*Suspected* conditions with calibrated confidence bands and abstains when unsure; zone
review stays with humans; no chemical product or dosage advice exists anywhere in the
product by design.

**What already exists (verifiable today):** a working MVP with a public live demo, a
trained and honestly evaluated model (in-domain held-out top-1 **0.9959** and PlantDoc
field out-of-distribution top-1 **0.2349**, always quoted together — see
`docs/06-model-card.md`), PDF field reports with a human-review ledger, a spray-planning
simulator, auth/roles/audit, CI with 249 automated tests, and a complete 16-document
engineering set. It was built solo and deployed on free tiers.

**The business:** UK-first SaaS for growers and agronomists, expanding from a focused
potato/arable wedge, with India as field-validation context. Pre-incorporation; target
is UK endorsement under the Innovator Founder route (see [05](05-uk-strategy.md)).

## 2. Problem

- The FAO estimates **up to 40% of global crop production is lost to pests annually**;
  plant diseases alone cost the global economy **over $220 billion per year**
  ([FAO, 2021](https://www.fao.org/newsroom/detail/Climate-change-fans-spread-of-pests-and-threatens-plants-and-crops-new-FAO-study/en)).
  The UK's own Food Security Report repeats the 20–40% figure
  ([GOV.UK, 2021](https://www.gov.uk/government/statistics/united-kingdom-food-security-report-2021/united-kingdom-food-security-report-2021-theme-1-global-food-availability)).
- Crop protection is consequently applied **uniformly across whole fields** because growers
  cannot see precisely where the problem is — over-application costs money and accelerates
  resistance; under-application loses yield.
- Existing tools either give a bare app-style verdict with no review trail (see Plantix in
  [04](04-competitor-landscape.md)) or target enterprise budgets. The missing product is a
  **decision-support workflow**: honest confidence, reviewable zones, printable evidence.

## 3. Product

| Capability | State (2026-09-28) |
|---|---|
| Image analysis with confidence bands + abstention (INCONCLUSIVE below LOW) | Live |
| Real model served publicly via out-of-band delivery (AD-009, `docs/12 §8`) | Live (one-time operator step) |
| Grad-CAM explainability overlays with stated caveats | Live |
| Field/farm management with drawn boundaries (Leaflet + OSM) | Live |
| Intervention zones as reviewable simulations (PENDING/APPROVED/REJECTED ledger) | Live |
| PDF field reports (suspected phrasing verbatim, demo/limits printed on the document) | Live |
| Spray-route simulator (exact polygon areas, honest assumptions printed) | Live |
| Auth, roles, per-account scoping, audit log, rate limiting | Live |
| Drone/provider integrations, detector-based localization, field-scale georeferencing | Roadmap (documented simulators only) |

Every surface labels simulation/demo status; every accuracy claim carries both evaluation
figures. This honesty is the product's differentiator, not a disclaimer bolted on.

## 4. Market (summary — full detail in [03](03-market-research.md))

- Global precision-agriculture market 2025 estimates range **$9.6–18.2B** across four named
  reports, growing at 6.6–15%/yr depending on scope `[source]`.
- UK precision-agriculture market ≈ **$0.42B (2025)**, ~7%/yr growth (Fortune Business
  Insights) `[source]`.
- UK structure: **209,000 holdings**, 17.0M ha utilised agricultural area, 6.17M ha
  croppable, **118k ha potatoes**, ~1.5M ha wheat (Defra, June 2024) `[source]`.
- Beachhead: UK potato growers + agronomists (late blight is a pressure every season);
  CropMind's current model already covers tomato, potato, corn, apple (21 conditions).

## 5. Go-to-market (UK-first)

1. **Phase A (validation, months 0–6):** free public product + 30 structured interviews
   with UK agronomists and potato growers (pricing test in [06](06-pricing-validation.md));
   feedback loop already built into the product (per-analysis feedback widget + admin triage).
2. **Phase B (paid pilots, months 6–18):** paid agronomist tier (multi-farm review
   workflow), 3–5 pilot accounts; publish pilot evidence honestly (what worked, what didn't).
3. **Phase C (scale, months 18–36):** co-op/adviser channel partnerships; detector-based
   localization and field georeferencing unlock per-hectare value pricing.

## 6. Operations

- **Founder:** Vishwa Odduri, solo — engineering, ML, deployment and documentation to date
  (verifiable: commit history, CI, deployment log).
- **Infrastructure:** free tiers today (Vercel + Render + managed Postgres); documented
  limits (cold starts, 512 MB, 30-day DB cycle) and a costed upgrade path (see [07](07-financial-model.md)).
- **Open source as go-to-market:** the repository itself is the credibility engine;
  business documents included (this package).
- **Compliant by construction:** no pesticide advice (regulatory boundary avoided by
  design — see [05 §5](05-uk-strategy.md)); UK GDPR posture in [08](08-data-ip-strategy.md).

## 7. Financial summary (assumptions in [07](07-financial-model.md))

- Today: **£0 revenue, ~£0 monthly infrastructure cost** (free tiers).
- Base case reaches ~£9k MRR at month 30 with ~£85k cumulative external funding need
  `[assumption — scenario, not forecast]`.
- Funding: bootstrapped validation → pre-seed/grant for pilots (options in [05 §6](05-uk-strategy.md)).

## 8. Risks (register in [09](09-risk-register.md))

Top three, honestly: (1) field/OOD performance gap is real (0.2349) — mitigated by
abstention, human review, and targeted field data; (2) solo-founder key-person risk —
mitigated by open, reproducible everything; (3) UK agritech funding "valley of death"
(Small Robot Company, 2024) — mitigated by software-only, near-zero burn.

## 9. Milestones

| Date (target) | Milestone | Evidence |
|---|---|---|
| 2026-08 to 09 | Phases 0–14: product, deployment, docs, business package | This repo (done) |
| 2026 Q4 | Phase 15 demo prep; endorsing-body application submitted | docs/14 roadmap |
| 2027 H1 | UK incorporation (post-endorsement), 30 validation interviews | Interview log |
| 2027 H2 | 3–5 paid pilots (agronomist tier) | Pilot agreements |
| 2028 | Co-op channel + detector localization release | Release notes |

## 10. Why this wins endorsement criteria (map in [10](10-endorsement-evidence-map.md))

- **Innovative:** honesty-first decision-support workflow (calibrated abstention +
  reviewable zones + evidence PDFs) in a market of bare verdict apps — and it already runs.
- **Viable:** built and deployed by the founder alone on free tiers; costs understood;
  plan matches available resources.
- **Scalable:** pure software, no inventory/hardware, self-serve onboarding, international
  market, UK job-creation path (first agronomist, first engineer).
