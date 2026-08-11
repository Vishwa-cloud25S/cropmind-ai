# 11 — Testing & Coverage

**Status:** Phase 11 · **Measured:** 2026-08-11 (counts re-measured at Phase 12 deploy-cleanup `77c0da0`-era) ·
**Rule:** every number in this document is reproduced by the commands in §3; nothing aspirational
is presented as current.

---

## 1. Test inventory (counts as measured on 2026-08-11)

| Suite | Framework | Tests | Where it runs |
|---|---|---|---|
| Backend API/DB | pytest (TestClient + SQLite) | **118** | CI job `backend`, every push |
| ML pipeline | pytest + CPU torch | **112** | CI job `ml`, every push |
| Simulation engine | pytest (pure stdlib) | **10** | CI job `ml`, every push |
| Frontend components | vitest + Testing Library | **77** (12 files) | CI job `frontend`, every push |
| Static gates | ruff · eslint · tsc --noEmit · next build | — | CI jobs, every push |
| Integration | docker compose config + full image build | — | CI job `docker`, every push |

## 2. The critical-flow e2e (NFR-02/NFR-08 style gate)

`backend/tests/test_e2e_critical_flow.py` walks the **one unbroken golden path** through the real
HTTP surface and database, with the ML worker driven synchronously via a stub predictor that
returns the exact shipped contract (torch never loads in backend CI; model quality is the ml
suite's and the model card's job):

register (ADMIN bootstrap stated) → login → farm → field + drawn boundary → field-scoped upload →
analysis (202, honestly async) → 409-before-ready pin → worker tick → prediction
(**phrasing asserted verbatim**) → zones generated → human review APPROVED → zone CSV export
(SIMULATION label in filename **and** body) → report generate (zones-first rule) → report
download (real `%PDF` bytes, filename carries the human report ID) → feedback → logout
(**revoked token is dead immediately**) → audit trail contains `REPORT_GENERATED` + `AUTH_LOGOUT`.

It also pins the 2026-08-11 authenticated-downloads regression class: the report's existence is
unconfirmed (404) to another account and to an anonymous caller while the owner's download
returns bytes.

Deliberately API-level: the test asserts the HTTP/DB/honesty pipeline deterministically and fast
(~2 s). Browser-level e2e is an acknowledged gap (§5).

## 3. Reproduce everything

```bash
# backend (no GPU, no Postgres needed — tests use per-test SQLite)
pip install -r backend/requirements-dev.txt
cd backend && python -m pytest -q

# coverage exactly as measured for this document
pip install pytest-cov
cd backend && python -m pytest -q --cov=app --cov-branch --cov-report=term-missing

# ml (CPU wheels keep it laptop-scale)
pip install --index-url https://download.pytorch.org/whl/cpu torch torchvision
pip install -r ml/requirements-dev.txt
cd ml && python -m pytest -q --cov=. --cov-branch --cov-report=term-missing

# simulation engine (pure stdlib)
python -m pytest simulation -q --cov=simulation --cov-branch

# frontend
cd frontend && npm ci && npm run lint && npm run typecheck && npm test && npm run build
```

## 4. Coverage — measured (at Phase-11 close; counts since grew by +6 backend, +3 frontend), and the targets we set

Measured 2026-08-11 with `pytest --cov --cov-branch` (branch coverage, Python 3.13):

| Layer | Statements | Missed | Branches | Partial | **Branch cov.** |
|---|---|---|---|---|---|
| Backend `app/` | 2 103 | 125 | 408 | 60 | **92 %** |
| ML `ml/` | 2 466 | 272 | 496 | 63 | **87 %** |
| `simulation/` | 347 | 10 | 98 | 11 | **95 %** |
| Frontend components | not instrumented | — | — | — | see below |

**Targets (ratchet floors, not vanity numbers):** backend **≥ 90 %**, ml **≥ 85 %**, simulation
**≥ 90 %** branch coverage. The floors sit just under today's measured values; a change that
drops a floor must either restore coverage or move the floor *with the reason written next to it*
(never silently). Weakest modules today and why:

- `services/mlbridge.py` 54 % — real-checkpoint loading and sha256 verification run only where a
  real checkpoint exists (operator machine / staging); the demo path is what's unit-testable
  without weights. Raising this needs a tiny trained fixture checkpoint, which is a dataset-size
  question, not a test-effort question.
- `workers/analysis_worker.py` 65 % — the long-running poll loop is exercised one tick at a time;
  crash/retry branches are covered, idle-loop branches are not.
- `services/uploads.py` 82 %, `services/analysis.py` 80 % — residual miss is mostly defensive
  branches for corrupt-state paths.
- Frontend: percentage is **not instrumented** (vitest runs without coverage today). The suite's
  77 tests cover every interactive panel (wizard, analysis view, zones/reports/sim panels, auth
  forms); adding `--coverage` with a documented floor is a queued hardening item, stated here
  rather than implied.

## 5. What is deliberately NOT covered (gap register)

| Gap | Why it is out at MVP | When it changes |
|---|---|---|
| Browser-level e2e (Playwright), visual regression | infrastructure weight vs one author at MVP; API e2e pins the pipeline | before public beta |
| Load/performance automation | NFR-03 latency is measured on operator hardware and published in docs/06 (110.4 ms p95 warm); no load rig exists | pilot traffic justifies it |
| Adversarial security testing / fuzzing | beyond MVP scope; threat model + controls in docs/09 | security review before public release |
| Automated accessibility (axe) | manual a11y conventions (chips+text, aria-live polls) verified by review | UI hardening (Phase 12+) |
| Multi-replica rate-limit behaviour | limiter is single-process by design (docs/09 §4) | first multi-node deployment |
| Real drone-provider integration | providers are an intent-receipt seam by design (docs/02 §8) | a provider signs on |

## 6. How CI enforces this

`.github/workflows/ci.yml` runs four jobs per push/PR: **backend** (ruff + pytest),
**frontend** (lint, typecheck, vitest, production build), **ml** (ruff on ml+simulation, both
pytest suites), **docker** (`compose config` + full image builds — the images that pilots run).
A red job blocks merge on `main`. Coverage numbers above are reproducible locally (§3);
CI does not yet fail on a coverage floor — the honest floor lives in §4 and the CI gate for it
is queued (adding it without breaking on per-module noise is the remaining work).
