# Third-Party Licenses

**Audited:** 2026-08-11 · **Method:** license fields read from installed package metadata
(`pip-licenses` for Python, each package's own `package.json` for Node), not copied from memory.
Versions below are the ones installed in the reference dev environment on the audit date;
the repo pins minimum ranges (`>=`), so CI may resolve newer compatible versions. Regenerate any
time with the commands in §4.

This repository's own source license is recorded in `LICENSE`/README once the founder confirms
it (current candidate: MIT). Datasets, model weights and map data are **not** code dependencies —
they are catalogued separately in `docs/datasets.md` (and no dataset is redistributed by this
repo).

---

## 1. Runtime dependencies (ship with the app)

### Backend API & worker (Python — `backend/requirements.txt`, `docker-compose`)

| Package | Version (audited) | License | Notes |
|---|---|---|---|
| FastAPI | 0.141.1 | MIT | web framework |
| uvicorn[standard] | 0.52.1 | BSD-3-Clause | ASGI server |
| Pydantic / pydantic-settings | 2.13.4 / 2.15.0 | MIT / MIT | schema validation, settings |
| SQLAlchemy | 2.0.51 | MIT | ORM |
| Alembic | 1.19.1 | MIT | migrations |
| psycopg[binary] | 3.3.4 | **LGPL-3.0-only** | Postgres driver; used **unmodified** as a downstream dependency (§3) |
| Pillow | 12.3.0 | MIT-CMU (HPND-style) | image decode/verify/re-encode |
| python-multipart | 0.0.32 | Apache-2.0 | upload parsing |
| bcrypt | 4.3.0 | Apache-2.0 | password hashing |
| PyJWT | 2.13.0 | MIT | session tokens |
| reportlab | 4.5.1 | BSD-3-Clause | PDF field reports (base-14 fonts — no font embedding, no font license concern) |
| PyYAML | 6.0.3 | MIT | config files |
| httpx | 0.28.1 | BSD-3-Clause | dataset download scripts |

### ML stack (Python — `ml/requirements.txt`; worker container only)

| Package | Version (audited) | License | Notes |
|---|---|---|---|
| PyTorch | 2.13.0+cpu | Apache-2.0 (bundled component licenses per its `LICENSE`/`NOTICE`) | inference + training |
| torchvision | 0.28.0+cpu | BSD-3-Clause | MobileNetV3-Small backbone weights: BSD 3-clause (recorded in docs/06 model card) |
| NumPy | 2.4.4 | BSD-3-Clause (+0BSD/MIT/Zlib/CC0 components per its LICENSES dir) | arrays |
| Requests | 2.34.2 | Apache-2.0 | dataset provenance fetches |

### Frontend (Node — `frontend/package.json`)

| Package | Version (audited) | License | Notes |
|---|---|---|---|
| Next.js | 14.2.18 | MIT | framework |
| React / react-dom | 18.3.1 | MIT / MIT | UI |
| Leaflet | 1.9.4 | BSD-2-Clause | map rendering |
| react-leaflet (+ @react-leaflet/core) | 4.2.1 (+2.1.0) | **Hippocratic-2.1** | React bindings for Leaflet — see §3 |

### Map data (not bundled)

- **OpenStreetMap** map tiles/data: © OpenStreetMap contributors, ODbL 1.0. Tiles are fetched by
  the user's browser from the public OSM tile service at runtime; the attribution is rendered on
  every map. Nothing OSM-derived is redistributed by this repo.

## 2. Build / test / lint dependencies (not shipped to users)

| Package | Version (audited) | License |
|---|---|---|
| pytest | 9.1.1 | MIT |
| pytest-cov | 3.x | MIT (used for docs/11 measurements) |
| ruff | 0.16.2 | MIT |
| TypeScript | 5.9.3 | Apache-2.0 |
| Tailwind CSS | 3.4.19 | MIT |
| PostCSS / Autoprefixer | 8.5.26 / 10.5.4 | MIT / MIT |
| ESLint + eslint-config-next | 8.57.1 / 14.2.18 | MIT / MIT |
| Vitest | 2.1.9 | MIT |
| jsdom | 24.1.3 | MIT |
| @testing-library/react · jest-dom · user-event | 16.3.2 · 6.9.1 · 14.6.3 | MIT |
| @types/\* (node, react, react-dom, leaflet) | pinned in `package-lock.json` | MIT |

Transitive dependencies of the packages above are their MIT/BSD/Apache-compatible ecosystems;
the full transitive trees can be regenerated with §4.

## 3. Notable entries (the ones a reviewer should see)

- **psycopg[binary] — LGPL-3.0-only.** Used as an unmodified third-party dependency, installed
  from its published wheel and linked at runtime through its public API; no psycopg source is
  copied or altered. Under LGPL §4 that conveys the library in Unmodified form; its source is
  available upstream (`psycopg/psycopg`). If a future build vendors or patches psycopg, this row
  must be revisited **before** merge.
- **react-leaflet / @react-leaflet/core — Hippocratic License 2.1.** An ethical-use licence that
  is **not OSI-approved**; it permits use (including commercial) except in defined human-rights
  violations. Agritech decision support is comfortably inside its permissions, but because it is
  not a standard permissive licence this entry is called out for the founder's legal review
  before incorporation around the venture. The escape hatch, if ever wanted, is mapbox-gl or
  plain Leaflet (BSD-2-Clause) with hand-rolled React wrappers — a day or so of work.
- **PyTorch / NumPy** ship bundles of third-party components under their own `LICENSES`/
  `NOTICE` files (Apache-2.0, BSD variants, BSL-1.0, MIT, Zlib, CC0) — all permissive; their
  wheels carry those files verbatim.

## 4. Regenerating this file

```bash
pip install pip-licenses
pip-licenses --from=mixed --format=markdown   # python side, incl. transitive
cd frontend && npx license-checker --summary  # node side, incl. transitive
```

Any dependency added to `backend/requirements*.txt`, `ml/requirements*.txt` or
`frontend/package.json` must extend this file in the same commit — same rule as docs/datasets.md
for training data.
