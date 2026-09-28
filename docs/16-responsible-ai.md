# 16 — Responsible AI Statement

**Status:** ✅ Phase 13 (2026-09-28) — final
**Read with:** [06 — Model card](06-model-card.md), [15 — Known limitations](15-limitations.md), [09 — Security posture](09-security.md), [10 — Privacy notice](10-privacy.md)

This is the accountable statement of how CropMind AI is designed, deployed, and constrained
as an AI system that can influence real-world decisions about crops, chemicals, and money.
It is written to be checked: every mechanism named here exists in code or in a published
artefact in this repository.

---

## 1. Intended use — and uses we refuse

**Intended:** decision *support* for farmers and agronomists — triaging suspected crop-health
issues from leaf imagery, prioritizing walk-through inspections, and planning where to look.

**Refused by design (not merely discouraged):**

| Use | Why refused | Where enforced |
|---|---|---|
| Autonomous spray/treatment decisions | Requires verified diagnosis + agronomic judgement this model cannot supply | No actuator/hardware integration exists; review is a human gate |
| Pesticide product/brand/dosage recommendation | Legal and safety red line; false confidence kills crops and people | Excluded from the data model — no field, no endpoint, no UI |
| Presenting output as confirmed diagnosis | Suspected-condition phrasing is stored and served **verbatim**; certainty would be fabrication | `phrasing` contract (docs/04 §2) |
| Crop-insurance or credit adjudication from model output | Unvalidated OOD performance (docs/15 M1); would launder uncertainty into decisions | Not built; data model unsuited; stated here so it stays unbuilt |
| Silent re-scaling of zones into real hectares | Invented precision; GPS is stripped at upload | `georeference_source: "none"` (docs/04 §3.7) |

## 2. Human-in-the-loop, structurally

- **INCONCLUSIVE is a first-class outcome.** Below the LOW band the system abstains and its
  only advice is "retake / ask an agronomist" — never a forced label.
- **Zone review is a human ledger.** APPROVE/REJECT transitions are audited old → new with
  reviewer and timestamp; regeneration never overwrites a human decision.
- **Feedback without auto-retraining.** User feedback is captured for *gated* future
  evaluation (docs/08). A model is promoted only by a measured, recorded gate — never by a
  cron, never by popularity.
- **Fabrication and errors surface.** Failed analyses say FAILED with the real error;
  wake-ups say "waking up"; nothing fakes success.

## 3. Honesty mechanisms (the integrity surface)

1. **Verbatim phrasing contract** — the model module emits the exact user-facing sentence;
   the API stores and returns it unchanged.
2. **Config-driven confidence bands** (`ml/configs/model.yaml`) — never hardcoded; changed
   only with recorded evaluation evidence.
3. **Dual-metric rule** — in-domain (0.9959) and out-of-domain (0.2349, a shortfall) numbers
   are published together, always, in README, model card, and every claim context.
4. **DEMO flags are structural** — sample-model output is flagged at DB, API, UI, and PDF
   layers; anonymous usage is demo-only.
5. **SIMULATION labels travel** — in filenames *and* file bodies for every export and report
   section derived from simulation.
6. **Open book** — source, model card, data card, eval runbook, third-party license audit,
   security posture, privacy notice: all public, all versioned.

## 4. Data ethics

- Training data is **public and licensed** (PlantVillage CC0; PlantDoc CC BY 4.0), with a
  maintained license register and provenance manifests (docs/datasets.md, 07).
- **No user imagery trains anything.** Uploads belong to the deployment owner; feedback is
  evaluation metadata, not a training feed.
- **Privacy by design:** EXIF GPS stripped at upload; geographic data exists only where the
  user explicitly draws it (10).

## 5. Fairness and representation

Acknowledged gaps (owned, from docs/15): 4 crops × 21 conditions; lab-condition training
data; English-only UI; smartphone assumed. The taxonomy grows only behind licensed data
*and* an honest gated evaluation — coverage is never stretched by lowering the bar.
The open-source, self-hostable, free-tier-runnable shape is itself an equity choice: the
primary persona is a smallholder, not an enterprise.

## 6. Safety

- The most dangerous failure in this domain is a **confident wrong answer acted on
  chemically**. Mitigations: abstention below thresholds, human review gates, no chemical
  pathway, standing decision-support notice on every prediction payload.
- Second danger: **wasted trust** from over-claimed performance. Mitigations: the
  dual-metric rule, the limitations register, demo honesty, and a public deploy log that
  records failures verbatim (docs/12 §7).
- The simulator touches no hardware and controls nothing physical.

## 7. Accountability and governance

- **Decision records:** ADRs (docs/02), promotion gates with measured evidence (model.yaml
  notes, docs/06 §2), an audit-log table for security-relevant writes, request IDs end-to-end.
- **Incident and vulnerability handling:** docs/09 (reports welcomed; honest posture over
  appearance); deploy incidents are logged as they happened, fixes pinned by tests.
- **Versioning:** model/dataset/threshold versions embedded in every prediction; a PDF
  carries the versions that produced it, so a claim can always be traced to evidence.

## 8. UK regulatory posture (Innovator Founder context)

- The product is **decision-support software**, not an agronomic prescription service and
  not a regulated device; it makes no efficacy, pesticidal, or yield claims. Marketing
  follows the same rule as the code: outcomes are labelled estimate/simulation; no
  testimonials or customer claims exist to misuse (none are fabricated — a hard rule).
- Data protection: the deployment processes personal data minimally (account email;
  voluntary feedback); the [privacy notice](10-privacy.md) and [security posture](09-security.md)
  describe practice today and duties before any real operation (UK GDPR / DPA 2018):
  no special-category data by design, GPS stripped at intake.
- Third-party license obligations — including the two flagged items (LGPL psycopg,
  Hippocratic react-leaflet) — are audited in [THIRD_PARTY_LICENSES.md](../THIRD_PARTY_LICENSES.md)
  with escape hatches named.

## 9. Commitments

1. Both accuracy numbers (in-domain *and* OOD shortfall) travel together in every public
   surface — including investor and visa materials.
2. Known limitations (docs/15) get fixed in the open or stay disclosed; they are never
   silently edited away. Fixes are pinned by regression tests.
3. Any future field-validation, trial, or customer evidence will be added as *recorded,
   dated artefacts* — or not claimed at all.
4. This statement is revisited at every model promotion and every phase gate.
