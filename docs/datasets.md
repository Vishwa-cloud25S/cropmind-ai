# Datasets — Research & Provenance Register

**Register v0.1 — verified 2026-08-08.** Owner: founder.

**Gate rule (NFR-09):** no dataset enters the training pipeline unless it has a completed row
below with **License status = APPROVED**, and its provenance (`source_url`, version/date, image
count, classes, known limitations, license + license URL) is also recorded in the
`dataset_sources` database table once the backend exists. Datasets are never committed to git
(see `.gitignore`) and never silently combined — every image keeps a `source` namespace.

---

## Candidate register

| # | Dataset | Source / paper | License (verified 2026-08-08) | Size & classes | Annotation | Role in CropMind | License risk | Decision |
|---|---------|----------------|-------------------------------|----------------|------------|------------------|--------------|----------|
| 1 | **PlantVillage** | Hughes & Salathé (2015), [Mendeley Data DOI 10.17632/tywbtsjrjv.1](https://data.mendeley.com/datasets/tywbtsjrjv/1); [Penn State mirror](https://github.com/ai-agriculture-circuits-and-systems/plant_village) | Discrepancy noted: [Meta-Album datasheet](https://meta-album.github.io/datasets/PLT_VIL.html) records the original Mendeley release as **CC0 1.0**; the Penn State mirror repo labels it **CC BY 3.0**. Both permit commercial use; CC BY 3.0 requires attribution. **Re-verify on the Mendeley page at download time (Phase 2). Attribution will be given regardless.** | 54,305 images; 38 classes over 14 crop species; single-leaf, uniform background | image-level labels | V1 classification baseline (config-driven 4-crop subset: Tomato, Potato, Corn/Maize, Apple) | Low–Medium (documentation discrepancy; older distributions of the same data carried research-only language — keeping the conservative-attribution practice above) | **APPROVED (conditional)** for R&D + product use pending the Mendeley re-check |
| 2 | **PlantDoc** | Singh et al., CoDS-COMAD 2020 (IIT Gandhinagar), [repo](https://github.com/pratikkayal/PlantDoc-Dataset), [detection mirror](https://github.com/pratikkayal/PlantDoc-Object-Detection-Dataset), [Dataset Ninja summary](https://datasetninja.com/plantdoc) | **CC BY 4.0** (LICENSE in repos) — commercial use allowed with attribution | ≈2,598 images; 13 species; 27 classes; detection mirror: train 2,251 / test 231 | image labels + bounding boxes (whole-leaf boxes, ≥ ~1/8 image area) | detection/localization training (Phase 4+) **and** out-of-domain evaluation of the V1 classifier (field imagery vs lab imagery) | Low | **APPROVED** |
| 3 | **Plant Pathology 2020 (FGVC7)** | Khan Lab, Cornell; Thapa et al., *Appl. Plant Sci.* 8(9):e11390 (2020); [Kaggle competition](https://www.kaggle.com/c/plant-pathology-2020-fgvc7); [project page](https://blogs.cornell.edu/applevarietydatabase/machine-learning-for-disease-detection/) | Dataset "freely available to download on Kaggle" (paper); exact license per Kaggle competition terms — **verify at download** | ~3,651 expert-annotated RGB apple-leaf images (scab 1,200 / rust 1,399 / complex 187 / healthy 865) + competition test set | image-level labels (multi-label capable) | optional Apple baseline / second crop family; stress-test on DSLR + smartphone conditions | Medium (Kaggle terms govern) | **CONDITIONAL** — only if terms check passes |
| 4 | **IP102 (insect pests)** | Wu et al., CVPR 2019; [official repo](https://github.com/xpwu95/IP102) | **"Free for academic usage. For other purposes, please contact the author"** (official repo, verified). A [Roboflow Universe mirror](https://universe.roboflow.com/roboflow-public/ip102-insect-pest-recognition) labels its copy CC BY 4.0 — a re-host cannot grant broader rights than upstream, so that label is **not** relied on. | 75,222 images; 102 pest classes; ~19k with boxes | image labels + boxes (subset) | future pest-detection module (post-V1) | **High** (non-commercial upstream) | **DEFERRED — excluded** until written permission or a properly licensed alternative |
| 5 | **OpenAerialMap** (per-asset) | [openaerialmap.org](https://openaerialmap.org) | Per-Uploader licenses, commonly CC BY / CC BY-NC — **checked per asset at download** | n/a | orthomosaics | demo orthomosaic & spray-simulation basemap; **not** training data | Low–Medium (per-asset) | **APPROVED, per-asset attribution recorded** |
| 6 | **USDA NAIP** (optional, US) | USDA FSA | Public domain (US Gov work) | n/a | aerial imagery | simulated field imagery in demo mode | Low | **APPROVED (optional)** |
| 7 | **Copernicus Sentinel-2** (deferred) | ESA/Copernicus | Free, full and open access (EU Reg. 1159/2013) | n/a | multispectral | field-context layer in roadmap phases | Low | **DEFERRED (post-MVP)** |

## V1 model scope derived from this register

- **Crops:** Tomato, Potato, Corn (maize), Apple — classes present in both PlantVillage and PlantDoc,
  enabling in-domain training *and* out-of-domain honesty testing.
- **Conditions:** the PlantVillage class set for those crops (e.g., Tomato–Early blight, Late blight,
  Leaf Mold, Septoria leaf spot, two-spotted spider mite, healthy; Potato–Early/Late blight, healthy;
  Corn–Northern Leaf Blight, Common rust, Gray leaf spot, healthy; Apple–scab, Black rot, rust, healthy).
  The configuration-driven taxonomy (crop/disease ids, descriptions, dataset source, supported_by_model,
  confidence thresholds) ships in `ml/configs/` (Phase 2–3) and is exposed at `/supported-crops`.

## Known limitations to carry into the data card (Phase 3+)

1. **Domain gap:** PlantVillage is photographed on uniform backgrounds; field imagery (PlantDoc-style)
   differs sharply. M1 therefore reports out-of-domain accuracy separately and honestly.
2. **No severity ground truth** in any approved dataset → severity is an explicitly-labelled visual
   proxy until annotated or field-collected data exists.
3. **Whole-leaf boxes** in PlantDoc ≠ lesion-level boxes; detector learns "suspicious leaf", not
   "lesion boundary". This is a documented limitation, not hidden.
4. **Geographic/bias coverage:** US-centric imagery (PlantVillage/FGVC) and Indian field imagery
   (PlantDoc); UK crops under-represented — feeds the data-strategy rationale (UK pilot collection).
5. **Class imbalance** (FGVC "complex" class = 187 images) handled via honest per-class metrics.

## Storage & provenance procedure (Phase 2)

```
data/raw/plantvillage/…       # downloaded, never committed
data/raw/<source>/PROVENANCE.json   # {source_url, download_date, license, license_url, sha256_manifest}
data/splits/<dataset>/<v>/    # deterministic seeds recorded
dataset_sources (DB table)    # mirrors register rows once backend exists
```

## Citations

- Hughes, D. P., & Salathé, M. (2015). *An open access repository of images on plant health to
  enable the development of mobile disease diagnostics.* arXiv:1511.08060.
- Singh, D., Jain, N., Jain, P., Kayal, P., Kumawat, S., & Batra, N. (2020). *PlantDoc: A Dataset
  for Visual Plant Disease Detection.* CoDS-COMAD 2020. doi:10.1145/3371158.3371196.
- Wu, X., Zhan, C., Lai, Y.-K., Cheng, M.-M., & Yang, J. (2019). *IP102: A Large-Scale Benchmark
  Dataset for Insect Pest Recognition.* CVPR 2019. (cited for completeness; dataset not used in V1)
- Thapa, R., Zhang, K., Snavely, N., Belongie, S., & Khan, A. (2020). *The Plant Pathology 2020
  challenge dataset to classify foliar disease of apples.* Applications in Plant Sciences, 8(9):e11390.
