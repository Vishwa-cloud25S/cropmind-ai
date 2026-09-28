# 3-Minute Demo Script (endorsing-body / partner audience)

**Prepared:** 2026-09-28 · **Duration:** ~3 minutes spoken (~430 spoken words) · **Setup:**
open `https://cropmind-ai-theta.vercel.app` **two minutes early** (free tier sleeps ~15 min;
the wake is honest and visible). Sign in as the showcase account or skip sign-in — the
flagged demo path is part of the story.

> Speaker cues in *[brackets]*. Everything shown is live state — if anything fails during a
> demo, say so and show the deploy log instead; the honesty machinery IS the pitch.

---

**[0:00–0:25] The one-liner.** "CropMind is crop-health screening that tells you what it
doesn't know. Farmers photograph a leaf; the product answers *Suspected* — never 'diagnosed'
— with a confidence band, and it abstains below a threshold instead of dressing up a guess."

**[0:25–0:55] Model truth, live.** *[Landing page — point at the truth panel chips.]*
"Everything about the model is read live from this deployment, not written into marketing.
Right now this chip says *serving: real model — remote*, integrity sha256-pinned. And here
are the only two accuracy numbers we ever quote, **always together**: in-domain top-1
**0.9959** — strong — and PlantDoc field out-of-distribution **0.2349** — a real gap,
published on our own homepage. You will not find another ag-AI landing page quoting its
field failure next to its lab score."

**[0:55–1:40] One analysis, real model.** *[Analyze → bundled sample picker →
"Tomato — Early blight (in-domain photo)".]*
"This toggles a bundled sample, labelled with provenance and what to expect. Upload, analyse.
… Here: *Suspected Tomato - Early blight - 91% confidence*, HIGH band — that wording is
verbatim everywhere in the system; uncertainty score beside it; Grad-CAM overlay with its own
caveat that highlights are contributors, not disease locations. Model version, dataset
version, latency — all printed on the result."

**[1:40–2:10] The honest edge.** *[Same picker → "Tomato — Early blight (field photo)".]*
"Same disease, but a real field photo — the family our 0.2349 number describes. In rehearsal
this exact image made the system **abstain**: *Inconclusive … below the LOW band — retake or
request agronomist review.* That is the feature: a product that says *we don't know* when it
doesn't. (If it answers this time, read the band: LOW stays visibly LOW — never upgraded.)"

**[2:10–2:40] Human review + evidence PDF.** *[Open the previous analysis → zones → approve →
report.]*
"SUSPECTED findings can generate intervention zones — explicitly a **simulation pending human
review**; I approve one as the human in the loop. The PDF field report: demo-path docs carry
a bold **DEMO TRIAL** banner naming the real model *with both evaluation figures*; the zone
review ledger prints my APPROVED decision; and there is **no chemical product or dosage
guidance anywhere** — by design, enforced by tests."

**[2:40–3:00] Close.** "Open source, MIT licence, every test above green in CI, a deployment
log that records its own crashes and my wrong first guesses verbatim, and a full business
package in the repo. £0 spent on infrastructure so far. Every claim in this demo is checkable
in the repository before you finish this sentence."

---

## Honesty rules for any future edit of this script

1. Both evaluation figures appear whenever either does, in-domain first, gap stated plainly.
2. Rehearsed outcomes are quoted **verbatim with dates** (see walkthrough-checklist.md);
   if a live rerun differs, the *live* result is narrated with its band — never covered up.
3. No capability beyond the current build; the roadmap belongs in the pitch deck, not the demo.
4. Free-tier wake/latency comments get explained, not apologized through.
