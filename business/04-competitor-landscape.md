# 04 — Competitor Landscape

**Prepared:** 2026-09-28 · **Rule:** competitor claims come from cited public sources with
dates; where we are weaker, we say so in §3.

## 1. Who is actually in the space

| Player | What they are | Scale (sourced) | Model | Notable for us |
|---|---|---|---|---|
| **Plantix** (PEAT GmbH, DE/IN) | Free smartphone disease/pest ID for smallholders + treatment recommendations (incl. chemical + biological) + agri-retail ecosystem | 20M+ downloads ([company LinkedIn](https://www.linkedin.com/company/plantix), accessed 2026-09-28); ~1M monthly actives, ~20k images/day (2020, [CGIAR](https://bigdata.cgiar.org/digital-intervention/plant-disease-diagnosis-using-artificial-intelligence-a-case-study-on-plantix/)); raised ~$15M incl. €6.6M Series A led by RTP Global ([YourStory 2020](https://yourstory.com/2020/04/startup-plantix-farmers-retail-inputs-crop-health), [AgFunderNews](https://agfundernews.com/breaking-crop-disease-recognition-app-plantix-raises-e6-6-million-series-a-led-by-rtp-global)) | Free for farmers; monetizes retailer ecosystem | The "verdict app" archetype: instant answer + product advice. Huge reach proves demand; treatment advice is a regulatory + trust surface we deliberately avoid. |
| **Taranis** | Enterprise remote-sensing scouting for large farms | enterprise-level, large-farm focus ([roundup](https://www.trendingaitools.com/ai-tools/plantix/), accessed 2026-09-28) | Enterprise sales | Not our buyer; validates enterprise ceiling, not our wedge. |
| **CropIn** | Digital farm management + traceability platform | farm-management/traceability focus (same [roundup](https://www.trendingaitools.com/ai-tools/plantix/), accessed 2026-09-28) | B2B platform | Adjacent platform; potential integration surface, not a scouting-honesty competitor. |
| **Gamaya** | Drone/hyperspectral analytics | large-scale analytics (same [roundup](https://www.trendingaitools.com/ai-tools/plantix/), accessed 2026-09-28) | Hardware-coupled B2B | Capital-intensive path we explicitly avoid (see SRC below). |

## 2. The UK cautionary tale (risk evidence, not a competitor)

**Small Robot Company** (Salisbury, UK — autonomous weeding/planting robots) entered
**liquidation in February 2024** (Kroll appointed) after its lead investor pulled and the
crowdfunding bridge fell short: *"We were the victims of the valley of death… Agriculture
is perceived as very risky. Government funding only covers [development] to prototype."*
([The Robot Report, 2024-02-02](https://www.therobotreport.com/agtech-startup-small-robot-company-shutting-down/);
[AgriTech Future, 2024-02-04](https://agritechfuture.com/robotics-automation/deep-sadness-as-small-robot-company-enters-liquidation/)).

**Lessons absorbed into this plan:** no hardware, no inventory, near-zero fixed burn until
revenue, and milestones that survive without venture funding.

## 3. Differentiation — and where we are honestly weaker

**Where CropMind is different (evidence in this repo):**

1. **Honesty as a workflow, not a disclaimer** — calibrated bands + abstention below LOW;
   in-domain 0.9959 *and* PlantDoc OOD 0.2349 published together everywhere; deployment
   failures logged verbatim. No competitor above publishes an OOD shortfall.
2. **Reviewable evidence chain** — zones are simulations with a PENDING/APPROVED/REJECTED
   ledger; the PDF field report prints the ledger, the model version and the limitations.
   Built for agronomist accountability, not just farmer curiosity.
3. **No chemical advice by design** — positioning avoids the product-advice regulatory
   surface and keeps trust with advisers (see 05 §5).
4. **Open source + reproducible** — an agronomist's CTO can audit every claim.

**Where we are honestly weaker today:**

- **Image database & crop coverage:** Plantix reported 10.5M+ images by 2020 against our
  4-crop/21-condition model. Coverage grows only with licensed data + honest evaluation.
- **Offline/mobile UX, languages, brand, distribution:** a funded app ecosystem beats a
  one-person web product on all four today.
- **Field performance:** their real-world accuracy is unknown to us; ours is honestly
  known to drop out-of-domain (0.2349) — we mitigate by design, they scale by data.

**Positioning statement:** not "a better Plantix" — **the decision-support layer for UK
growers and agronomists who must verify and document crop-health decisions**, free to
start, honest by construction.
