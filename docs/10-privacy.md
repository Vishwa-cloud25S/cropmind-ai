# 10 — Privacy Notice (self-hosted MVP)

**Status:** Phase 11 · **Last reviewed:** 2026-08-11 · **Audience:** operators running the MVP,
pilot farmers/agronomists using it, and reviewers of the endorsement evidence pack.

CropMind AI is **self-hosted**: the software and its database run on the operator's own machine
(`docker compose up`). Nothing is transmitted to CropMind AI's founder or any third party by the
application itself. This notice describes the data the software handles, so a pilot operator can
make their own lawful basis determination. It is written to be true about the code, not to
impress.

---

## 1. What data the system stores

| Category | Contents | Where it lives |
|---|---|---|
| Account | email, bcrypt password hash, role | `users` table |
| Session | issued JWTs (claims only), revoked-token denylist (`jti`, expiry) | `revoked_tokens` table |
| Imagery | your uploaded field photos — **re-encoded** JPEG + 384 px thumbnail, sha256, dimensions, capture-time note | `upload_dir` volume + `images` table |
| EXIF | stripped at upload (§2); at most a boolean `gps_present` note survives | image payload JSON |
| Farms & fields | names, declared crop, optional **hand-drawn** field boundary (WGS84 polygon) | `farms` / `fields` |
| Analyses & predictions | model output contract verbatim: phrasing, confidence, band, uncertainty, severity proxy, regions, latency, model/dataset versions | `analyses` / `predictions` / `prediction_regions` |
| Intervention zones | image-space regions + human review state (`PENDING`/`APPROVED`/`REJECTED`, note, reviewer, timestamps) | `intervention_zones` |
| Simulation runs | operator-declared parameters + SIMULATION-labelled results | `simulation_runs` |
| Reports | generated PDF field reports (the artifact of record) | `upload_dir` volume + `reports` |
| Feedback | per-account verdicts on predictions (correctness, actual condition, quality, notes) | `feedback` |
| Audit trail | every mutating action: actor, action, entity, **client IP**, request id, timestamp | `audit_logs` |

## 2. GPS & EXIF policy (deliberate design)

- Uploaded JPEGs are decoded and **fully re-encoded server-side**. All EXIF metadata — including
  GPS coordinates — is stripped by that re-encode. The only surviving signal is an honest boolean:
  `gps_present: true` ("the original had GPS; we discarded it"), recorded so a reviewer knows a
  location existed and was **not** used.
- The **only geography in the system is what a human draws**: field boundaries are hand-drawn
  polygons on the map. Intervention zones are computed in **image-normalized coordinates**
  (`image-normalized-xyxy`, `georeference_source: "none"`) — the software never invents or
  back-fills a location from a photo, and the PDF reports and exports say so verbatim.

## 3. Who can see what

- `FARMER` accounts see their own rows plus legacy NULL-owner (pre-auth/demo) rows.
- `AGRONOMIST` and `ADMIN` see all rows (audit and review duties).
- Out-of-scope rows answer 404 without confirming existence (docs/09 §3).
- Demo mode: anonymous uploads are flagged `DEMO`, shared-visible, and **expire** — the demo
  cleanup deletes demo artifacts after the demo TTL (default 720 minutes). Demo rows are not
  retained history.

## 4. Third parties the browser contacts

Exactly one: **OpenStreetMap public tile servers** (`{s}.tile.openstreetmap.org`), queried by the
map pages to render background map tiles. Your field geometry is drawn client-side over those
tiles; **vector data is not sent to OSM** — but their tile servers do see ordinary HTTP requests
(IP, user-agent), as with any public map tile usage. The map carries the required
`© OpenStreetMap contributors` attribution. No analytics, trackers, ad networks, or font CDNs are
loaded anywhere in the app.

## 5. Data sharing, subprocessors

None in the self-hosted MVP. There is no server-side third-party integration (no cloud storage,
no telemetry, no error-reporting SDK). If a deployment later adds one (e.g., hosted Postgres in
Phase 12), this document must be updated in the same change — that is a written rule, not an
aspiration.

## 6. Retention & deletion

- **Demo artifacts**: deleted by the demo cleanup after the TTL (§3).
- **Account data, imagery, reports**: retained until the operator deletes them — the system keeps
  honest history on purpose (failed analyses stay visible; regeneration overwrites files, never
  silently forks). Deleting a farm cascades per the API design (409 surfaces dependent counts
  first).
- **Backups**: not automated at MVP — the operator owns `/var/lib/postgresql` and `uploads`
  Docker volumes and their lifecycle.

## 7. Legal-basis notes for pilot operators (not legal advice)

- Likely bases for a small invited pilot: **consent** (pilot participants sign up and upload) and
  **legitimate interests** (operating and auditing the pilot service).
- Personal data that could identify a person: account email, audit-log IPs, and any faces/locations
  accidentally captured in photos before server-side EXIF stripping. Coach pilot users to
  photograph leaves, not people.
- The software's prediction is **decision support with a human in the loop** — no automated
  decision with legal or similarly significant effect is made about any person.
- UK GDPR/EU GDPR obligations sit with the **operator's organisation**; this notice gives them the
  ground truth about data flows to write their own.

## 8. Changes to this notice

This notice is versioned with the repository. Any change to what data is collected or where it
goes must update this document in the same commit — same rule as §5.
