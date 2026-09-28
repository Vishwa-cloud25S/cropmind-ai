# Pitch Deck Outline (12 slides)

**Prepared:** 2026-09-28 · Companion to [01-business-plan.md](../business/01-business-plan.md).
**Content rule (binding):** every slide carries its source or a `[VERIFY — pending]`
placeholder; both evaluation figures whenever either appears; no traction/revenue/user
claims of any kind (current honest state: 0 paying users, £0 revenue, pre-incorporation).
`[SHOT]` marks where a real product screenshot goes (frames exist under
`docs/assets/screens/`; refresh with real-model serving chips).

| # | Slide | Content | Every claim backed by |
|---|---|---|---|
| 1 | Title | CropMind AI — crop-health screening that tells you what it doesn't know. Founder: Vishwa Odduri. Live URL + repo QR. | — |
| 2 | Problem | Up to 40% of global crops lost to pests; >$220B/yr plant-disease cost; uniform spraying because growers can't see precisely. | FAO newsroom 2021; UKFSR 2021 (links in business/03) |
| 3 | Product in one frame | `[SHOT]` analysis view: verbatim *Suspected* phrasing, HIGH band, Grad-CAM caveat, demo flags. One sentence: image → honest verdict → reviewable zones → evidence PDF. | live demo |
| 4 | The honest moat | Confidence bands + abstention (INCONCLUSIVE below LOW); both evaluation figures quoted on our own homepage: 0.9959 in-domain / 0.2349 field OOD. "Nobody else puts their gap on the front door." | model card docs/06; `/model-info` |
| 5 | Live demo beat | `[SHOT]` 3-min demo storyboard: bundled samples (labelled provenance), abstention on field photo, DEMO TRIAL banner. | demo/walkthrough-checklist.md rehearsal evidence |
| 6 | Why now / market | Precision-ag $10–18B global (range across 4 named reports), UK ≈ $0.42B growing ~7%; UK 209k holdings, 6.17M ha croppable. | business/03 sources named per figure |
| 7 | Competition | Plantix-scale free verdict apps vs reviewable decision-support: comparison table incl. "where we are weaker today" row. | business/04 (sourced) |
| 8 | Business model | Freemium SaaS: Community free → Grower ~£19/mo → Agronomist ~£75/mo → co-op custom. All tiers marked **indicative, in validation** (30-interview plan with published decision rule). | business/06 |
| 9 | Traction & status (honest) | Working public product, real model live, MIT open source, 249+ automated tests green in CI. **0 paying users, £0 revenue, pre-incorporation — by stage, not by omission.** Next 90 days: interviews → 3–5 paid pilots. | repo + CI; business/10 |
| 10 | Financials | 3-year scenario table (conservative/base/stretch) with the £85k cumulative need and the "survives unfunded" design (SRC lesson). | business/07 (assumptions tagged) |
| 11 | Team / execution proof | Solo founder: built + deployed + documented everything visible in this deck; phases 0–15 public; deployment log records failures verbatim. India field context, UK-first plan. | commit history; docs/12 §7 |
| 12 | The ask + evidence map | Endorsement under Innovator Founder: innovation/viability/scalability → click-verifiable evidence table; contact via GitHub issues. | business/10; business/05 |

## OOD slide rule (slide 4 wording, pinned by review)

Show the numbers exactly as the model card does: "in-domain held-out top-1 **0.9959**;
PlantDoc field OOD top-1 **0.2349** — a real domain gap we publish, mitigate with abstention
+ human review, and close with licensed field data (roadmap)." Never crop the slide so the
second number falls off; if space forces a choice, drop the in-domain number instead.
