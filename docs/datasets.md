# Datasets — Research & Provenance Register

**Register v0.2 — last verified 2026-08-08.** Owner: founder.

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
| 1 | **PlantVillage** — Mendeley mirror (v1) | Arun Pandian & Geetharamani, [Mendeley DOI 10.17632/tywbtsjrjv.1](https://data.mendeley.com/datasets/tywbtsjrjv/1); related paper [10.1016/j.compeleceng.2019.04.011](https://doi.org/10.1016/j.compeleceng.2019.04.011); underlying collection: Hughes & Salathé (2015), arXiv:1511.08060 | **CC0 1.0** — public domain. **Resolved 2026-08-08:** the "Licence" section of the Mendeley page (fetched live) shows CC0 1.0, consistent with the [Meta-Album datasheet](https://meta-album.github.io/datasets/PLT_VIL.html). An unofficial Penn State *mirror* repo labelled it CC BY 3.0 — that label does not bind the CC0 original. Attribution is given regardless. | 61,486 images; 39 classes (38 leaf classes incl. our 4 crops + `Background_without_leaves`, which we exclude by policy) | image-level labels | V1 classification baseline (4-crop subset: Tomato, Potato, Corn, Apple) | Low | **APPROVED** |
| 2 | **PlantDoc** | Singh et al., CoDS-COMAD 2020 (IIT Gandhinagar), [classification repo](https://github.com/pratikkayal/PlantDoc-Dataset), [Dataset Ninja summary](https://datasetninja.com/plantdoc) | **CC BY 4.0** — LICENSE.txt fetched verbatim from the repo 2026-08-08; attribution text shipped in model/data cards | train/ + test/ trees; **28 class folders verified via GitHub API** (note: no healthy-Potato folder in train/) | image labels; bounding boxes in the separate [object-detection mirror](https://github.com/pratikkayal/PlantDoc-Object-Detection-Dataset) | out-of-domain evaluation of the V1 classifier; detection training in Phase 4 via the detection mirror | Low | **APPROVED** |
| 3 | **Plant Pathology 2020 (FGVC7)** | Khan Lab, Cornell; Thapa et al., *Appl. Plant Sci.* 8(9):e11390 (2020); [Kaggle competition](https://www.kaggle.com/c/plant-pathology-2020-fgvc7); [project page](https://blogs.cornell.edu/applevarietydatabase/machine-learning-for-disease-detection/) | Dataset "freely available to download on Kaggle" (paper); exact license per Kaggle competition terms — **verify at download** | ~3,651 expert-annotated RGB apple-leaf images (scab 1,200 / rust 1,399 / complex 187 / healthy 865) + competition test set | image-level labels (multi-label capable) | optional Apple baseline / DSLR+smartphone robustness check | Medium (Kaggle terms govern) | **CONDITIONAL** — only if terms check passes |
| 4 | **IP102 (insect pests)** | Wu et al., CVPR 2019; [official repo](https://github.com/xpwu95/IP102) | **"Free for academic usage. For other purposes, please contact the author"** (official repo, verified). A [Roboflow Universe mirror](https://universe.roboflow.com/roboflow-public/ip102-insect-pest-recognition) labels its copy CC BY 4.0 — a re-host cannot grant broader rights than upstream, so that label is **not** relied on. | 75,222 images; 102 pest classes; ~19k with boxes | image labels + boxes (subset) | future pest-detection module (post-V1) | **High** (non-commercial upstream) | **DEFERRED — excluded** until written permission or a properly licensed alternative |
| 5 | **OpenAerialMap** (per-asset) | [openaerialmap.org](https://openaerialmap.org) | Per-uploader licenses, commonly CC BY / CC BY-NC — **checked per asset at download** | n/a | orthomosaics | demo orthomosaic & spray-simulation basemap; **not** training data | Low–Medium (per-asset) | **APPROVED, per-asset attribution recorded** |
| 6 | **USDA NAIP** (optional, US) | USDA FSA | Public domain (US Gov work) | n/a | aerial imagery | simulated field imagery in demo mode | Low | **APPROVED (optional)** |
| 7 | **Copernicus Sentinel-2** (deferred) | ESA/Copernicus | Free, full and open access (EU Reg. 1159/2013) | n/a | multispectral | field-context layer in roadmap phases | Low | **DEFERRED (post-MVP)** |

## License verification log

- **2026-08-08 — PlantVillage:** Mendeley page fetched live; Licence section shows **CC0 1.0**.
  Resolved CC0-vs-CC-BY discrepancy from v0.1: the CC BY 3.0 label appears only on an unofficial
  mirror repo and does not restrict the CC0 original. Download endpoints recorded in
  `ml/data/registry.py` (without-augmentation archive preferred; see below).
- **2026-08-08 — PlantDoc:** LICENSE.txt (CC BY 4.0) fetched verbatim from repo. Class folders
  (28) read from the GitHub trees API; absence of a healthy-Potato folder recorded as a limitation.
- **2026-08-08 — IP102:** academic-use-only terms re-confirmed on the official repo; decision
  stands as DEFERRED/excluded.

## Download & provenance procedure (implemented in Phase 2)

```bash
pip install -r ml/requirements.txt

# Full pipeline: download → split → verify → stats
python -m ml.data.cli pipeline --dataset plantvillage --accept-license
python -m ml.data.cli pipeline --dataset plantdoc    --accept-license

# Or step by step:
python -m ml.data.cli download --dataset plantvillage          # refuses without --accept-license
python -m ml.data.cli split    --dataset plantvillage           # deterministic 70/15/15, seed 42
python -m ml.data.cli verify   --dataset plantvillage           # provenance + leakage + integrity
python -m ml.data.cli stats    --dataset plantvillage           # -> reports/datasets/
```

Output layout (everything under `data/` is gitignored):

```
data/raw/plantvillage/
├── plantvillage-mendeley-v1.zip     # archive (sha256 recorded)
├── extracted/                        # auto-located class-folder root (nested without-aug handled)
└── PROVENANCE.json                   # urls, license, sha256, image/class counts, downloads_utc
data/splits/plantvillage/v1/
├── train.txt val.txt test.txt        # "relpath<TAB>disease_id"
└── split_manifest.json               # seed, ratios, per-class counts, skipped folders, content sha256
reports/datasets/plantvillage-stats.{md,csv}
```

**Augmentation-leakage policy:** training splits are built ONLY from the without-augmentation
source. Any our-own augmentation happens in Phase 3 inside the training transform, applied to
the training split only — never to files, so val/test can never contain an augmented copy of a
train image.

## V1 model scope derived from this register

- **Crops:** Tomato, Potato, Corn (maize), Apple — present in both datasets, enabling in-domain
  training (PlantVillage) *and* out-of-domain honesty testing (PlantDoc field imagery).
- **Conditions:** per `ml/configs/taxonomy.yaml` (21 classes). Configuration-driven; a class only
  flips `supported_by_model: true` after an evaluation report exists.

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
  (CC0 1.0). Related paper: Computers and Electronics in Agriculture. doi:10.1016/j.compeleceng.2019.04.011
- Hughes, D. P., & Salathé, M. (2015). *An open access repository of images on plant health to
  enable the development of mobile disease diagnostics.* arXiv:1511.08060.
- Singh, D., Jain, N., Jain, P., Kayal, P., Kumawat, S., & Batra, N. (2020). *PlantDoc: A Dataset
  for Visual Plant Disease Detection.* CoDS-COMAD 2020. doi:10.1145/3371158.3371196 (CC BY 4.0).
- Wu, X., Zhan, C., Lai, Y.-K., Cheng, M.-M., & Yang, J. (2019). *IP102: A Large-Scale Benchmark
  Dataset for Insect Pest Recognition.* CVPR 2019. (cited for completeness; **not used** in V1)
- Thapa, R., Zhang, K., Snavely, N., Belongie, S., & Khan, A. (2020). *The Plant Pathology 2020
  challenge dataset to classify foliar disease of apples.* Applications in Plant Sciences, 8(9):e11390.
