# 07 — Financial Model (3-year scenarios)

**Prepared:** 2026-09-28 · **Status of every number below: `[assumption]` unless tagged
`[source]`. This is a planning scenario for the viability conversation — not a forecast,
not traction. Actual results will differ; material updates get committed with dates.**

## 1. Today's honest baseline

| Item | State |
|---|---|
| Revenue | £0 (0 paying users) |
| Infrastructure | ~£0/mo — free tiers (Vercel + Render + managed Postgres) `[verifiable: docs/12]` |
| Documented free-tier limits | cold starts, 512 MB RAM, 30-day DB expiry cycle, single instance `[docs/12 §2]` |
| Founder cost to date | time only (equipment already owned) |

## 2. Assumption set (each line defensible in an endorsement interview)

| # | Assumption | Value | Defence |
|---|---|---|---|
| A1 | Hosting at pilot scale | £40–90/mo | Current free tiers outgrown at ~hundreds of weekly analyses; paid tiers of today's providers `[verify at purchase — list in docs/12]` |
| A2 | Domain/email/misc | ~£50/yr | Registrar + workspace pricing at purchase |
| A3 | Interviews → pilot conversion | 6 of 25 | Decision rule in [06 §3](06-pricing-validation.md) |
| A4 | Grower tier price | £19/mo | Indicative — [06](06-pricing-validation.md) |
| A5 | Agronomist tier price | £75/mo, avg 6 client-farms covered | Indicative — [06](06-pricing-validation.md) |
| A6 | Free → paid monthly churn | 6%/mo early | Typical early-SaaS planning figure `[assumption]` |
| A7 | Founder draw | £0 until post-pilot £1.5k/mo | Subsistence-level planning figure; personal maintenance requirement (£1,270/28 days) met separately `[source: visa guidance links in 05]` |
| A8 | First agronomist (contract) | £3.5k/mo from month ~14 | UK contract day-rate annualised `[assumption]` |
| A9 | First engineer | £4.2k/mo from month ~18 | UK junior-mid salary + on-costs `[assumption]` |

## 3. Scenarios (monthly recurring revenue milestones)

| Milestone | Conservative | Base | Stretch |
|---|---|---|---|
| Interviews done (30) | m6 | m5 | m4 |
| First paying account | m9 | m7 | m6 |
| 5 paying accounts | m15 | m11 | m9 |
| Paying accounts at m30 | 10 | 18 | 35 |
| Blended ARPU/mo | £45 | £60 | £65 |
| **MRR at m30** | **~£0.5k** | **~£1.1k + agronomist tiers ≈ £9k total** | **~£22k** |
| Break-even (vs costs below) | m30+ | m26–m30 | m20 |

*The base-case m30 figure mixes £19–75 tiers per A4/A5; the arithmetic is shown so an
endorser can attack every input — that is the point of "credibly defended projections".*

## 4. Cost build-up (base case)

| Phase (months) | Fixed costs/mo | What it funds |
|---|---|---|
| 0–6 | ~£5 (domain) | Validation; free tiers hold |
| 7–13 | ~£60 | A1 hosting + misc; pilots start |
| 14–23 | ~£3.7k | + A8 agronomist contract |
| 24–30 | ~£8k | + A9 engineer + A7 founder draw |

## 5. Funding need

| Stage | Need | Source options |
|---|---|---|
| Validation (m0–6) | < £0.5k | Founder |
| Pilots (m7–13) | ~£2–6k cumulative | Founder + grant competition `[verify live programmes — 05 §6]` |
| Scale prep (m14–24) | ~£60–120k cumulative gap | Pre-seed / grant blend; every milestone before this survives without it (SRC lesson — [04 §2](04-competitor-landscape.md)) |

**Cumulative external funding need (base case): ≈ £85k over 30 months `[assumption]`** —
consistent with the "no fixed minimum investment" route while demonstrating a real,
defensible number rather than an arbitrary one.

## 6. Sensitivity (what breaks the base case, stated)

- Interview→pilot conversion < 4/25 → pricing pivot per [06 §3](06-pricing-validation.md);
  scale phase deferred, burn stays ≈ £60/mo.
- Churn > 10%/mo → agronomist-led model only; Grower tier dropped.
- No external funding by m20 → solo operation continues (infrastructure cost curve allows
  it); job-creation milestones move right — said here so it never has to be hidden later.

## 7. What we will publish back into this file

Quarterly, committed with dates: paying accounts, MRR, churn, hosting cost, interview
completion, grant outcomes (won **and lost**). The published actuals against these scenarios
are themselves endorsement evidence at contact-point meetings.
