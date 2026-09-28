# 08 — Data & IP Strategy

**Prepared:** 2026-09-28 · Includes **two open action items the founder must decide** (marked ⚠).

## 1. IP inventory

| Asset | Status today (verifiable) | Strategy |
|---|---|---|
| **Source code** (this repo) | Public on GitHub. ⚠ **No LICENSE file exists yet** — so despite the "open-source" branding in the footer, rights are technically all-reserved by default until one is added. | Add an OSI license. Recommendation: **MIT** (maximally permissive, standard for MVP credibility; compatible with every dependency except the already-flagged Hippocratic `react-leaflet`, see `THIRD_PARTY_LICENSES.md`). **Decision pending founder confirmation — then added to the repo immediately.** Apache-2.0 is the alternative if patent-grant language is preferred. |
| **Model weights** (`cropmind-leaf-classifier v0.1.0`) | Never in git (AD-008); served on the public deployment via out-of-band delivery with integrity pin (AD-009, `docs/12 §8`) | Treated as a proprietary runtime artifact: the product serves them but does not offer them for download; model-versions table keeps provenance. Extraction risk via API is accepted and documented (AD-009) — the moat is workflow + trust + data flywheel, not weight secrecy. Option registered: revisit if a future model becomes the primary asset. |
| **Model card + evaluation reports** (`docs/06`, `reports/`) | Public, versioned | Deliberately public — the paired in-domain/OOD numbers are the brand. |
| **Training data** | PlantVillage (Mendeley; licensing recorded in `datasets.md`/model card), PlantDoc CC BY 4.0 | Only licensed, provenance-recorded datasets ever train the model; the taxonomy gate (`supported_by_model`) enforces this in code. |
| **User imagery + annotations** | Stored per-account with owner scoping; feedback widget records correctness/actual condition with a stated "no automatic retraining" promise | **Farmers own their data.** Export and deletion are product requirements (API-level today, self-serve UI on the roadmap). Any future training use requires opt-in consent with a stated purpose — the "no automatic retraining" promise changes only via a documented, announced policy change, never silently. |
| **Brand "CropMind AI"** | ⚠ Unregistered | File a UK trademark at incorporation (class 9/42/44 — confirm with counsel) `[action item]`. Until then, consistent public use + dated repo history is the honest evidence of use. |

## 2. Farmer data rights (product commitments)

1. **Ownership:** a user's imagery, fields, zones and reports remain theirs; CropMind
   stores them to provide the service.
2. **Portability:** reports and zone geometry are already downloadable; full account
   export is a roadmap item, stated here as a commitment so architecture keeps it cheap.
3. **Deletion:** account deletion removes user rows (cascade rules reviewed per-release);
   audit-log pseudonymisation follows (see `docs/10` privacy posture).
4. **No shadow use:** feedback and imagery are not used for training without explicit
   opt-in (see table above) — this is written here so any future change is visibly a change.

## 3. UK GDPR posture `[pre-incorporation — counsel review at incorporation]`

- Roles: CropMind is **processor** for customer farm data, **controller** for account/auth
  and product-telemetry data; to be set out in customer terms at first paid pilots.
- Lawful bases: contract (service), legitimate interest (security logs — minimised),
  consent (any training opt-in).
- Special note: crop/field imagery is unlikely to be special-category data, but **field
  boundaries are location-linked** — treated as sensitive in access design (owner-scoped,
  audited) above the legal minimum, deliberately.
- ICO registration at incorporation `[action item]`; breach-runbook already exists in
  spirit via the audit log + incident-logged-honestly culture (see deploy log, docs/12 §7).

## 4. Open-core boundary (how open source and business coexist)

Open: the entire application, ML pipeline, simulator, docs and this business package.
Commercial: hosted operation, multi-farm reviewer tooling, future integration SLAs and
support. The boundary rule: **nothing a user relies on for honesty (labels, limitations,
evaluation numbers) may ever live only in the closed part.**
