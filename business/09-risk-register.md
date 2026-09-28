# 09 — Risk Register

**Prepared:** 2026-09-28 · Scales: L/M/H. Owner is the founder unless named. Reviewed at
every phase close; changes commit with dates.

| # | Risk | L | I | Mitigation (in place) | Residual / trigger to watch | Status |
|---|---|---|---|---|---|---|
| R1 | **Field/OOD model gap** — PlantDoc field OOD top-1 is 0.2349; real-world verdicts may often be wrong | H | H | Abstention below LOW band; human review mandatory; paired metrics published; INCONCLUSIVE is a designed outcome, not hidden | Pilot abstention rate; user trust interviews (06) | Open — measured honestly, not "solved" |
| R2 | **Solo-founder key-person** — illness/burnout stops everything | M | H | Fully open, reproducible repo; every step documented (docs/01–16); a competent engineer could take over from the docs alone | Bus factor stays 1 until first engineer (07 A9) | Open |
| R3 | **UK agritech "valley of death"** — funding dries between prototype and revenue (Small Robot Company, liquidated 2024-02 — [source](https://www.therobotreport.com/agtech-startup-small-robot-company-shutting-down/)) | M | H | Software-only, no inventory; ~£0/mo run-rate until revenue; milestones survivable unfunded (07 §6) | External funding absent by m20 → plan rightsizes | Mitigated by design |
| R4 | **Free incumbent absorbs segment** (Plantix free; 20M+ downloads — [04](04-competitor-landscape.md)) | M | M | Different buyer (review workflow, not verdicts); agronomist channel; evidence PDFs | Interview price-tolerance results | Open |
| R5 | **Regulatory drift toward product advice** — someone "adds just one suggestion" feature request | M | H | Hard product rule: no chemical advice anywhere; pinned by tests; refusal documented in docs/16 | Any PR touching recommendation-like text — review gate | Controlled |
| R6 | **Model extraction via public API** (weights now served publicly, AD-009) | M | L | Rate limits; weights not downloadable; moat is workflow+data, not secrecy (08) | Abuse patterns in logs | Accepted, documented |
| R7 | **Free-tier operational limits** — cold starts, 512 MB RAM, 30-day DB expiry (current DB expires ≈ 2026-10-28), ephemeral disk | H | L | Documented honestly in docs/12; renewal runbook; costed upgrade path (07 A1) | Calendar reminder ~2026-10-22 — set ✓ | Managed operationally |
| R8 | **Security breach** (auth, uploads, tokens) | M | H | bcrypt + JWT revocation; per-account scoping (tests pin isolation); rate limits; audit log; no secrets in git; PAT rotation discipline | Dependency CVEs — patch cadence | Controlled, standing |
| R9 | **Visa endorsement refusal** | M | H | Evidence-first package (10); verifiable claims only; apply with 2 body choices; refusal feedback loop fixes gaps and reapplies | Endorsing-body list changes — re-verify live list (05 §1) | Open — the point of this package |
| R10 | **Data-licensing changes upstream** (dataset terms shift) | L | M | Only licensed datasets ever train (taxonomy gate enforces); provenance recorded | Periodic license re-check before new training runs | Controlled |
| R11 | **Over-promise creep in marketing** — a bald accuracy claim slips into copy | M | M | Pair-travel rule pinned in tests (banner/truth panel carry both figures); docs/16 governs claims; "silently upgraded claim is a bug" on the About page | Review every public sentence against docs/16 | Controlled by tests |
| R12 | **Scope creep** (roadmap temptation: drones, detectors, more crops) | H | M | Phased roadmap with completion gates; simulator honesty rules; crops added only with licensed data + passed evaluation | Any "quick" feature skipping the taxonomy gate | Managed |
| R13 | **Free-tier abuse / cost spike before revenue** (inference CPU burns on free abusive traffic) | M | M | Per-IP rate limits; upload caps; free analysis-cap lever stated in 06 §4 | Usage metrics vs A1 cost curve | Controlled |

## Standing rules

1. A risk that materialises gets a dated incident entry (pattern proven by the deployment
   log, docs/12 §7 — failures recorded verbatim, never erased).
2. No risk is ever deleted from this register — closed rows move to "Closed + date + why".
3. The three top risks at any review are stated in the phase-close report.
