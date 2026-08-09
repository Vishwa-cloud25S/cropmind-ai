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
| GET | `/model-info` | Model status/version from `ml/configs/model.yaml` (`EVALUATED` for run 0.1.0 — PROMOTED only after deployment evidence), confidence bands, uncertainty/severity method labels, standing client notice |
| GET | `/supported-crops` | Taxonomy (`ml/configs/taxonomy.yaml` v0.2): 4 crops × 21 conditions, per-condition `confidence_threshold` + `supported_by_model` (all `true` since the reviewed 2026-08-09 flip — commit `c9f454f`), `model_available: false` until the serving stack loads a checkpoint live |

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
| GET | `/analyses/{id}` | Status payload: `status` (QUEUED → PROCESSING → COMPLETED \| FAILED), timestamps, `error` (on FAILED), embedded `job` (`status`, `attempts`, `max_attempts`) |
| GET | `/analyses/{id}/prediction` | **409** `{"detail": {"detail": "prediction not ready", "analysis_status", "poll"}}` until COMPLETED — never a partial prediction. Then the full prediction payload (§3.5 shape) |

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

## 4. Lifecycle states

| Row | States |
|---|---|
| `analyses.status` | `QUEUED` → `PROCESSING` → `COMPLETED` \| `FAILED` |
| `analysis_jobs.status` | `PENDING` → `RUNNING` → `COMPLETED` \| `FAILED` (terminal) \| back to `PENDING` (retry, `run_after` backoff) |
| `intervention_zones.review_status` (Phase 7) | `PENDING` → `APPROVED` \| `REJECTED` |

## 5. Error-code summary

| Code | Meaning here |
|---|---|
| 400 | Upload validation (empty, corrupt, declared/magic mismatch); invalid relation ids |
| 404 | Unknown image / analysis / prediction |
| 409 | Prediction requested before its analysis COMPLETED (includes current status + poll path) |
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

- **Phase 7:** `/intervention-zones`, zone review (APPROVED/REJECTED), GeoJSON/CSV export labelled "simulation".
- **Phase 9:** `/reports` + `/reports/{id}/download` (ReportLab PDF with report IDs).
- **Phase 10:** `/auth/*` (JWT, roles), per-user scoping, rate limiting, feedback capture.
