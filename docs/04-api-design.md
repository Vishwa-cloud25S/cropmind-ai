# 04 — API Design

**Status:** ✅ Phase 5 implemented (2026-08-09) · synced with `backend/app/api/v1/` · live OpenAPI at `/docs`
**Read with:** [02 — System architecture](02-system-architecture.md) §6–§10, [11 — Reliability plan](11-reliability-plan-testing.md)

This document is the REST contract as *implemented*. Where a future phase changes a
route the table says so — nothing here promises capability that is not wired today.

---

## 1. Conventions

| Topic | Rule |
|---|---|
| Mounting | All routes at the app root (single service); FastAPI serves OpenAPI at `/docs`, spec at `/openapi.json` |
| Request IDs | `RequestIDMiddleware` stamps every request; returned as `x-request-id` response header, included in structured logs, recorded on write audit rows |
| Auth | **Phase 10.** The schema is auth-ready (`users`, `requested_by`, `uploader_id` columns exist) but routes are open in Phase 5. Demo-mode sample imagery is the only unauthenticated content by design — everything else gains JWT in Phase 10 |
| Errors | Standard FastAPI shape `{"detail": "..."}`. Structured summaries add a dict body (`{"detail": {...}}`) where noted |
| IDs | UUIDv4 strings (36 chars), server-generated — never client filenames |
| Timestamps | UTC ISO-8601 |
| Pagination | `limit` (1–100, default 20) + `offset` on list endpoints |

## 2. Honesty contract (applies to every prediction payload)

These rules are not cosmetic — they are the product's integrity surface:

1. **`phrasing` is stored verbatim.** The model module produces exactly
   `Suspected {crop} - {condition name} - {x}% confidence`, or, below the LOW band,
   `Inconclusive ({crop} - {name} at {x}% is below the LOW band) - retake photo or request agronomist review`.
   The API stores and returns it unchanged; nothing is re-derived API-side.
2. **INCONCLUSIVE is a first-class outcome** (`status: "INCONCLUSIVE"`, `band: null`), never forced into a wrong label.
3. **Demo output is always flagged.** Predictions produced by the synthetic sample model carry `demo: true` on the prediction *and* the model-version object. Demo is plumbing evidence, never a field-performance claim.
4. **No chemical guidance.** Every prediction response embeds `client_notice` ("decision support requiring human verification … no chemical product or dosage guidance").
5. **Explainability caveats travel with regions.** `explainability_caveat` is on every prediction payload; `detection_regions` geometries carry `coordinate_space: "image-normalized-xyxy"` — image space, *not* geographic coordinates (geographic mapping is the Phase 7 FieldMappingProvider).
6. The **full model-module contract** (top-k, uncertainty, severity proxy, version fields, limitation notice, timestamp…) is preserved verbatim in `raw`.

## 3. Endpoints

### 3.1 Health

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Liveness — process is up. Never touches dependencies. `{"status": "ok", "service": "cropmind-api", "version": "…"}` |
| GET | `/health/ready` | Readiness — database reachable (`SELECT 1`). `200 {"status": "ready", "database": "ok"}`, else `503 {"detail": {"status": "not_ready", "database": "unreachable"}}` |

### 3.2 Model metadata (read-only, config-driven)

| Method | Path | Description |
|---|---|---|
| GET | `/model-info` | Model status/version from `ml/configs/model.yaml` (`PROMOTED` for run 0.1.0 since the reviewed 2026-08-11 live-serving flip — worker job 39bec3e6, prediction demo=false), confidence bands, uncertainty/severity method labels, standing client notice |
| GET | `/supported-crops` | Taxonomy (`ml/configs/taxonomy.yaml` v0.3): 4 crops × 21 conditions, per-condition `confidence_threshold` + `supported_by_model` (all `true` since the reviewed 2026-08-09 flip — commit `c9f454f`), `model_available: true` since the reviewed 2026-08-11 live-serving flip (analysis `6144ff30…`, demo=false, SUSPECTED 0.4311 LOW) |

### 3.3 Images

| Method | Path | Description |
|---|---|---|
| POST | `/images` | Multipart upload (`file`), optional `field_id`, `demo` query params. Validation pipeline (docs/02 §9): declared-type precheck → **magic bytes** (JPEG/PNG/WebP/TIFF — extensions never trusted) → Pillow decode+verify → EXIF-orientation normalize → RGB JPEG re-encode (longest edge ≤ 2048) + 384px thumbnail → sha256 dedupe. **201** `{"image": {…, "deduplicated": bool}}`. The client never gets the original bytes back — only the re-encoded copy. Rejections: `400` empty/corrupt/declared-mismatch, `413` > `MAX_UPLOAD_SIZE_MB` (25 MB default; enforced while streaming), `415` unknown magic bytes |
| GET | `/images/{id}` | Metadata row (`404`) |
| GET | `/images/{id}/download?thumb=false` | The stored re-encode (or thumbnail) as JPEG (`404`) |

Duplicate uploads (same sha256) return the **existing** image id with `deduplicated: true`;
the stray normalized copy is deleted, and the dedupe is audited (`IMAGE_UPLOAD_DEDUPLICATED`).

### 3.4 Analyses

| Method | Path | Description |
|---|---|---|
| POST | `/analyses` | **202 Accepted** — enqueue. Body `{"image_id": "…", "field_id": "…"?, "demo": bool}`. Returns `{"analysis_id", "job_id", "status": "QUEUED", "poll": "/analyses/{id}", "note"}` (`404` unknown image). The analysis row and its queue job are written in **one transaction** (FK safety, ADR-004) |
| GET | `/analyses?limit=20&offset=0&status=` | Newest-first page (history UI). `{"count", "analyses": [status payloads]}`. `status` is whitelisted {QUEUED, PROCESSING, COMPLETED, FAILED} → `400 {"detail": {"detail": "unknown status filter", "allowed": […]}}` on anything else |
| GET | `/analyses/{id}` | Status payload: `status` (QUEUED → PROCESSING → COMPLETED \| FAILED), timestamps, `error` (on FAILED), embedded `job` (`status`, `attempts`, `max_attempts`) |
| GET | `/analyses/{id}/prediction` | **409** `{"detail": {"detail": "prediction not ready", "analysis_status", "poll"}}` until COMPLETED — never a partial prediction. Then the full prediction payload (§3.5 shape) |
| GET | `/analyses/{id}/gradcam` | The stored Grad-CAM overlay as `image/png` (filename `cropmind-gradcam-<id8>.png`). **409** `{"detail": {"detail": "Grad-CAM overlay not available", "analysis_status"}}` until ready; `404` unknown analysis / stored file missing |

The worker (`app.workers.analysis_worker`, separate process/container) claims jobs with
heartbeat + attempts-aware backoff (`run_after = now + attempts² × JOB_RETRY_BACKOFF_S`),
reaps stale RUNNING jobs after `JOB_HEARTBEAT_TIMEOUT_S` (120 s), and mirrors every
transition onto the analysis row the API reads.

### 3.5 Predictions

| Method | Path | Description |
|---|---|---|
| GET | `/predictions?limit=20&offset=0` | Newest-first page: `{"count", "predictions": […], "client_notice"}` |
| GET | `/predictions/{id}` | Single prediction (`404`) |

Prediction payload (every field sourced from the stored contract):

```jsonc
{
  "prediction_id": "…", "analysis_id": "…",
  "status": "SUSPECTED",                     // or "INCONCLUSIVE"
  "phrasing": "Suspected corn - Northern Leaf Blight - 92% confidence",  // verbatim from the model module
  "crop": "corn",
  "condition": {"disease_id": "corn_northern_leaf_blight", "name": "Northern Leaf Blight"},
  "confidence": 0.9231, "band": "HIGH",      // band null when INCONCLUSIVE
  "uncertainty": 0.21,
  "estimated_visual_severity": 0.18,         // visual proxy — labelled as such via severity_label + raw
  "severity_label": "Estimated visual severity",
  "latency_ms": 101.5,
  "demo": true,                              // sample-model predictions, never silent
  "model": {"name": "cropmind-leaf-classifier", "version": "0.1.0",
            "dataset_version": "mendeley-v1", "threshold_version": "0.1", "demo": true},
  "regions": [{"geometry": {"type": "Polygon", "coordinate_space": "image-normalized-xyxy", …},
               "area_px": 553, "confidence": 0.9231}],
  "gradcam_available": true,
  "analysis_demo_requested": true,
  "client_notice": "…", "explainability_caveat": "…",
  "raw": { /* the complete Predictor contract from ml/inference/predictor.py, verbatim */ }
}
```

### 3.6 Farms & fields

Farm/field structure analyses attach to (Phase 6). `owner_id` stays NULL pre-auth — Alembic
migration `0002` made `farms.owner_id` nullable; Phase 10 assigns real owners and tightens
scoping. Every write is audited (`FARM_CREATED` / `FARM_UPDATED` / `FARM_DELETED`, `FIELD_*`).

| Method | Path | Description |
|---|---|---|
| POST | `/farms` | **201** `{"farm": {id, name, location, field_count, created_at}}` |
| GET | `/farms?limit=50&offset=0` | Newest-first `{"count", "farms": […]}` |
| GET | `/farms/{id}` | `{"farm": {…}, "fields": [{id, farm_id, name, crop_id, area_ha, created_at}]}` (`404`) |
| PATCH | `/farms/{id}` | Rename / move (`404`) |
| DELETE | `/farms/{id}` | **204** — **409** `{"detail": {"detail": "farm still has fields — delete them first", "field_count"}}` while fields exist (never silently destructive) |
| POST | `/farms/{farm_id}/fields` | **201** `{"field": {…}}`. `crop_id` is validated against the taxonomy's crop ids → **400** `{"detail": {"detail": "unsupported crop_id", "allowed": […]}}` (closed vocabulary — e.g. wheat is honestly rejected until licensed data + honest evaluation add it) |
| GET | `/fields/{id}` | Single field (`404`) |
| PATCH | `/fields/{id}` | name / crop_id (re-validated) / area_ha / **boundary_geojson** — user-drawn WGS84 polygon, strictly validated (closed ring, ≥3 distinct corners, lon/lat ranges; `400` with the precise reason otherwise) (`404`) |
| DELETE | `/fields/{id}` | **204** — **409** `{"detail": {"detail": "field is still referenced", "image_count", "zone_count"}}` while images or intervention zones reference it |

### 3.7 Intervention zones & field map (Phase 7)

**Geo-honesty (architectural, enforced here).** Image GPS coordinates are *stripped at
upload* — privacy by design (docs/02 §9) — so the system cannot know where a leaf photo
was taken, and refuses to invent it. Every zone is stored and returned in the evidence's
own coordinate space (`image-normalized-xyxy`) with `georeference_source: "none"` until a
genuinely georeferenced source (drone orthomosaic with a GeoTIFF transform) provides an
honest pixel→geo mapping. `est_area_ha` is `null` with an explanatory `area_note` whenever
scale is unknowable. Field *boundaries* are the only geographic data, because the user
draws them directly (§3.6 boundary validation).

**Zone generation.** From a COMPLETED SUSPECTED analysis only — an INCONCLUSIVE analysis
generates **no zones** (the system abstained; there is honestly nothing to intervene on,
and the response says so). One zone per detection region. Regeneration replaces PENDING
zones but never touches APPROVED/REJECTED ones (human decisions are not silently
overwritten).

**Risk & review priority (deterministic rule, not a model).**
`score = band_score (LOW→1, MEDIUM→2, HIGH→3) + 1 if visual-severity proxy ≥ zone_severity_critical (0.5 default)`;
score→level at 1/2/3/4 = LOW/MEDIUM/HIGH/CRITICAL. Priority: CRITICAL→1 (review first),
HIGH→2, MEDIUM→3, LOW→4. Payloads carry `risk_basis` describing the stored evidence the
rule consumed. Zones carry no pesticide/product/dosage content — they are
precision-intervention *simulations* pending human review.

| Method | Path | Description |
|---|---|---|
| POST | `/analyses/{id}/intervention-zones` | **201** — generate. `{"count", "zones", "note", "simulation_label"}`; count 0 + abstention note for INCONCLUSIVE. **409** (status + poll) until COMPLETED, `404` unknown. Audited `ZONES_GENERATED` |
| GET | `/intervention-zones?field_id=&review_status=&limit=&offset=` | Newest-first `{"count", "zones", "simulation_label"}`. `review_status` whitelisted → `400` with `allowed` |
| GET | `/intervention-zones/{id}` | Single zone (`404`) |
| PATCH | `/intervention-zones/{id}` | Body `{"review_status": "APPROVED"\|"REJECTED", "review_note"?}` — records `reviewed_at`, returns `review_transition` "OLD → NEW" (re-review allowed, always recorded). Audited `ZONE_REVIEWED` per transition (`404`, `422` invalid target) |
| GET | `/intervention-zones/export?field_id=&review_status=&format=geojson\|csv` | Labelled download: filename `cropmind-zone-simulation-…`, GeoJSON carries a top-level `simulation` foreign member + per-feature properties, CSV starts with a `# … simulation` row + `simulation_label` column. `400` unknown format |
| GET | `/fields/{id}/map-data` | One aggregate read for the map page: field (+boundary, farm name), latest ≤100 analyses with prediction summaries, zones, and `decision_support` (risk/review counts, pending count, up-to-3 first-priority pending zone ids, rule note: *review order, not an agronomic risk score*) (`404`) |

### 3.8 Simulator (Phase 8)

**Simulation honesty.** The engine (`simulation/`, provider Protocols per docs/02 §8) does
labelled arithmetic only: *areas the user marked × a rate the user declared*. Treatment
polygons are user-drawn WGS84 validated exactly like field boundaries — image-space zones
are never auto-scaled into hectares (they inform where the operator marks; §3.7). The rate
is whatever the user types; non-positive rates are rejected (`422`) and the API never
suggests one. Every run persists params + labelled result verbatim (migration `0004`) so any
savings figure can be re-derived later — "files win" applies to simulation too. Engine rules
(documented, deterministic): exact polygon areas in a planar anchor projection (
error « 1% at field scale), boustrophedon route at swath centrelines, turns = straight joins
+ declared per-swath overhead, swath cap 2000 with the measured count in the error. A
simulated drone provider proves the API→hardware seam and returns an intent receipt —
**no aircraft exists** (`docs/02 §8`: real vendors plug in behind the same Protocols).

| Method | Path | Description |
|---|---|---|
| POST | `/simulations/spray-plan` | **201** `{"simulation": {…params + labelled results…}}`. Body: `field_id`, `treatment_polygons` (1–50 WGS84 polygons), `spray_width_m` (0.25–50), `speed_mps` (0.1–30), `declared_rate_l_per_ha` (>0, ≤2000), `turn_overhead_s` (0–60 default 0). Results: exact areas (ha), treated fraction, swath count, spray-on/route lengths, est. time, blanket vs precision volumes, savings (labelled planning illustration), route GeoJSON, assumptions, provider receipt, engine version + honesty notice. **409** no drawn boundary · **404** unknown field · **400** polygon/geometry/engine constraint (reason verbatim: unclosed, outside boundary, overlap, measured swath cap). Audited `SIMULATION_RUN_CREATED` |
| GET | `/simulations?field_id=&limit=&offset=` | Newest-first summaries `{"count", "simulations", "note"}` with `key_results` only (detail lives on the stored row) |
| GET | `/simulations/{id}` | Full stored run — params + results as first served (`404`) |
| GET | `/simulations/{id}/route.geojson` | Stored route download; filename + top-level member carry the simulation label (`404`) |

### 3.9 Reports (Phase 9)

**Report honesty.** A field report is the *printable record of stored evidence*, never a
polished-up story: the Suspected phrasing travels verbatim from the stored prediction
contract; INCONCLUSIVE renders as an explicit abstention ("the system ABSTAINED…", retake
guidance, no zones by design); the zone section is a *review ledger* (PENDING / APPROVED /
REJECTED per zone, with reviewer notes) carrying the image-space/georeference-none labels
and no product, chemical or dosage content; demo analyses get a bold DEMO banner on page
one. One report row per analysis: generation is explicit and audited; regeneration keeps
the human `report_id` (`CMA-YYYYMMDD-XXXXXX`) and overwrites the same file so no stale
copy survives silently — **files win**: the PDF under `upload_dir` is the artifact of
record, API payloads are snapshots of its build basis. A SUSPECTED analysis cannot
produce a report until its intervention zones exist (the full ledger must be on it);
the 409 says so and points at zone generation.

| Method | Path | Description |
|---|---|---|
| POST | `/analyses/{id}/report` | **201** — generate or regenerate the PDF. Response `{"report": {…full payload incl. build basis…}}`. **404** unknown analysis · **409** prediction not complete (`poll` included) or SUSPECTED-without-zones (actionable hint). Audited `REPORT_GENERATED` per generation |
| GET | `/analyses/{id}/report` | Always 200 for a known analysis: `{"status": "READY", "report": {…}}` or `{"status": "GENERATE", "report": null, "why": …}` — the UI renders an explanation + Generate button instead of forcing a 404 flow (`404` unknown analysis) |
| GET | `/reports?limit=&offset=` | Newest-first summaries `{"count", "total", "reports", "note"}` with `key_facts` (phrasing, prediction status, zone review totals) — light history surface; the file stays the artifact |
| GET | `/reports/{id}` | Full payload including the build basis (`404`) |
| GET | `/reports/{id}/download` | The PDF artifact; filename `cropmind-field-report-{report_id}.pdf` (`404` unknown, **409** file missing on disk with regenerate hint) |

### 3.10 Auth, sessions & scoping (Phase 10)

**Security honesty.** Passwords are bcrypt-hashed (`$2b$`, self-describing). Sessions are
HS256 JWT access tokens, 12 h by default; sign-out writes the token's `jti` to the
`revoked_tokens` denylist and every authenticated call checks it — **logout really
revokes** (no client-side theatre). `JWT_SECRET_KEY` unset/placeholder ⇒ an ephemeral
per-boot secret is used with a loud startup warning (tokens die on restart; that is
stated, not hidden). Login failures return one generic `401 invalid email or password`
for unknown email AND wrong password (no account enumeration), with
`WWW-Authenticate: Bearer`. A failed login is committed to the audit log *before* the
401 is raised — security events must survive request rollback. A present but
invalid/expired/revoked token is a hard 401 (never silently downgraded to anonymous);
an absent header means anonymous, and each endpoint applies its own rule.

**Bootstrap & roles.** The first registered account becomes `ADMIN` (one-time,
documented, surfaced in the response and the UI); every later account is `FARMER`;
`AGRONOMIST`/`ADMIN` are assigned by an admin. Role writes answer 403 with
`your_role` + `requires`; an admin cannot change their own role (409 — the
no-admins-left footgun is blocked, not warned about).

**Scoping v1 (stated in scoped payloads).** `FARMER` sees rows they own plus legacy
NULL-owner rows (pre-auth/demo records form a shared workspace); `AGRONOMIST` and
`ADMIN` see all; out-of-scope rows answer 404 (existence not confirmed). Writes that
create farms/fields/upload-and-plan require `FARMER` or `ADMIN`; reviewers read. Every
farm/image/analysis row created under an account records `owner_id`/`uploader_id`/
`requested_by`. Demo mode keeps a clearly-flagged anonymous path: with `DEMO_MODE`
on, anonymous callers may upload+analyse with `demo=true` only — stored as `DEMO`,
always flagged. Content dedupe is global (sha256): identical bytes under another
account answer an honest 409 instead of a metadata peek.

**Binary artifacts (2026-08-11 hardening).** Report PDFs, zone exports, stored imagery
and Grad-CAM overlays are served from the same scoped routes, so they obey the same
visibility rule — which means a bare browser navigation (`<a href>` / `<img src>`,
which carries no `Authorization` header) anonymously hits the by-design 404 even when
the row exists. The frontend therefore downloads/shows every artifact through an
authenticated `fetch` → blob (object URL), and CORS exposes `Content-Disposition` so
the server-set, honestly-labelled filename reaches the browser. A failed download
surfaces the real status in the UI — it never silently succeeds or shows a broken
image; error pages are not a workaround surface.

| Method | Path | Description |
|---|---|---|
| POST | `/auth/register` | **201** `{access_token, token_type, expires_at, expires_in_s, user, role_note}`. Email sanity + password policy (≥10 chars, letter+digit — unmet rules listed verbatim, 422); 409 existing address (signup enumeration stated, mitigation post-MVP); first account = ADMIN |
| POST | `/auth/login` | **200** token payload; **401** generic message (+ `WWW-Authenticate`); failed attempts audited `AUTH_LOGIN_FAILED` |
| POST | `/auth/logout` | Revokes the presented token server-side (denylist), audited `AUTH_LOGOUT`; **200** `{detail}` stating revocation is real |
| GET | `/auth/me` | `{user, session{expires_at, issuer, revocation}}` — session truth from the server, not from local state (`401`) |

### 3.11 Feedback, admin & rate limiting (Phase 10)

Feedback (FR-18) is per-account by design — a verdict that can't be attributed can't be
audited; submissions state they inform the data strategy and that **no automatic
retraining** happens. The admin surface (FR-21 v1) is ADMIN-only. Rate limiting
(§3.11) is an in-memory per-process sliding window keyed by client IP — honest for the
single-instance MVP; a shared store slots in behind the same 429 contract for
multi-replica deployments.

| Method | Path | Description |
|---|---|---|
| POST | `/analyses/{id}/feedback` | **201**; body `{correctness: YES\|NO\|NOT_SURE, actual_condition?, notes?, image_quality?}`; `401` anonymous · `404` unknown/out-of-scope · `409` prediction not complete · `422` invalid enum. Audited `FEEDBACK_SUBMITTED` |
| GET | `/analyses/{id}/feedback` | Own verdicts; ADMIN/AGRONOMIST see all rows for the analysis with author attribution |
| GET | `/admin/users` | ADMIN only: users + farm counts + bootstrap note (`403` otherwise) |
| PATCH | `/admin/users/{id}/role` | Role change, audited `AUTH_ROLE_CHANGED` OLD → NEW; `409` self-change blocked; `422` invalid role |
| GET | `/admin/feedback` | All verdicts with authors + `by_correctness` tallies |
| GET | `/admin/audit-logs?limit=` | Newest-first security trail |
| GET | `/admin/overview` | Measured-at-request-time counts (incl. per-status breakdowns) — never cached marketing numbers |

**Rate limits** (config: `RATE_LIMIT_AUTH_PER_MINUTE` default 10, `RATE_LIMIT_WRITE_PER_MINUTE`
default 120, `RATE_LIMIT_ENABLED` default true): `429` with `Retry-After` header and a body
saying what was limited and when to retry.

## 4. Lifecycle states

| Row | States |
|---|---|
| `analyses.status` | `QUEUED` → `PROCESSING` → `COMPLETED` \| `FAILED` |
| `analysis_jobs.status` | `PENDING` → `RUNNING` → `COMPLETED` \| `FAILED` (terminal) \| back to `PENDING` (retry, `run_after` backoff) |
| `intervention_zones.review_status` (Phase 7) | `PENDING` → `APPROVED` \| `REJECTED` |
| `reports` (Phase 9) | no state machine — one row per analysis; `generated_at` refreshes on every explicit regeneration (human `report_id` stable) |
| `auth sessions` (Phase 10) | JWT valid → revoked (logout, `revoked_tokens` jti denylist) \| expired (12 h TTL) |
| `users.role` (Phase 10) | `FARMER` (default) · `AGRONOMIST` · `ADMIN` (first-account bootstrap, then admin-assigned; self-change blocked) |
| `feedback.correctness` (Phase 10) | `YES` \| `NO` \| `NOT_SURE` (immutable rows; new verdicts append) |

## 5. Error-code summary

| Code | Meaning here |
|---|---|
| 400 | Upload validation (empty, corrupt, declared/magic mismatch); invalid relation ids; unsupported `crop_id` (taxonomy whitelist, `allowed` listed); unknown analysis-status / review-status filter / export format; invalid field boundary (precise validator reason) |
| 401 | Missing/invalid/expired/revoked session (carries `auth` reason + `WWW-Authenticate: Bearer`); wrong credentials (one generic message, no enumeration) |
| 403 | Authenticated but wrong role for the action (carries `your_role` + `requires`) |
| 404 | Unknown image / analysis / prediction / farm / field / intervention zone / simulation run / report; stored Grad-CAM file missing; **also rows outside your scope** (existence stays unconfirmed) |
| 429 | Per-IP rate limit exceeded (bucket + `retry_after_s` + `Retry-After` header; §3.11) |
| 409 | Prediction, Grad-CAM or zone generation requested before its analysis COMPLETED (includes current status + poll path); delete of a farm/field that still has dependents (carries the honest blocking counts); spray simulation against a field with no drawn boundary; report generation before its basis exists (prediction incomplete, or SUSPECTED without zones — actionable hint included); stored report PDF missing on disk (regenerate hint) |
| 413 | Upload exceeds `MAX_UPLOAD_SIZE_MB` (enforced while streaming) |
| 415 | Unrecognized image bytes (magic-byte sniff failed) |
| 503 | `/health/ready` with database unreachable |

## 6. Seeded reference data

`python -m app.db.seed` (worker container startup) upserts `dataset_sources` from
`ml/data/registry.py` — PlantVillage (`mendeley-v1`, CC0-1.0) and PlantDoc
(`github-master-2026-08-08`, CC-BY-4.0) with URLs and recorded limitations.
`image_count` stays `NULL` until *measured*; `verified_at` stays `NULL` (seeding copies
the audited registry record — it is not itself a re-verification). Idempotent.

## 7. What lands later (documented deltas)

- **Geo growth (when a georeferenced source is ingested):** genuinely geographic zones arrive
  only with a drone orthomosaic carrying a GeoTIFF transform (post-MVP geo milestone) —
  only then does `georeference_source` become something other than `"none"` and
  `est_area_ha` become computable (see §3.7 geo-honesty).
