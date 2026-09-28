# 03 — User Workflows

**Status:** ✅ Phase 13 (2026-09-28) — final
**Read with:** [01 — Product requirements](01-product-requirements.md), [13 — User guide](13-user-guide.md), [16 — Responsible AI](16-responsible-ai.md)

This document defines **who the product is for, the journeys it supports, and the state
models those journeys move through**. It is the bridge between the product requirements
(01) and the screens/API that exist today.

> **Honesty note (product principle 3).** The personas below are *design personas*
> derived from the founder's domain experience and publicly available smallholder-agriculture
> literature. They are **not** the output of customer interviews or field studies — no such
> validation has been conducted yet, and none is claimed anywhere in this repository
> (the endorsement evidence plan for customer discovery is a Phase 14 artefact with
> explicitly-marked placeholders only).

---

## 1. Personas (design hypotheses, unvalidated)

### P1 — "Smallholder farmer" (primary user)

| | |
|---|---|
| Context | 1–5 ha holdings, often several scattered blocks; smartphone (Android) with intermittent connectivity; sprays on a calendar/risk basis, frequently blanket-spraying whole fields |
| Goals | Catch problems earlier; spend less on crop-protection inputs; have something credible to show an agronomist or buyer |
| Constraints | Limited agronomy training; low trust in black-box apps; cannot risk acting on a wrong answer; data costs matter |
| What the product gives them | A photo → a *suspected* condition with an honest confidence band; a field map of where to look first; a PDF to carry to an agronomist |
| What it explicitly does **not** give them | A diagnosis ("suspected", never confirmed); any chemical product, brand, or dosage recommendation; savings promises — only labelled simulations |

### P2 — "Consulting agronomist" (reviewer)

| | |
|---|---|
| Context | Advises many farms; receives photos over messaging apps with no structure; limited time per farm visit |
| Goals | Triage which farmer/block to visit first; keep a reviewable record of what was flagged and decided |
| Constraints | Professionally liable for advice; will not trust unverifiable outputs |
| What the product gives them | Review queues (zones PENDING → APPROVED/REJECTED, audited transitions), verbatim model phrasing with bands, feedback capture per analysis |
| What it explicitly does **not** give them | Automated diagnosis to rubber-stamp; hidden re-derivations of model output (the stored phrasing is the model's, byte-for-byte) |

### P3 — "Farm manager / operator-admin" (ADMIN role)

| | |
|---|---|
| Context | Runs the deployment for an operation (self-hosted today); onboards staff |
| Goals | Manage accounts and roles; see platform usage; ensure the audit trail exists |
| What the product gives them | `/admin` console (users, role changes with old→new audit, feedback, audit logs, measured overview counts) |
| What it explicitly does **not** give them | Per-user performance tracking, data export for surveillance — out of scope by design |

**Account model mapping:** FARMER (default) — own farms/fields/analyses/zones/reports;
AGRONOMIST (reviewer) — read/review across accounts; ADMIN — P2 visibility plus user/role
administration. The first account on a fresh deployment becomes ADMIN (documented
bootstrap, surfaced in the register response and UI).

---

## 2. Core journeys

### J1 — First visit → account (2 min)

1. Land on `/` (landing: what it is, what it is not — the honest scope is on the front door).
2. `/register` → email + password. Response and UI say if you became the bootstrap ADMIN.
3. Signed in (JWT, 12 h; sign-out revokes server-side). Anonymous visitors can still use the
   **flagged demo path** only (`demo=true` uploads/analyses, DEMO-labelled everywhere).

### J2 — First analysis (photo → honest verdict)

1. `/analyze` → the three-step wizard: **(1) capture/upload** a leaf photo → **(2) context** (optional farm/field) → **(3) processing**.
2. Upload pipeline protects the user silently: type sniffing (magic bytes, not extensions),
   EXIF-orientation normalize, **GPS metadata stripped** (privacy), 2048px JPEG re-encode,
   sha256 dedupe.
3. Worker picks the job (bounded retries with honest failure after 3 attempts).
4. Result screen: the **verbatim phrasing** (`Suspected {crop} - {condition} - {x}% confidence`
   or the INCONCLUSIVE sentence), confidence band, uncertainty, *Estimated visual severity*
   (labelled proxy), Grad-CAM overlay with its caveat, model + dataset versions, and the
   standing decision-support notice. DEMO runs are visibly flagged.
5. If INCONCLUSIVE: the app says retake/review — **no zones can be generated** (designed abstention).

### J3 — Field map → intervention zones → human review

1. `/map` → draw the field boundary (the ONLY geography in the system — image GPS is stripped).
2. From a SUSPECTED analysis: generate zones. They appear in **evidence space**
   (image-normalized coordinates, `georeference_source: "none"` — never invented locations).
3. Risk level + review priority come from a **documented deterministic rule** (band + severity
   proxy) — labelled "review order, not an agronomic risk score".
4. Review each zone: APPROVE / REJECT with a note. Transitions are audited OLD→NEW; re-review
   is allowed and always recorded; regeneration never overwrites a human decision.
5. Export GeoJSON/CSV — filenames and bodies carry **SIMULATION** labels.

### J4 — Spray-plan simulation (labelled arithmetic)

1. `/simulate` → pick a boundary-only field, mark treatment polygons yourself
   (image zones *inform*; nothing auto-scales hectares from pixels).
2. Type the application rate yourself — the system never suggests one.
3. Run → SIMULATION-labelled result: areas, route, totals; assumptions verbatim.
4. Stored in run history; route downloadable with the same labels.

### J5 — Field report (the agronomist hand-over)

1. From an analysis: generate the PDF. It carries the unique `CMA-…` report ID, the verbatim
   phrasing, bands, versions, the **zone review ledger** (who approved/rejected what, when),
   and DEMO banners when applicable.
2. Download → share with the agronomist/buyer. Regeneration is explicit, never silent.

### J6 — Feedback (closes the loop without auto-retraining)

- On an analysis: record correctness / actual condition / image quality / notes.
- The UI states plainly: **feedback is stored for evaluation and does not trigger automatic
  retraining.** Model changes only happen through the gated eval pipeline (docs/08).

### J7 — Administration (ADMIN)

- `/admin`: users + role changes (self-demotion blocked, audited), feedback inbox, audit log
  browser, measured overview counts. Anything else is deliberately out of the console.

---

## 3. State models (what the UI is allowed to show)

### 3.1 Analysis lifecycle

```
QUEUED ──worker claim──> PROCESSING ──> COMPLETED ──> prediction verdict: SUSPECTED | INCONCLUSIVE
                      └──> FAILED (error shown verbatim; retried per bounded backoff before that)
```

- Zones: only from COMPLETED ∧ SUSPECTED. INCONCLUSIVE/FAILED generate none (HTTP 409/empty with the reason).
- A poll/transient network failure never relabels an analysis FAILED — the client holds state
  and retries honestly (Phase 12 hardening, docs/12 §5).

### 3.2 Zone review lifecycle

```
PENDING ──> APPROVED ──┐
   └─────> REJECTED ───┴── (re-review allowed; every transition audited OLD→NEW, with reviewer + timestamp)
```

- Regeneration replaces PENDING zones only; APPROVED/REJECTED survive (human decisions are not erased).

### 3.3 Report lifecycle

- Created on demand (201); regenerate = explicit POST again (new content, same analysis,
  ledger refreshed); failures surface as API errors — never a half-written PDF served quietly.

---

## 4. Screen inventory (as implemented)

| Route | Purpose | Auth |
|---|---|---|
| `/` | Landing — pitch + honest scope + live links | public |
| `/login` `/register` | Session start; bootstrap-ADMIN note on register | public |
| `/dashboard` | Home: recent analyses, quick actions | account (demo rows without) |
| `/analyze` | 3-step analysis wizard | account, or flagged anonymous demo |
| `/analyses` | History (scoped: own · reviewers all · anonymous demo only) | scoped |
| `/analyses/[id]` | Analysis view: verdict, bands, Grad-CAM, feedback widget | scoped |
| `/farms` | Farms & fields CRUD, boundary edit entry | account |
| `/map` | Boundary drawing, zones, review, exports | scoped |
| `/simulate` | Spray-plan simulation + stored runs | account |
| `/reports` | PDF report list/download | scoped |
| `/model-information` | Live `/model-info` + `/supported-crops` (taxonomy, bands, status) | public |
| `/settings` | Profile/session (sign out = server-side revocation) | account |
| `/admin` | Users/roles, feedback, audit logs, overview | ADMIN |

Routes marked *scoped* resolve out-of-scope objects as **404** (existence is never leaked);
wrong-role writes are **403** with the reason. Full contract: [04 — API design](04-api-design.md).

---

## 5. Designed-in abstentions (workflows that deliberately dead-end)

These are features, not gaps — each prevents a specific real-world harm:

1. **INCONCLUSIVE photos produce no zones and no report verdict.** A low-confidence model
   abstains; the next step offered is retake/human review, not a guess.
2. **Anonymous usage is permanently DEMO-labelled.** Without an accountable owner, outputs
   cannot be mistaken for a farm record.
3. **No chemical path anywhere.** There is no screen where product or dosage could be entered
   or shown — the domain is excluded from the data model itself.
4. **Simulations cannot present as measurements.** Filenames, banners, PDF sections, and API
   payloads all carry the SIMULATION label; removing it requires editing source, not config.
