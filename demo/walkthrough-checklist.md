# End-to-End Walkthrough (checklist + rehearsal evidence)

**Prepared:** 2026-09-28 · **Duration:** 3–5 minutes. **Environment:** public deployment
(Vercel frontend + Render free API — wake it ~2 min early). **Rule:** if a step fails,
record the failure verbatim (docs/12 §7 gets the row) — never improvise around it.

## The 7 steps

1. **Wake + truth.** Open `https://cropmind-ai-theta.vercel.app` → Model truth panel shows
   status + serving chip (`serving: real model · remote (AD-009)` when the real checkpoint
   serves; `sample model (flagged)` otherwise — say what it says, not what you expected).
2. **Account.** Sign in (showcase account) — or stay anonymous to show the flagged demo path.
3. **Sample choice.** Analyze → bundled sample picker: one *in-domain* photo and one *field*
   photo (both labelled with provenance + expectation note).
4. **Analysis.** Upload → wait for COMPLETED (worker polls; free-tier latency is stated).
   Read the verdict verbatim + band + uncertainty; show model/dataset/threshold versions.
5. **Zones.** Generate intervention zones → confirm the SIMULATION framing (image-space,
   no georeference claimed) → APPROVE one as the human reviewer (note recorded).
6. **Report.** Generate PDF → check the banner matches the truth (demo path ⇒ DEMO TRIAL
   banner with both figures; sample weights ⇒ DEMO banner; real + normal path ⇒ none) →
   download and scroll the review ledger + limitation lines aloud.
7. **Trail.** History shows the new rows; feedback widget can record a correctness verdict
   (feeds the data strategy — "no automatic retraining" is stated on it).

## Rehearsal evidence — executed live 2026-09-28 (real model v0.1.0 serving)

Four bundled samples run against the public API; outcomes copied verbatim from the
predictions (field `Tomato Block A` on the showcase farm):

| Sample photo | Outcome (verbatim) | Reading |
|---|---|---|
| `pv-tomato-early-blight` (in-domain) | **Suspected Tomato - Early blight - 91% confidence** (SUSPECTED, HIGH, demo=false, model 0.1.0) | correct crop + condition, in-domain strength |
| `pv-potato-late-blight` (in-domain) | **Suspected Potato - Late blight - 77% confidence** (SUSPECTED, HIGH) | correct crop + condition |
| `pd-tomato-early-blight-field` (PlantDoc field) | **Inconclusive (Tomato - Yellow Leaf Curl Virus at 21% is below the LOW band) - retake photo or request agronomist review** | the published OOD gap, live: the system **abstained** |
| `pd-potato-late-blight-field` (PlantDoc field) | **Suspected Potato - Early blight - 39% confidence** (SUSPECTED, LOW band) | the honest miss: wrong *condition* family, disclosed at LOW — never upgraded |

Flagship path completed identically to the script: zones generated (`f88528c5-2143-4951-82ea-3c6aff448847`, HIGH, conf 0.91) → APPROVED with reviewer note → report **`CMA-20260928-2CDDF0`** generated 201 and downloaded 200 (4,950 B). PDF text verified to contain: DEMO TRIAL banner naming the real model + **both** figures (0.9959 / 0.2349), the verbatim 91% phrasing, the APPROVED ledger line, "SIMULATION PENDING HUMAN REVIEW", "Sample (demo) weights: **no**".

Earlier sign-off moments (verifiable in repo/deploy log): founder solo golden path with a
real leaf photo, 2026-09-28 (SUSPECTED HIGH → zone APPROVED → PDF audited); anonymous demo
path end-to-end, 2026-09-28.

## Operator pre-demo checklist (2 minutes)

- [ ] Open the URL ~2 min early; confirm the truth panel chip tells the expected story.
- [ ] Fresh uploads/downloads exist (sleep/wake or redeploy wipes files — docs/12 §7
      runbook step 6; re-seed with the showcase script beforehand if the demo must look populated).
- [ ] Script in hand; screenshot fallback: `demo/` + README "See it working" frames.
- [ ] If something breaks live: say it, open docs/12 §7, show how failures are recorded —
      that IS the closing argument.
