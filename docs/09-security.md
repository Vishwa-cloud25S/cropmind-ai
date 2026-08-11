# 09 — Security Posture

**Status:** Phase 11 · **Last reviewed:** 2026-08-11 · **Scope:** the self-hosted MVP
(`docker compose up` on a single operator machine). Cloud deployment adds its own layer and
is documented where it lands (Phase 12).

This document describes what the system actually does today. Anything not implemented is
listed in §8 as a gap, not implied.

---

## 1. Threat model (what we defend against, honestly)

| # | Threat | In scope? |
|---|---|---|
| T1 | Credential theft → account takeover | ✅ password hashing, token expiry, server-side revocation |
| T2 | Cross-account data access (one grower reading another's analyses/reports) | ✅ ownership scoping with existence non-confirmation (404) |
| T3 | Account/User enumeration | ✅ generic auth errors; signup 409 is a **stated, accepted** residual (§8) |
| T4 | Malicious uploads (polyglot files, decompression bombs, oversized payloads) | ✅ magic-byte sniffing, Pillow decode+verify, size cap, full re-encode |
| T5 | Brute force / abusive write rates | ✅ per-IP rate limits (single-node caveat, §8) |
| T6 | Token replay after logout | ✅ server-side `revoked_tokens` denylist (checked every request) |
| T7 | XSS stealing session tokens | ⚠️ partial — React output-escapes by default; token lives in `localStorage` (trade-off stated in §6) |
| T8 | Multi-node / distributed abuse, DDoS at scale | ❌ out of scope for a single-machine MVP (see §8) |
| T9 | Model-theft via API (weights exfiltration) | ✅ weights are never served over the API; only derived artifacts (predictions, Grad-CAM, PDFs) are exposed |
| T10 | Dependency supply-chain CVEs | ⚠️ pinned ranges + CI build; automated CVE scanning is a listed gap (§8) |

## 2. Authentication

- **Passwords** are hashed with **bcrypt** (`bcrypt>=4.1,<5`) — per-user salt, self-describing
  hash string. Plaintext is never stored or logged. Policy: ≥10 chars with ≥1 letter and ≥1 digit;
  unmet rules are listed verbatim in the 422 response (documented, not hidden).
- **Tokens** are HS256 JWTs (PyJWT), 12-hour expiry, issued at register/login. The token carries
  `sub`, `role`, `jti`, `exp`; the `jti` is what makes logout real.
- **Logout is server-side**: the token's `jti` is written to the `revoked_tokens` denylist
  (migration `0005`) and every authenticated request checks it. A revoked token is dead
  immediately, not "within expiry" — pinned by
  `backend/tests/test_e2e_critical_flow.py` and `test_auth_api.py`.
- **JWT secret**: `JWT_SECRET_KEY` env var. If unset or left at the documented placeholder, the
  server generates an **ephemeral per-boot secret and logs a loud warning** (sessions then end at
  every restart — a failure you notice, never a silent insecure default). See
  `backend/app/services/security.py`.
- **No account enumeration on login**: wrong-email and wrong-password produce the same generic
  401 plus `WWW-Authenticate`. Failed logins are committed to the audit log **before** the 401
  is returned (the record survives the failure).
- **Bootstrap**: the **first registered account becomes ADMIN** — stated in the register
  response (`role_note`) and in the UI, never silent. Every subsequent account is `FARMER`.

## 3. Authorization & data scoping

Roles: `FARMER` (owns rows), `AGRONOMIST` (reads everything, no ownership writes),
`ADMIN` (everything, plus the admin console).

- Read scoping (v1, stated in scoped payloads): `FARMER` sees own rows **plus legacy
  NULL-owner rows** (pre-auth/demo records form a shared workspace); `AGRONOMIST`/`ADMIN` see all.
- **Out-of-scope rows answer 404**, and the error never says whether the row exists
  ("existence unconfirmed") — distinct from wrong-role writes, which answer **403 with the
  reason** (`403` is never used for existence).
- Every farm/image/analysis row created under an account records `owner_id` / `uploader_id` /
  `requested_by`; reports and exports inherit the analysis scope (joined ownership filter,
  not a separate policy that could drift).
- **Binary artifacts** (report PDFs, zone exports, stored imagery, Grad-CAM) obey the same
  rule: a bare unauthenticated browser navigation to a scoped artifact gets the by-design 404,
  which is why the frontend downloads them through an authenticated fetch → blob (fixed
  2026-08-11; regression-pinned in the e2e critical-flow test: owner 200 + real bytes,
  other user 404, anonymous 404).
- **Admin self-lockout is blocked**: an ADMIN cannot change their own role (409 — the
  no-admins-left footgun is denied, not warned). Role changes are audited OLD→NEW.
- Content dedupe is global by sha256: identical bytes under another account answer an honest
  409 instead of a metadata peek at someone else's image.

## 4. Rate limiting

- In-memory sliding window keyed by client IP: **auth endpoints 10/min**, **write endpoints
  120/min**. Over-limit → 429 with `Retry-After` and a `detail` that names the limit
  (no silent throttling).
- Honest caveat: the limiter is **per-process, in-memory**. It restarts with the process and
  does not coordinate across replicas. The store seam (`app/services/ratelimit.py`) is the
  documented swap point for a shared backend when the deployment outgrows one node (§8).

## 5. Upload pipeline (untrusted file handling)

`POST /images` runs, in order: streaming **25 MB cap** → **magic-byte sniffing** (the extension
and the declared content-type are never trusted; declared/magic mismatch → 400) → Pillow
decode+verify (parse bombs rejected, RAW/other formats rejected) → **EXIF orientation
normalization** → full **JPEG re-encode** to a new file (the persisted bytes are pixels we
decoded and re-wrote ourselves — embedded payloads, polyglot tricks and metadata do not
survive) → 384 px thumbnail → **sha256 dedupe**. Stored metadata carries the sha256 so the
integrity of every stored byte is verifiable later.

## 6. Transport, CORS, browser surface

- **MVP transport is plain HTTP localhost.** There is no TLS in compose; TLS termination is a
  deployment-layer responsibility and is called out in the deploy doc (Phase 12), not implied.
- CORS is an allowlist (`CORS_ORIGINS`, default `http://localhost:3000`) with credentials;
  `Content-Disposition` is the one exposed response header so honest artifact filenames reach
  the browser.
- **No auth cookies** — sessions ride the `Authorization` header, so classic CSRF does not
  apply. The trade-off: the token lives in `localStorage`, which any successful XSS could read.
  Current mitigations: React escapes rendering by default, there is no `dangerouslySetInnerHTML`
  in the codebase, and no third-party script tags. A stricter posture (httpOnly cookie + CSRF
  token, CSP header) is a listed gap in §8.
- The frontend's browser talks to exactly two hosts: the API and **OpenStreetMap tile servers**
  (map pages; see docs/10-privacy §Third parties). No analytics, no tag managers, no CDN fonts.

## 7. Auditability

- Every mutating route writes an `audit_logs` row: actor, action, entity, entity_id, client IP,
  request ID. Security-relevant events are guaranteed-logged: login failures (logged before the
  401), logouts, role changes (OLD→NEW), report generation, feedback, simulation runs.
- Request IDs: every HTTP request gets one (`RequestIDMiddleware`) and it propagates into audit
  rows and logs — an incident can be reconstructed request-by-request.
- Admin surfaces: `/admin/audit-logs`, `/admin/overview` counts, `/admin/feedback`,
  `/admin/users` — all ADMIN-only, all read paths scoped.

## 8. Known gaps and accepted risks (stated, not hidden)

| Gap | Status | Why acceptable at MVP / when it changes |
|---|---|---|
| Signup 409 reveals a registered email | **Accepted, disclosed** (docs/04 §3.10) | MVP farms are invited users; mitigation (verify-then-reveal) is post-MVP |
| In-memory rate limiter | accepted | single node; Redis swap at the documented seam when scaling |
| Token in `localStorage`; no CSP/httpOnly cookie | accepted, stated in §6 | no third-party JS today; revisit before public self-registration |
| No MFA, no email verification | accepted | password+policy only at MVP |
| No automated dependency CVE scanning in CI | **gap** | pins are minimum ranges; adding `pip-audit`/`npm audit` gate is queued for hardening |
| Plain HTTP in compose | accepted | TLS is a Phase-12 deployment-layer item |
| No automated backup/DR for Postgres volume | accepted | single operator machine; deployment phase revisits |
| Password reset flow | none | accounts are operator-created at MVP |

## 9. Responsible disclosure

Security issues: open a **private** report to the maintainer (GitHub → Security tab) or email
the address on the repository profile — please do not file public issues for exploitable
findings. We commit to an honest acknowledgement of what is and isn't a real risk in this
codebase, consistent with the honesty contract in docs/04 §2.
