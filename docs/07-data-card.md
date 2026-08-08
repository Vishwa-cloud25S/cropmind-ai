# 07 — Data Card (v1, 2026-08-08)

Data used by CropMind AI model version 0.1.0. The audited register with decisions and
verification log lives in `docs/datasets.md`; this card is the model-facing data sheet.

## 1. Composition summary

| Role | Dataset | License (verified) | Volume used | Classes |
|---|---|---|---|---|
| In-domain training + held-out test | **PlantVillage — Mendeley mirror v1** (without-augmentation archive only) | **CC0 1.0** (double-verified 2026-08-08; see §2) | 27,335 images (train 19,126 / val 4,090 / test 4,119) | 21 (4 crops: Tomato 10, Corn 4, Apple 4, Potato 3) |
| Out-of-domain honesty evaluation | **PlantDoc** (field imagery) | **CC BY 4.0** (LICENSE fetched verbatim) | mapped subset of the train/ tree, folder-level provenance recorded | 17 of the 28 folders map to our disease_ids |
| Excluded | IP102 pests; FGVC7 (conditional); augmented PlantVillage variants | — | 0 | license/access rules in register |

## 2. PlantVillage subset — provenance chain

- **Source:** Arun Pandian, J. & Geetharamani, G. (2019), Mendeley Data v1, DOI
  `10.17632/tywbtsjrjv.1`; underlying collection Hughes & Salathé (2015), arXiv:1511.08060.
- **License:** CC0 1.0 confirmed by two independent authoritative sources on 2026-08-08 — the
  Mendeley page Licence section and the DataCite DOI metadata (`rightsList`: "Public Domain
  Dedication", record updated 2025-04-10). Attribution given regardless.
- **Acquisition:** automated download refused by the source (HTTP 403, all endpoints,
  2026-08-08). Manual import route per register; we do not bypass access controls and do not use
  scraped mirrors. Archive sha256 recorded in the operator's `PROVENANCE.json`
  (`data/raw/plantvillage/PROVENANCE.json`).
- **Augmentation-leakage policy:** ONLY the `without_augmentation` tree feeds splits. Our own
  augmentation is runtime-only inside the training transform, applied to the train split —
  never to files, so val/test can never contain an augmented duplicate of a train image.
- **Scope filtering (recorded, never deleted):** 17 other-crop folders (blueberry, cherry, grape,
  orange, peach, bell-pepper, raspberry, soybean, squash, strawberry) remain in the raw store and
  are listed in provenance warnings + split manifests as skipped; `Background_without_leaves` is
  excluded by policy. None are claimed as supported.
- **Class-folder normalization:** mirrors use different conventions (`Apple___Apple_scab` style,
  `Apple_scab` style, WITHOUT-augmentation `Crop___Condition` style incl. hyphen in "Two-spotted"
  and doubled crop prefixes). `ml/data/classmap.py` normalizes; aliases come only from
  verbatim-observed dirnames (verification log 2026-08-08: one alias gap found by the coverage
  gate and fixed — 17→21 mappable classes, no taxonomy change).
- **Split:** deterministic 70/15/15, seed 42; split files + `split_manifest.json` carry per-class
  counts and content sha256 `276dc3e9f21bf497b8996b089946281616857128e24436870331527af42130e7`
  (support: max 805 tomato yellow leaf curl virus, min 24 potato healthy in the test split —
  ~33:1 imbalance; full per-class counts: operator-local `reports/datasets/plantvillage-stats.md`).

## 3. PlantDoc — out-of-domain set

- **Source:** Singh et al., CoDS-COMAD 2020 (IIT Gandhinagar),
  `github.com/pratikkayal/PlantDoc-Dataset`; **CC BY 4.0** (LICENSE.txt fetched verbatim).
  Attribution: "Singh, D., Jain, N., Jain, P., Kayal, P., Kumawat, S., & Batra, N. (2020).
  PlantDoc: A Dataset for Visual Plant Disease Detection. CoDS-COMAD 2020. (CC BY 4.0)".
- **Use:** OOD evaluation of the V1 classifier only — **never trained on, never tuned on**.
- **Composition notes:** train/ has 28 class folders (GitHub API verified 2026-08-08); 17 map to
  our disease_ids; remainder recorded as skipped. **No healthy-Potato folder** in train/
  (recorded limitation). Bounding boxes exist only in a separate object-detection mirror.

## 4. Known limitations of the data itself

1. **Domain gap:** PlantVillage leaves are photographed on uniform backgrounds; field imagery
   (lighting, clutter, occlusion, cultivar, geography) differs sharply → measured OOD gap
   published in `reports/model_evaluation/`.
2. **Geographic/cultivar bias:** US-centric PlantVillage; Indian PlantDoc; **UK crops
   under-represented** → feeds the data strategy (UK pilot collection in the business roadmap).
3. **No severity ground truth:** severity outputs elsewhere are a labelled visual proxy.
4. **No pest-insect training data:** IP102 upstream license is academic-use-only and is excluded
   until permission or a properly licensed alternative exists (register decision).
5. **Class availability ≠ agronomic importance**; thin classes (e.g. potato healthy) have wide
   per-class error bars.
6. Personal data: none; datasets are public plant-leaf imagery.

## 5. Rights, retention & deletion

We do not redistribute datasets; each retains its own license. Raw/processed data lives on
operator storage only (`data/`, gitignored) with PROVENANCE.json per dataset; deletion of a
dataset amounts to removing its directory + manifests (documented in the register).
Changelog: v1 2026-08-08 — issued with model card v1 for baseline 0.1.0.
