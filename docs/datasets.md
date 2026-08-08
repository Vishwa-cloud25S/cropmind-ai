# Datasets — Research & Provenance Register

**Register v0.5 — last verified 2026-08-08.** Owner: founder.

**Gate rule (NFR-09):** no dataset enters the training pipeline unless it has a completed row
below with an APPROVED decision, its provenance (`source_url`, version/date, image count,
classes, known limitations, license + license URL) is recorded in a `PROVENANCE.json` at
download time (`ml/data/download.py`), and — once the backend exists — in the `dataset_sources`
table. Datasets are never committed to git and never silently combined: every image keeps a
`source` namespace and every skipped class folder is recorded in split manifests.

---

## Candidate register

| # | Dataset | Source / paper | License (verified 2026-08-08) | Size & classes | Annotation | Role in CropMind | License risk | Decision |
|---|---------|----------------|-------------------------------|----------------|------------|------------------|--------------|----------|
| 1 | **PlantVillage** — Mendeley mirror (v1) | Arun Pandian & Geetharamani, [Mendeley DOI 10.17632/tywbtsjrjv.1](https://data.mendeley.com/datasets/tywbtsjrjv/1); related paper [10.1016/j.compeleceng.2019.04.011](https://doi.org/10.1016/j.compeleceng.2019.04.011) (*Computers & Electrical Engineering* 76:323–338); underlying collection: Hughes & Salathé (2015), arXiv:1511.08060 | **CC0 1.0** — public domain. Confirmed 2026-08-08 by **two independent authoritative sources**: the page's Licence section *and* the [DataCite DOI metadata](https://api.datacite.org/dois/10.17632/tywbtsjrjv.1) rightsList ("Public Domain Dedication", record updated 2025-04-10). Attribution given regardless. | 61,486 images; 39 classes (38 leaf classes incl. our 4 crops + `Background_without_leaves`, excluded by policy) | image-level labels | V1 classification baseline (4-crop subset) — **acquisition via manual import: automated download is HTTP-403 refused by the source (see below)** | Low | **APPROVED** |
| 2 | **PlantDoc** | Singh et al., CoDS-COMAD 2020 (IIT Gandhinagar), [classification repo](https://github.com/pratikkayal/PlantDoc-Dataset), [Dataset Ninja summary](https://datasetninja.com/plantdoc) | **CC BY 4.0** — LICENSE.txt fetched verbatim from the repo 2026-08-08; attribution text shipped in model/data cards | train/ + test/ trees; **28 class folders verified via GitHub API** (note: no healthy-Potato folder in train/) | image labels; bounding boxes in the separate [object-detection mirror](https://github.com/pratikkayal/PlantDoc-Object-Detection-Dataset) | out-of-domain evaluation of the V1 classifier; detection training in Phase 4 via the detection mirror | Low | **APPROVED** |
| 3 | **Plant Pathology 2020 (FGVC7)** | Khan Lab, Cornell; Thapa et al., *Appl. Plant Sci.* 8(9):e11390 (2020); [Kaggle competition](https://www.kaggle.com/c/plant-pathology-2020-fgvc7); [project page](https://blogs.cornell.edu/applevarietydatabase/machine-learning-for-disease-detection/) | Dataset "freely available to download on Kaggle" (paper); exact license per Kaggle competition terms — **verify at download** | ~3,651 expert-annotated RGB apple-leaf images (scab 1,200 / rust 1,399 / complex 187 / healthy 865) + competition test set | image-level labels (multi-label capable) | optional Apple baseline / DSLR+smartphone robustness check | Medium (Kaggle terms govern) | **CONDITIONAL** — only if terms check passes |
| 4 | **IP102 (insect pests)** | Wu et al., CVPR 2019; [official repo](https://github.com/xpwu95/IP102) | **"Free for academic usage. For other purposes, please contact the author"** (official repo, verified). A [Roboflow Universe mirror](https://universe.roboflow.com/roboflow-public/ip102-insect-pest-recognition) labels its copy CC BY 4.0 — a re-host cannot grant broader rights than upstream, so that label is **not** relied on. | 75,222 images; 102 pest classes; ~19k with boxes | image labels + boxes (subset) | future pest-detection module (post-V1) | **High** (non-commercial upstream) | **DEFERRED — excluded** until written permission or a properly licensed alternative |
| 5 | **OpenAerialMap** (per-asset) | [openaerialmap.org](https://openaerialmap.org) | Per-uploader licenses, commonly CC BY / CC BY-NC — **checked per asset at download** | n/a | orthomosaics | demo orthomosaic & spray-simulation basemap; **not** training data | Low–Medium (per-asset) | **APPROVED, per-asset attribution recorded** |
| 6 | **USDA NAIP** (optional, US) | USDA FSA | Public domain (US Gov work) | n/a | aerial imagery | simulated field imagery in demo mode | Low | **APPROVED (optional)** |
| 7 | **Copernicus Sentinel-2** (deferred) | ESA/Copernicus | Free, full and open access (EU Reg. 1159/2013) | n/a | multispectral | field-context layer in roadmap phases | Low | **DEFERRED (post-MVP)** |

## License & access verification log

- **2026-08-08 — PlantVillage license (resolved):** CC **0** 1.0 (public domain). Evidence: (1) Mendeley
  page Licence section, live fetch; (2) [DataCite DOI metadata](https://api.datacite.org/dois/10.17632/tywbtsjrjv.1)
  `rightsList`: `openAccess` + "Public Domain Dedication", `rightsUri: creativecommons.org/publicdomain/zero/1.0`,
  record registered 2019-04-18, updated 2025-04-10. Earlier CC BY 3.0 wording seen only on an
  unofficial Penn State *mirror* repo — it labels that repo's own derived structure and does not
  bind the CC0 original. Attribution given regardless (see Citation below).
- **2026-08-08 — PlantVillage programmatic access (BLOCKED):** all three previously configured
  Mendeley download endpoints returned **HTTP 403** to automated clients (Windows + Linux runs).
  Decision (recorded in `ml/data/registry.py` as `AUTO_BLOCKED`): never retry those URLs
  automatically; never spoof browsers or bypass access controls; never use unofficial scraped
  copies. The documented path is **manual browser download + `ml.data.cli import`** (below).
  The GitHub original mirror (spMohanty/PlantVillage-Dataset) clones fine but ships **no explicit
  license file**, so it is not relied on for the product pipeline.
- **2026-08-08 — PlantDoc:** LICENSE.txt (CC BY 4.0) fetched verbatim; class folders (28) read from
  GitHub trees API; 17 folders map to V1 disease_ids; no healthy-Potato folder (recorded limitation).
- **2026-08-08 — PlantDoc Windows extraction failure (FOUND + FIXED):** the first real PlantDoc pull
  downloaded the 832 MB archive fine but crashed at extraction. Root causes: (1) the
  `ZipFile.extractall(filter="data")` branch was dead code — `filter` belongs to tarfile's PEP 706,
  no CPython zipfile has ever accepted it (signature verified on 3.13.14), so every call fell into
  the unfiltered fallback; (2) the fallback is not MAX_PATH-aware and hit the Win32 260-char limit on
  a 310-char auto-generated member name (this zip ships >200-char filenames). Fix: `extractall` is
  never called — `safe_extract` is a manual, deterministic, zip-slip-validated, MAX_PATH-aware
  (`ml/data/winpath.py`) member walk with an `.extracted-ok` completion marker (partial extractions
  self-heal; no false reuse). Cached archive reused — no re-download.
- **2026-08-08 — IP102:** academic-use-only terms re-confirmed on the official repo; DEFERRED/excluded.
- **2026-08-08 — Class-map alias gap (FOUND + FIXED by the coverage gate):** the first real
  import of the without-augmentation archive failed structure verification at 17/21 mappable
  folders. Root cause: four in-scope folders use a third naming variant the class map lacked
  aliases for (`Crop___Condition` convention incl. a hyphen in "Two-spotted" and doubled crop
  prefixes: `Corn___Cercospora_leaf_spot Gray_leaf_spot`, `Tomato___Spider_mites Two-spotted_spider_mite`,
  `Tomato___Tomato_Yellow_Leaf_Curl_Virus`, `Tomato___Tomato_mosaic_virus` — verbatim dirnames).
  No taxonomy, scope, or label change: the 21-class scope stayed identical; aliases were added
  from observed names only, and the gate was upgraded to enforce FULL documented coverage
  (floor = 21) plus a hard failure on unmapped V1-crop-prefixed folders (`require_full_class_coverage`
  for the training source; eval datasets like PlantDoc keep documented partial coverage as
  recorded warnings — see `ml/data/registry.py`, `ml/data/verify.py`).

## Acquisition & provenance procedure

### Automated-download status (2026-08-08)

| Dataset | Automated download | Documented route |
|---|---|---|
| plantvillage | **BLOCKED — HTTP 403 from all Mendeley endpoints for automated clients** | manual browser download → `import` |
| plantdoc | works (GitHub zip endpoint) | `download` or manual `import` |

When automation is refused, we never spoof clients, never bypass controls, never retry
forbidden endpoints, and never fall back to unverifiable copies.

### Windows (PowerShell) — recommended workflow

```powershell
cd C:\Users\<you>\path\to\cropmind-ai
pip install -r ml\requirements.txt

# 1) In your browser, open https://data.mendeley.com/datasets/tywbtsjrjv/1
#    and download "Plant_leaf_diseases_dataset_without_augmentation.zip" (~828 MB).
#    It lands in %USERPROFILE%\Downloads.

# 2) Import (verifies zip signature, extracts safely, checks class structure, records sha256 + provenance):
python -m ml.data.cli import --dataset plantvillage --archive "$env:USERPROFILE\Downloads\Plant_leaf_diseases_dataset_without_augmentation.zip" --accept-license

# 3) Deterministic pipeline, unchanged:
python -m ml.data.cli split  --dataset plantvillage
python -m ml.data.cli verify --dataset plantvillage
python -m ml.data.cli stats  --dataset plantvillage

# 4) Baseline training run (Phase 3 config; hours on CPU — leave it running, see docs/05-ml-pipeline.md):
python -m ml.training.train --config ml/configs/train_v1.yaml

# Every command above is ONE line — copy from THIS FILE in your editor, not from a
# chat window: chat renderers wrap long lines and linkify dotted module names,
# which corrupts pasted commands. Verify your clone is current first: `git pull origin main`
# then `python -m ml.data.cli --help` must list `import` among the subcommands.

# PlantDoc (automated route works):
python -m ml.data.cli pipeline --dataset plantdoc --accept-license
# …or manual: download https://github.com/pratikkayal/PlantDoc-Dataset/archive/refs/heads/master.zip, then `import --archive <zip>`

# macOS/Linux: identical commands with forward-slash paths.
# Already-extracted folder instead of a zip? → --directory "C:\path\to\class\folders" (verified in place, no copy).
```

### HTTP 403 — what the error means and what to do

If you see `cannot be downloaded programmatically … HTTP 403`: the authoritative source
rejected the automated client — this is expected, not a bug, and retrying changes nothing.
Follow the manual route above. Do not attempt workarounds that alter the client identity or
harvest session data — we intentionally do not bypass access controls.

Output layout (everything under `data/` is gitignored):

```
data/raw/plantvillage/
├── extracted/                 # auto-located class-folder root (nested without-aug handled)
└── PROVENANCE.json            # doi, citation, license, access dates, acquisition{method, sha256}, counts
data/splits/plantvillage/v1/
├── train.txt val.txt test.txt        # "relpath<TAB>disease_id"
└── split_manifest.json               # seed, ratios, per-class counts, skipped folders, content sha256
reports/datasets/plantvillage-stats.{md,csv}
```

`PROVENANCE.json` schema (written identically for auto-download and manual import):

```json
{
  "dataset": "plantvillage", "name": "…", "version": "mendeley-v1",
  "doi": "10.17632/tywbtsjrjv.1", "citation": "Arun Pandian, J., & Geetharamani, G. (2019)…",
  "page_url": "…", "license_id": "CC0-1.0", "license_url": "…", "license_observed": "…",
  "programmatic_status": "AUTO_BLOCKED",
  "downloaded_utc": "…", "access_date_utc": "…",
  "acquisition": { "method": "manual-archive | manual-directory | auto-download",
                   "source_basename": "…", "imported_utc": "…",
                   "archive_sha256": "<64-hex or null>", "sha256_note": null },
  "images_root": "…", "class_dirs": ["…"], "class_dir_count": 21, "image_count": 54305,
  "structure_warnings": ["…"]
}
```

**Augmentation-leakage policy:** training splits are built ONLY from the without-augmentation
source. Any our-own augmentation happens in Phase 3 inside the training transform, applied to
the training split only — never to files, so val/test can never contain an augmented copy of a
train image.

## V1 model scope derived from this register

- **Crops:** Tomato, Potato, Corn (maize), Apple — present in both datasets, enabling in-domain
  training (PlantVillage) *and* out-of-domain honesty testing (PlantDoc field imagery).
- **Conditions (21 classes):** configuration-driven per `ml/configs/taxonomy.yaml`; a class only
  flips `supported_by_model: true` after an evaluation report exists. Folder-name variants across
  mirrors/extraction formats are normalized by `ml/data/classmap.py`; aliases are added only
  from verbatim-observed dirnames — never guessed, never a relabeling.

| Crop | V1 classes (disease_ids) |
|---|---|
| Tomato (10) | bacterial_spot, early_blight, late_blight, leaf_mold, septoria_leaf_spot, spider_mites, target_spot, yellow_leaf_curl_virus, mosaic_virus, healthy |
| Potato (3) | early_blight, late_blight, healthy |
| Corn (4) | cercospora_gray_leaf_spot, common_rust, northern_leaf_blight, healthy |
| Apple (4) | scab, black_rot, cedar_rust, healthy |

- **Coverage gate (import-time):** the training source must map **all 21** documented classes
  (`expected_min_mapped_class_dirs = 21` + full-coverage check in `ml/data/verify.py`). An
  unmapped folder whose name matches a V1 crop is treated as a **class-map gap and blocks
  training** — partial coverage cannot silently pass while the API advertises the full taxonomy.
- **Out-of-scope data is retained, never deleted:** PlantVillage's 17 other-crop folders
  (blueberry, cherry, grape, orange, peach, bell-pepper, raspberry, soybean, squash, strawberry)
  stay in the raw store, are listed in provenance `structure_warnings`, and appear in split
  manifests as skipped. `Background_without_leaves` is excluded by policy. None of these are
  claimed as supported anywhere in the product, and extending scope is a documented-register
  decision, not a code default.

## Known limitations carried into the data card (Phase 3+)

1. **Domain gap:** PlantVillage is photographed on uniform backgrounds; PlantDoc field imagery
   differs sharply → out-of-domain metrics published separately.
2. **No severity ground truth** in approved datasets → severity remains a labelled visual proxy.
3. **PlantDoc whole-leaf boxes ≠ lesion boxes**; detector learns "suspicious leaf", not lesions.
4. **Geographic bias:** US-centric PlantVillage/FGVC imagery, Indian PlantDoc imagery; UK crops
   under-represented → feeds the data strategy (UK pilot collection).
5. **Class imbalance:** e.g. FGVC "complex" (187 images); PlantDoc distribution is long-tailed.
6. **No healthy-Potato folder in PlantDoc train** — out-of-domain Potato coverage is disease classes only.
7. **Mirror ambiguity:** several "PlantVillage" mirrors exist with different class-folder
   conventions; `ml/data/classmap.py` normalizes them and is unit-tested against both.

## Citations

- Arun Pandian, J., & Geetharamani, G. (2019). *Data for: Identification of Plant Leaf Diseases
  Using a 9-layer Deep Convolutional Neural Network.* Mendeley Data, v1. doi:10.17632/tywbtsjrjv.1
  (CC0 1.0). Related paper: Geetharamani G. & Arun Pandian J., *Computers & Electrical Engineering*,
  76, 323–338. doi:10.1016/j.compeleceng.2019.04.011
- Hughes, D. P., & Salathé, M. (2015). *An open access repository of images on plant health to
  enable the development of mobile disease diagnostics.* arXiv:1511.08060.
- Singh, D., Jain, N., Jain, P., Kayal, P., Kumawat, S., & Batra, N. (2020). *PlantDoc: A Dataset
  for Visual Plant Disease Detection.* CoDS-COMAD 2020. doi:10.1145/3371158.3371196 (CC BY 4.0).
- Wu, X., Zhan, C., Lai, Y.-K., Cheng, M.-M., & Yang, J. (2019). *IP102: A Large-Scale Benchmark
  Dataset for Insect Pest Recognition.* CVPR 2019. (cited for completeness; **not used** in V1)
- Thapa, R., Zhang, K., Snavely, N., Belongie, S., & Khan, A. (2020). *The Plant Pathology 2020
  challenge dataset to classify foliar disease of apples.* Applications in Plant Sciences, 8(9):e11390.
