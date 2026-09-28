# Demo rehearsal notes — measured outcomes (Phase 15)

Every number below was measured against the **public demo deployment**
(`https://cropmind-demo-api.onrender.com`, real model v0.1.0 served via AD-009)
on **2026-09-28 UTC**. Nothing here is aspirational — repeat the steps and you get
the same class of outcome. API routes are mounted at the service root (no `/api/v1`
prefix); the frontend is `https://cropmind-ai-theta.vercel.app`.

## R1 — Money-loop (in-domain leaf, anonymous demo path)

Input: bundled sample `pv-tomato-early-blight.jpg` (PlantVillage, CC0, re-encoded
retake — see "Dedupe" below).

| Stage | Endpoint | Measured |
| --- | --- | --- |
| Upload | `POST /images?demo=true` | **0.2 s** (HTTP 201/200) |
| Analysis create | `POST /analyses` | 0.2 s (accepted) |
| Prediction (warm worker) | `GET /analyses/{id}/prediction` | **≈4–38 s** end-to-end (see note) |
| Zone generation | `POST /analyses/{id}/intervention-zones` | **0.7 s**, 1 zone |
| Report generate | `POST /analyses/{id}/report?demo=true` | **0.45 s** (HTTP 201) |
| PDF download | `GET /reports/{uuid}/download?demo=true` | **0.09 s**, 4,700 bytes, 2 pages |

Outcome verdict (verbatim): **`Suspected Tomato - Early blight - 91% confidence`**
— band HIGH, `demo: true`, real weights (`weights_origin: remote-checkpoint`).

Report produced: **`CMA-20260928-9A9684`** (uuid `8f00afde-b0d0-4cf2-a26f-355a350752b9`).
PDF text extracted and machine-checked — all true:

- "DEMO TRIAL — analysed by the real cropmind-leaf-classifier v0.1.0 …" banner
- paired figures **0.9959** (in-domain) and **0.2349** (PlantDoc field OOD) printed together
- verbatim "…91% confidence" phrasing
- "INTERVENTION ZONES — SIMULATION PENDING HUMAN REVIEW" ledger
- image SHA-256 integrity line + "Sample (demo) weights: no"
- report ID `CMA-20260928-9A9684`

> Timing note: the demo runs on Render's free tier. A warm worker answers in
> ≈4 s; a cold worker (service spun down after idle, model re-fetch
> 230 MB + torch start) takes ≈38–60 s. The UI honestly shows the analysis as
> PENDING/RUNNING during that window. **Demo discipline: run one throwaway
> analysis 2 minutes before the live demo to warm the worker.**

## R2 — Coercion-proof (field photo → abstention)

Input: bundled sample `pd-tomato-early-blight-field.jpg` (PlantDoc, CC BY 4.0 field photo).

Outcome (verbatim): **`Inconclusive (Tomato - Yellow Leaf Curl Virus at 19% is below the
LOW band) - retake photo or request agronomist review`** — status INCONCLUSIVE,
no condition claimed, no zones by design. Prediction returned in **4.3 s** (warm).

This is the honesty-gate demonstration: the model does not dress up a guess when
the evidence is a real field photograph. The paired figures printed everywhere
(0.9959 in-domain / 0.2349 field OOD) predict exactly this behaviour — which is
why we quote them together on every surface.

## R3 — Adversarial text-image ("financial soup")

Input: a 640×480 rendered text page ("FINANCIAL SOUP / PESTICIDE DOSAGE: 2.5 L/ha /
NOT A LEAF"), i.e. someone trying to coerce a confident reading from non-leaf input.

Outcome (verbatim): **`Suspected Corn (maize) - Healthy - 37% confidence`** —
LOW band (LOW = 0.25–0.45 per `ml/configs/model.yaml`), disclosed as LOW.

**Investigation (honest):** this is the published M1 limitation made visible —
the backbone is an ImageNet leaf classifier with no leaf/non-leaf gate, so an
arbitrary image returns a low-confidence leaf-family guess instead of refusing.
It does NOT cross the MEDIUM band and it is always shown with its raw percentage
and band. Sitting mitigations on record: abstention for anything below LOW (0.25),
OOD figure published on every surface (0.2349), severity labelled "visual proxy",
and docs/15 lists "non-leaf imagery may return a low-band guess" as a known limit.
Phase-16+ candidates: a leaf-detector pre-gate; conformal rejection tuning.
The demo script handles this by showing R2 (abstention) as the coercion story and
naming this residual honestly if asked.

## Dedupe behaviour observed (designed, honest)

Re-uploading byte-identical sample files returns HTTP 409:
"these exact bytes are already stored under another account — content dedupe is
global, so the existing copy cannot be shared into your workspace". This is the
integrity model working: identical bytes already exist, and cross-account sharing
is refused. Rehearsals therefore use re-encoded "retakes" (quality-94 JPEG),
exactly as a real user retaking a photo would produce. The bundled in-app samples
avoid this for first-time demo users because each viewer's fresh capture differs.

## Model truth probe (R1 prerequisite)

`GET /model-info` returned `serving.weights_origin: remote-checkpoint`,
`weights_state: downloaded` (after first warm analysis; `pending-first-download`
immediately post cold-start), `integrity: sha256-pinned`, plus the evaluation pair
`0.9959 / 0.2349 (plantdoc)`. The landing-page Model Truth panel renders from this
exact block — the demo never hardcodes a model claim.
