# 10 — Endorsement Evidence Map (Innovator Founder)

**Prepared:** 2026-09-28 · **Purpose:** give an endorsing body a one-page, click-verifiable
trail from each criterion to evidence. **Rule:** the status column tells the truth —
`✅ exists` means verifiable today; `🔄 planned` means exactly that, no blurring.

Criteria wording source: [GOV.UK endorsing-bodies guidance](https://www.gov.uk/government/publications/scale-up-and-innovator-founder-visa-endorsing-bodies-guidance/innovator-founder-and-scale-up-visas-guidance-for-endorsing-bodies-accessible) (accessed 2026-09-28).

## 1. Innovation — "genuine, original business plan… competitive advantage"

| Claim | Evidence (click-verifiable) | Status |
|---|---|---|
| Working product, not slideware | Public live demo (URLs in `README.md` / `docs/12`) — sign up, analyse, review zones, export a PDF | ✅ |
| Honesty-first workflow is genuinely differentiated | Calibrated bands + abstention; PENDING/APPROVED/REJECTED zone ledger; evidence PDF printing limitations on its face — code + tests in this repo | ✅ |
| Real ML with published honest evaluation | Model card (`docs/06`) + evaluation reports (`reports/`) — in-domain 0.9959 **and** PlantDoc OOD 0.2349 quoted together everywhere | ✅ |
| Open, original implementation | Full source + 16 engineering docs + CI with 249 automated tests | ✅ |

## 2. Viability — "realistic and achievable based on available resources"

| Claim | Evidence | Status |
|---|---|---|
| Founder can deliver solo | Phases 0–14 designed, built, tested, deployed, documented by one person — commit history | ✅ |
| Costs understood and near-zero at validation stage | Deployment doc (`docs/12`) with free-tier limits stated; cost build-up at [07 §4](07-financial-model.md) | ✅ |
| Financial projections credibly defensible | Scenario model with every assumption tagged and attackable ([07](07-financial-model.md)) | ✅ |
| Credible demand path | Loss/damage figures (FAO, UKFSR) + UK market sizing with named sources ([03](03-market-research.md)) + 30-interview validation plan with a published decision rule ([06](06-pricing-validation.md)) | ✅ (plan); 🔄 (interview evidence, Phase 15+) |
| Founder market awareness | Competitor landscape with sourced claims incl. where we are weaker ([04](04-competitor-landscape.md)) | ✅ |
| Investment/funds evidence | No fixed minimum applies; founder-funded validation budget + £1,270 maintenance requirement noted ([05 §1](05-uk-strategy.md)) — **bank statements prepared at application** | 🔄 personal docs at application |

## 3. Scalability — "structured planning, job creation, national/international growth"

| Claim | Evidence | Status |
|---|---|---|
| Structured growth plan | Phased roadmap (`docs/14`) completed publicly to date; GTM phases A/B/C ([01 §5](01-business-plan.md)) | ✅ |
| Software scalability (no inventory/hardware) | Architecture docs (`docs/02`); free→paid infra path costed ([07](07-financial-model.md)) | ✅ |
| UK job creation | Hire plan: agronomist (m~14), engineer (m~18), CS/field-data (year 2) ([05 §4](05-uk-strategy.md), [07 A8/A9](07-financial-model.md)) | 🔄 plan, dated |
| International scope | Product already serves a public URL; model taxonomy crop-agnostic by design; India field-validation context documented ([05 §7](05-uk-strategy.md)) | ✅ (capability); 🔄 (UK revenue first) |
| Projections based on credible research | All market figures sourced with links/dates ([03](03-market-research.md)); assumptions isolated ([07 A1–A9](07-financial-model.md)) | ✅ |

## 4. Application-readiness checklist (honest)

| Item | Status |
|---|---|
| Business plan + this package | ✅ (this directory) |
| Live product + walkthrough script | ✅ live; 🔄 Phase 15 demo script polish |
| Endorsing bodies re-verified from the live GOV.UK list | 🔄 at application (list changes) |
| UK company incorporation | 🔄 post-endorsement step (see [05 §3](05-uk-strategy.md)) |
| Trademark filing | 🔄 at incorporation ([08](08-data-ip-strategy.md)) |
| Personal maintenance evidence (£1,270/28 days) + English B2 | 🔄 personal documents at application |
| Contact-point meeting readiness (quarterly actuals published into 07 §7) | ✅ mechanism; 🔄 first quarter of actuals |

## 5. What this map deliberately does not contain

No claimed traction, revenue, users, partnerships, grants, or endorsements. If any appear
here later, they will arrive with a date and a link — the same rule the deployment log
already follows.
