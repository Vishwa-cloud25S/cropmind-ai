# 01 — Product Requirements (PRD)

**Product:** CropMind AI
**Doc status:** Draft v0.1 — Phase 0 (2026-08-08)
**Owner:** Founder (Vishwaksha Odduri)
**Change policy:** updated at the end of every phase; breaking scope changes recorded in the changelog at the bottom.

---

## 1. Product statement

> CropMind AI converts crop-health imagery into explainable, geospatially localized
> intervention zones for precision crop protection.

It is **not** positioned as "AI that detects plant disease". Detection is the first step of a
longer workflow that ends in *reviewable, exportable, map-based treatment zones* that a human
approves or rejects. The product proposition is precision intervention, not diagnosis.

Workflow:

```
IMAGE → AI DETECTION → CONFIDENCE + UNCERTAINTY → LOCALIZATION → SEVERITY ESTIMATION
→ EXPLAINABILITY → FIELD/GPS MAPPING → PRECISION INTERVENTION ZONES
→ ESTIMATED INPUT SAVINGS (simulation) → HUMAN REVIEW → REPORT
```

## 2. Target users

**Primary (V1 focus):** small/medium farms, precision-ag operators, agricultural consultants,
agronomists, cooperatives.
**Secondary (later):** agri-tech companies, drone service providers, crop-protection companies,
research institutions, government programs.

## 3. Scope

### In scope for the MVP
- Local-first full-stack app: Next.js frontend, FastAPI backend, PostgreSQL, local ML worker.
- Auth (JWT), roles (FARMER / AGRONOMIST / ADMIN), farm & field management.
- Image upload (JPEG/PNG/TIFF), validation, thumbnails, metadata extraction, tiling for large imagery.
- Baseline ML: transfer-learned leaf classifier + localization/severity proxies, explainability (Grad-CAM).
- Leaflet/OpenStreetMap field maps; intervention zones; GeoJSON/CSV export ("simulation"-labelled).
- Spray decision support (risk level + review priority — no chemical/prescriptive output).
- Savings calculator & precision-spray simulator, both labelled **SIMULATION**.
- PDF field reports, dashboards, history, feedback capture, demo mode with sample imagery.
- Docs: model card, data card, architecture, security, privacy, testing, deployment, responsible AI.
- Free-tier deployment path documented; app always runnable locally.

### Explicitly out of scope (V1)
- Real drone hardware control, RTK GPS, live telemetry (interfaces only; simulators implemented).
- Pesticide product/dosage recommendation, regulatory compliance claims, agronomic prescriptions.
- Multi-tenant SaaS billing, payments.
- Claimed field-validated savings or efficacy.

## 4. Functional requirements

| ID | Requirement | Phase |
|----|-------------|:-----:|
| FR-01 | Register / login / logout; password hashing; JWT sessions; protected routes | 10 |
| FR-02 | Roles: FARMER (own data), AGRONOMIST (assigned review), ADMIN (system mgmt) | 10 |
| FR-03 | Farm CRUD | 6 |
| FR-04 | Field CRUD incl. boundary drawing on map | 6–7 |
| FR-05 | Image upload: single + batch; JPEG/PNG/TIFF; validation; size limits; thumbnails; EXIF/GeoTIFF metadata capture | 5 |
| FR-06 | Analysis jobs with status PENDING → PROCESSING → COMPLETED/FAILED via background worker | 5 |
| FR-07 | ML inference returning condition, confidence, uncertainty, model_version, latency | 3 |
| FR-08 | Localization of suspected regions (heatmap-derived regions → boxes; detector when trained) | 3–4 |
| FR-09 | Experimental visual-severity score, labelled "estimated visual severity" | 3 |
| FR-10 | Grad-CAM explainability overlay + honest UI caveat | 3 |
| FR-11 | Leaflet field map: boundary, detection regions, zones, historical observations, layer toggles | 7 |
| FR-12 | Intervention-zone generation; approve/reject; GeoJSON + CSV export labelled "precision intervention zone simulation" | 7 |
| FR-13 | Decision support per zone: risk level, observed condition, confidence, est. area, review priority | 7 |
| FR-14 | Savings calculator (field area, costs, affected %) labelled "Simulation" | 8 |
| FR-15 | Precision-spray simulator: field, zones, spray width, speed → route, treated/untreated area, time | 8 |
| FR-16 | Farm dashboard: fields, analyses, issues, high-risk zones, est. treated-area reduction, charts | 6 |
| FR-17 | Analysis history per field; field comparison | 6 |
| FR-18 | Feedback capture: correct? YES/NO/NOT_SURE + actual condition + notes + image quality (feeds future data strategy) | 10 |
| FR-19 | PDF field report (crop, field, image, condition, confidence, severity, zones, model version, limitations, review status, report ID) | 9 |
| FR-20 | Demo mode: no-account flow with 3–5 bundled sample images end-to-end | 15 |
| FR-21 | Admin panel: users, analyses, model versions, feedback, datasets, reports, audit logs, health | 10 |
| FR-22 | Health endpoint, request IDs, structured logs, inference timing | 5 |
| FR-23 | Audit logging of security-relevant events | 10 |
| FR-24 | `/model-info` and `/supported-crops` endpoints; limitations surfaced in UI | 3 |

## 5. Non-functional requirements

| ID | Requirement | Target / note |
|----|-------------|---------------|
| NFR-01 | Runs locally with `docker compose up` on a dev laptop | Phase 1 gate |
| NFR-02 | Free deployment path documented (Vercel + Render/Supabase or equivalents) with deploy date recorded | Phase 12 |
| NFR-03 | CPU inference for a 512px field image on a modern laptop | target ≤ 2.5 s (measured, then documented honestly) |
| NFR-04 | Upload ceiling | 25 MB default, configurable |
| NFR-05 | No secrets in git; `.env.example` only | continuous |
| NFR-06 | Accessibility: semantic HTML, keyboard nav, contrast ≥ WCAG AA on core flows | Phases 6+ |
| NFR-07 | Mobile-responsive dashboard and map | Phase 6+ |
| NFR-08 | Critical-flow e2e test (register → … → report) green in CI | Phase 11 |
| NFR-09 | Dataset-license gate: nothing enters training without an entry in `docs/datasets.md` with license status APPROVED | Phase 2+ |

## 6. First measurable MVP milestone — **M1 "Vertical slice"**

**Definition:** an unauthenticated demo user can upload (or pick) a tomato-leaf photo; the system
returns and persists a prediction with confidence band, Grad-CAM overlay, estimated visual
severity, and model version; the UI labelled with honest caveats; a PDF report downloads.

**Quantitative exit gates (report actuals, no manufactured numbers):**
1. Baseline classifier (MobileNetV3-Small transfer-learned on the approved PlantVillage
   4-crop subset) reaches **top-1 ≥ 0.80 on its held-out PlantVillage test split** for the
   supported classes.
2. The **same** model scored on PlantDoc (out-of-domain, field imagery) — actual number is
   reported in the eval report whatever it is (working target ≥ 0.50 top-1; a lower number is a
   documented finding, not a failure).
3. Confusion matrix, per-class precision/recall/F1, latency on CPU auto-generated into
   `reports/model_evaluation/`.
4. CPU inference ≤ 2.5 s/image on the dev machine.
5. Demo completes in ≤ 5 minutes end-to-end.

If any gate is missed, the miss is documented — M1 exists to measure, not to look good.

## 7. Full MVP acceptance checklist

Tracked from the master spec (§75). Current state: **all items pending** until the relevant phase lands.

- [ ] App accessible; Demo mode without account
- [ ] Image upload → processed → prediction + confidence + model version displayed
- [ ] Explainability + severity displayed
- [ ] Farm/field CRUD; analysis linked to field
- [ ] Map: field, regions, zones; zones approvable/rejectable; GeoJSON export
- [ ] Simulation run; PDF report; history; feedback; DB persistence
- [ ] Auth + OpenAPI docs; tests pass in CI
- [ ] README, deployment docs, model card, data card, responsible-AI doc
- [ ] Business plan, pitch deck outline, financial model, endorsement evidence framework (placeholders, no fabricated evidence)

## 8. Safety & honesty constraints (binding on every phase)

- Output phrasing: "Suspected {condition} — confidence {x}%" — never definitive diagnosis.
- No pesticide product/brand/dosage advice; decision support only with human verification prompts.
- All savings/impact numbers shown as **MODEL SIMULATION** until field trials exist.
- Explainability is a correlation visualization, never claimed as causal proof.
- No fabricated datasets/metrics/customers/interviews/approvals/testimonials — placeholders like
  `[INSERT VERIFIED …]` until evidence exists.
- Pesticide legal/approval claims only with authoritative citation, or not at all.

## 9. Assumptions & open questions

1. PlantVillage Mendeley license: Meta-Album datasheet records CC0 1.0; a Penn State mirror records
   CC BY 3.0 — re-verify at download (Phase 2). Attribution given regardless. See `docs/datasets.md`.
2. IP102 (pests) is academic-use-only upstream → excluded from V1; revisit with author permission or
   a properly licensed alternative.
3. Severity estimation has no public ground-truth dataset in scope → visual proxy only, replaced by
   segmentation-based method in later phases.
4. Free tier availability (Vercel/Render/Supabase) changes over time; doc dated at deployment.

## Changelog

- v0.1 (2026-08-08): Phase 0 draft created.
