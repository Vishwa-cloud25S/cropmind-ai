# 02 — Lean Canvas

**Prepared:** 2026-09-28 · Every cell is tagged **[E]** (evidence exists — link/verify) or
**[A]** (assumption to validate in Phase 15+ interviews). An honest canvas says which is which.

| Block | Content |
|---|---|
| **Problem** | Up to 40% of global crops lost to pests; >$220B/yr plant-disease cost ([FAO](https://www.fao.org/newsroom/detail/Climate-change-fans-spread-of-pests-and-threatens-plants-and-crops-new-FAO-study/en)) **[E]**. Uniform whole-field spraying because growers can't see precisely where problems are **[A]** — assumed from literature + founder context, to be validated in the 30-interview plan (see 06). Existing verdict apps lack confidence honesty, review trails and evidence exports **[E]** (comparison in 04). |
| **Customer segments** | UK arable growers (potato wedge first — 118k ha UK potatoes, Defra 2024 **[E]**); independent agronomists reviewing many farms **[A]**; co-ops/adviser networks later **[A]**. Early adopters: tech-curious potato/veg growers in eastern England **[A]**. |
| **Unique value proposition** | "Crop-health screening that tells you what it **doesn't** know." Suspected-condition verdicts with calibrated bands and abstention; reviewable intervention zones; a printable evidence PDF with the review ledger on it. Honesty is the feature **[E]** (shipped — live demo). |
| **Solution** | Vision model (4 crops, 21 conditions) + Grad-CAM + zone simulation + PDF reports + spray-route simulator, web-based, no hardware **[E]**. Detector localization + field georeferencing **[A — roadmap]**. |
| **Channels** | Open-source repo + public live demo (zero-cost, always-on— **[E]**); agronomist interviews and referrals **[A]**; UK ag-tech events and co-op introductions **[A]**; content/radical-honesty marketing (published OOD shortfall) **[E — already differentiates]**. |
| **Revenue streams** | Freemium SaaS: Free tier (community/validation) → Grower ~£19/mo → Agronomist ~£75/mo multi-farm → Co-op custom **[A — indicative, to be tested per 06]**. No per-acre hardware or services revenue. |
| **Cost structure** | Today: ~£0/mo infra on free tiers **[E]** (limits documented in docs/12). At pilots: ~£40–90/mo hosting **[A]**; domain/email ~£50/yr **[A]**; founder time **[E — sunk]**. Post-endorsement: founder living costs + first agronomist salary (see 07) **[A]**. |
| **Key metrics** | Weekly active reviewers; analyses completed per farm per week; % predictions SUSPECTED vs INCONCLUSIVE (abstention rate — honest health metric, **not** to be minimized by tuning); zone review turnaround; free→paid conversion **[A targets in 07]**; demo→signup conversion **[E instrumentable — already measurable]**. |
| **Unfair advantage** | Radical, verifiable honesty as brand + workflow (published OOD shortfall, deployment failure log, demo labelling — competitors show none of this) **[E]**; fully open reproducible stack a solo founder can run at near-zero cost **[E]**; founder can build *and* validate in two farming contexts (UK target, India field context) **[E/A]**. |

## What would kill this canvas (state it, then test it)

1. Growers won't pay for "screening" — they want prescriptions **[A → test in interviews 1–10]**.
2. OOD gap (0.2349 field top-1) proves too wide for trust even with abstention **[E that the gap exists / A how users react — pilot measure]**.
3. Free incumbents (Plantix free tier) absorb the segment before paid pilots land **[E that they're free / A UK agronomist willingness-to-pay]**.
