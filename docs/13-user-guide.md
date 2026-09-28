# 13 — User Guide

**Status:** ✅ Phase 13 (2026-09-28) — final
**Read with:** [03 — User workflows](03-user-workflows.md) (personas/journeys), [15 — Known limitations](15-limitations.md), [06 — Model card](06-model-card.md)

How to run and use CropMind AI today — the public demo or your own machine. Everything the
UI tells you is also written down here, so what you see is what you can verify.

---

## 1. Ways to access

| Mode | Where | Model | Notes |
|---|---|---|---|
| **Public demo** | https://cropmind-ai-theta.vercel.app | **DEMO sample model only** (synthetic patterns, clearly flagged) | Free tier: sleeps after ~15 min idle; the first action after that can take ~a minute while it wakes |
| **Local / self-hosted** | `docker compose up --build` (README quickstart) | DEMO sample model by default; set `MODEL_CHECKPOINT` to a trained run for the evaluated baseline | The model card's numbers were measured on the baseline checkpoint, never on the sample model |

**Accounts.** Register with an email + password. On a *fresh* deployment the **first account
becomes ADMIN** (bootstrap — the register screen and response say so); later accounts are
FARMER, and an admin can promote reviewers to AGRONOMIST. Without an account you can still
try the **flagged demo path** — those runs are labelled DEMO everywhere and stay separate
from real records.

## 2. Running an analysis

1. **Analyze** (/analyze) → step 1: upload a photo of a **single leaf, well-lit, filling the
   frame**. The model was trained on lab-style leaf imagery; field/background-heavy photos
   are genuinely harder for it — if it is unsure it will say so (§3).
   - Your photo is normalized and **location metadata is removed** at upload (privacy by
     design). Duplicates are detected by content hash.
2. Step 2: optionally attach the image to one of your fields (or create the farm/field inline).
3. Step 3: processing. On the free demo the backend may need ~a minute to wake — the wizard
   waits, retries automatically, and says so. **You don't need to re-click anything.**
   If an analysis exhausts its three worker attempts it is marked **FAILED** with the real
   error — that is the system being honest, not hiding a crash.

## 3. Reading the result (this matters)

- **`Suspected {crop} - {condition} - {x}% confidence`** — the model's suspect, confidence
  shown against the configured bands: **HIGH ≥ 0.60 · MEDIUM ≥ 0.45 · LOW ≥ 0.25**.
- **INCONCLUSIVE** — confidence below the LOW band. This is a first-class, honest outcome:
  **retake the photo or request agronomist review.** Nothing is forced into a label, and
  INCONCLUSIVE analyses intentionally produce **no intervention zones**.
- **DEMO flag** — predictions from the synthetic sample model are always marked DEMO
  (analysis history, analysis view, PDF banner). Demo output demonstrates the plumbing;
  it must never be cited as field performance.
- **Grad-CAM overlay** — highlights regions that contributed strongly to the prediction.
  It is *not* a guarantee of disease location (the caveat travels with the overlay).
- **Estimated visual severity** — an experimental area-based proxy, labelled as such. It is
  not an agronomic severity measurement.
- **What the app will never show:** a confirmed diagnosis, or any chemical product/dosage
  guidance. Decision support only — a human verifies.

## 4. Field map and intervention zones

1. **Draw the field boundary** on the map (the only geography the system keeps — photo GPS
   is stripped at upload).
2. From a **SUSPECTED** analysis, **generate zones**. Each detection region becomes one zone,
   positioned in *image space* (not geo-referenced — the map says this plainly).
3. **Review order** comes from a published deterministic rule (confidence band + severity
   proxy). It is a review order, **not** an agronomic risk score — the label says so.
4. **Approve or reject** each zone, with a note. Every change is recorded (old → new, who,
   when); re-review is allowed and equally recorded. Regenerating zones never erases a
   decision you already made.
5. **Exports** (GeoJSON/CSV) are labelled SIMULATION in both the filename and the content.

## 5. Spray-plan simulation

On `/simulate`: choose a field (boundary only), **draw the treatment polygons yourself**,
and **type the application rate yourself** — the app never suggests rates. The result is
labelled arithmetic (your areas × your rate) with assumptions verbatim; runs are stored so
simulations stay reproducible. It is a planning *simulation* — not a validated saving, not
an equipment control file.

## 6. PDF field reports

From any completed analysis, generate a PDF field report. It includes the unique
`CMA-…` report ID, the verbatim phrasing and confidence band, model/dataset versions, the
zone **review ledger** (who approved/rejected what and when) and DEMO banners where
applicable. Download it from `/reports` and share it with your agronomist.

## 7. Feedback

On an analysis you can record whether the suspect was correct, the actual condition, image
quality, and notes. Feedback is stored, visible to reviewers/admins, and used in future
gated evaluations — the app states clearly that it **does not trigger automatic retraining**.

## 8. Administration (ADMIN)

`/admin`: user list and role changes (audited old → new; you cannot demote yourself),
feedback inbox, audit-log browser, and measured overview counts. Sign-out revokes your token
server-side immediately.

## 9. Free-tier demo caveats

- **Sleep:** after ~15 minutes idle the API sleeps; the next action can take ~a minute while
  it boots. The app waits and tells you — don't hammer the button.
- **Resources:** the demo runs a single small instance. Very unlikely, but if analyses
  repeatedly come back FAILED on the public demo, the deployment notes (docs/12 §2) explain
  the documented fallback.
- **Data lifetime:** the demo database is a free-tier instance for evaluation purposes;
  don't treat it as long-term storage.

## 10. FAQ

**Why did my analysis say INCONCLUSIVE?** The model's confidence fell below the LOW band —
it abstained honestly. Retake: single leaf, close, good light, plain background.
**Why are there no zones for my analysis?** Zones exist only for SUSPECTED verdicts; an
INCONCLUSIVE result means there is honestly nothing to map.
**Why won't it tell me what pesticide to use?** By design, permanently. The product is
decision support; chemical choices belong to qualified humans and local regulations.
**Where is my photo's GPS?** Stripped at upload, deliberately. Field position comes from the
boundary *you* draw.
**Is demo output real performance?** No — DEMO-flagged output comes from a synthetic sample
model (plumbing evidence). Real measured performance is published in the
[model card](06-model-card.md) (in-domain 0.9959 top-1 *and* the honest out-of-domain
shortfall 0.2349 — both travel together).
