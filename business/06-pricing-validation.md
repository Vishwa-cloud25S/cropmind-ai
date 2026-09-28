# 06 — Pricing for Validation

**Prepared:** 2026-09-28 · **Everything on this page is indicative for validation —
nothing here is a real price, a commitment, or evidence of willingness to pay (0 paying
users today).** The 30-interview plan in §3 exists to replace these assumptions with evidence.

## 1. Indicative tiers `[assumption throughout]`

| Tier | Indicative price | For | Includes | Rationale anchor |
|---|---|---|---|---|
| **Community (free)** | £0 | Anyone | Public demo path + 1 farm, N analyses/mo `[cap TBD in interviews]` | Plantix is free for farmers — a paid wall at the door loses the segment before trust forms ([04](04-competitor-landscape.md)) |
| **Grower** | ~£19/mo | Single farm, self-scout | Unlimited own-farm analyses, zone review ledger, PDF evidence reports, season archive | Anchored "cost of one unnecessary blanket pass avoided" framing to **test**, not assert |
| **Agronomist** | ~£75/mo | Advisers, multi-farm | Everything + multi-farm review queue, priority triage, client-shareable PDFs | The review ledger is the multi-farm multiplier — the tier's value reviewer-side |
| **Co-op / adviser network** | custom | Groups | Fleet visibility, data governance, integrations, onboarding support | Phase C channel; priced per-group after 2+ network conversations |

**Deliberate non-prices:** no per-analysis micro-billing (punishes scouting exactly when it
matters); no hardware, install or data-hostage fees; export and leave is always free (see 08).

## 2. Anchors and honest counter-weights

- **Plantix: free for farmers** and monetizes the retailer ecosystem
  ([YourStory 2020](https://yourstory.com/2020/04/startup-plantix-farmers-retail-inputs-crop-health)) —
  proves free-tier demand; our paid case must therefore be *review workflow + evidence*, not verdicts.
- **Enterprise players (Taranis et al.)** prove enterprise budgets exist but require sales
  we cannot yet staff — hence agronomist-led mid-market.
- **Counter-weight honesty:** UK farm software willingness-to-pay for *scouting aids* is
  unproven by us. If interviews show growers won't pay for screening-only, the fallback
  model is agronomist-led per-farm billing where the adviser captures and shares the value.

## 3. The validation plan (30 interviews, months 0–6)

| # | Segment | Count | Core questions |
|---|---|---|---|
| 1 | UK potato/arable growers | 15 | Scouting routine today? Blanket vs targeted spraying? Would a reviewable zone + evidence PDF change a decision this season? Which tier, if any, at what price? |
| 2 | Independent agronomists | 10 | Would you put your name on the review ledger? Multi-farm triage value? What must be true before you recommend it to a client? Price tolerance per farm? |
| 3 | Co-op/adviser-network leads | 5 | Group licensing shape? Data governance requirements? Integration blockers? |

**Protocol honesty rules:** no leading questions; record raw notes; publish the aggregate
outcome in this file — *including a negative result* (a "growers won't pay" finding gets
published here verbatim and the model pivots to agronomist-led).

**Success threshold `[assumption-set decision rule]`:** ≥6 of 25 grower/agronomist
interviewees accept a paid pilot at Grower/Agronomist tier **and** ≥3 agronomists agree to
review-led usage with named clients → proceed to paid pilots. Below that: pivot pricing
before spending on acquisition.

## 4. Free-tier economics guardrail

Free usage costs real inference CPU; guardrails (already built): per-IP rate limits,
upload caps, demo-path flagging. If free usage threatens cost before revenue, the honest
lever is lowering the free analysis cap — never silently degrading model quality.
