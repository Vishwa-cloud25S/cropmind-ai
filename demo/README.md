# Demo Kit (Phase 15)

**Prepared:** 2026-09-28 · **For:** endorsing-body reviewers, partners, and anyone who gives
3 minutes to see what CropMind actually does. **Rule set:** the same honesty rules as the
product (docs/16) — suspected phrasing, paired evaluation figures, no chemical advice,
samples labelled with provenance, failures shown not hidden.

## Contents

| File | What it is |
|---|---|
| [demo-script-3min.md](demo-script-3min.md) | Word-for-word 3-minute demo script with timing beats |
| [walkthrough-checklist.md](walkthrough-checklist.md) | End-to-end walkthrough steps **with the verbatim rehearsal evidence** (executed live 2026-09-28 against the public deployment, real model serving) |
| [pitch-deck-outline.md](pitch-deck-outline.md) | Slide-by-slide outline — every claim carrying its source or its honest placeholder |
| [rehearsal-notes.md](rehearsal-notes.md) | Measured rehearsal outcomes against the live deployment (R1 money-loop timings + `CMA-20260928-9A9684`, R2 abstention, R3 honest non-leaf finding, dedupe behaviour) |
| [acceptance-sweep.md](acceptance-sweep.md) | Final acceptance sweep: every FR/NFR and docs/01 §7 item mapped to evidence |
| [media/](media/) | The 4 bundle samples as bytes, byte-identical to the in-app picker set |
| [samples policy](#sample-photos) | 4 bundled sample photos, provenance-pinned (below) |

## Sample photos

Four real leaf photos ship as static assets (`frontend/public/demo-samples/`) and appear in
the Analyze wizard as a labelled picker for anyone without a photo at hand (FR-20).
Provenance is declared per file in `frontend/lib/demo-samples.ts` and **byte-pinned**:
tests recompute each file's sha256 and compare against the recorded prefix — a silently
swapped image is a failing build.

| File | Domain | Source + license |
|---|---|---|
| `pv-tomato-early-blight.jpg` | in-domain (what 0.9959 describes) | PlantVillage Mendeley v1, **CC0 1.0**, via spMohanty/PlantVillage-Dataset mirror |
| `pv-potato-late-blight.jpg` | in-domain | PlantVillage Mendeley v1, **CC0 1.0**, same mirror |
| `pd-tomato-early-blight-field.jpg` | **field/OOD** (what 0.2349 describes) | PlantDoc test set, **CC BY 4.0** (Singh et al.), pratikkayal/PlantDoc-Dataset |
| `pd-potato-late-blight-field.jpg` | **field/OOD** | PlantDoc test set, **CC BY 4.0** (Singh et al.) |

## What this demo proves — and what it never claims

- **Proves:** the full workflow runs in public (upload → real-model inference → verbatim
  verdict → reviewable zones → evidence PDF), labels derive from truth on every surface,
  and the model's domain gap is demonstrated live rather than hidden.
- **Never claims:** field performance from in-domain samples; agronomic severity from a
  visual proxy; product/dosage guidance of any kind; revenue/traction of any kind.
