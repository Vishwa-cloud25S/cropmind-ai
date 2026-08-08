"""Registry of external datasets: the machine-readable mirror of docs/datasets.md.

The markdown register is the audited human record (license verification dates,
decisions, limitations). This module carries the identifiers the pipeline needs.
Nothing downloads or trains without a row here AND an APPROVED decision in
docs/datasets.md (gate rule NFR-09).

programmatic_status records whether automated download currently works:
- AUTO_OK       : a documented URL streams the archive today
- AUTO_BLOCKED  : the authoritative source refuses automated clients (e.g. HTTP 403)
                  → the manual import route is required; URLs are kept for the
                  record and are never retried automatically
- MANUAL_ONLY   : no programmatic route exists at all
"""

from dataclasses import dataclass


class ProgrammaticStatus:
    AUTO_OK = "AUTO_OK"
    AUTO_BLOCKED = "AUTO_BLOCKED"
    MANUAL_ONLY = "MANUAL_ONLY"


@dataclass(frozen=True)
class DatasetSpec:
    key: str
    name: str
    version: str
    page_url: str
    license_id: str
    license_url: str
    candidates: tuple[str, ...]  # download URLs tried in order (AUTO_OK only)
    archive_name: str
    license_observed: str  # what the authoritative sources showed, and when we checked
    doi: str | None = None
    citation: str = ""
    manual_steps: tuple[str, ...] = ()
    programmatic_status: str = ProgrammaticStatus.AUTO_OK
    status_note: str = ""
    expected_min_mapped_class_dirs: int = 2
    notes: str = ""


PLANTVILLAGE = DatasetSpec(
    key="plantvillage",
    name="PlantVillage (Mendeley Data mirror of the public plant-disease image collection)",
    version="mendeley-v1",
    page_url="https://data.mendeley.com/datasets/tywbtsjrjv/1",
    license_id="CC0-1.0",
    license_url="https://creativecommons.org/publicdomain/zero/1.0/",
    candidates=(
        # HTTP 403 for automated clients on ALL of these (observed 2026-08-08):
        # retained for the audit record only — never retried automatically.
        "https://data.mendeley.com/public-files/datasets/tywbtsjrjv/files/d5652a28-c1d8-4b76-97f3-72fb80f9b11c/file_downloaded",
        "https://data.mendeley.com/public-api/zip/tywbtsjrjv/download/1",
        "https://prod-dcd-datasets-cache-zipfiles.s3.eu-west-1.amazonaws.com/tywbtsjrjv-1.zip",
    ),
    archive_name="plantvillage-mendeley-v1.zip",
    license_observed=(
        "CC0 1.0 confirmed by two independent authoritative sources (2026-08-08): "
        "Mendeley page 'Licence' section, and DataCite DOI metadata rightsList "
        "('Public Domain Dedication', cc.org/publicdomain/zero/1.0; record updated 2025-04-10)"
    ),
    doi="10.17632/tywbtsjrjv.1",
    citation=(
        "Arun Pandian, J., & Geetharamani, G. (2019). Data for: Identification of Plant Leaf "
        "Diseases Using a 9-layer Deep Convolutional Neural Network. Mendeley Data, v1. "
        "doi:10.17632/tywbtsjrjv.1 (CC0 1.0). Related paper: Computers & Electrical Engineering, "
        "76, 323–338. doi:10.1016/j.compeleceng.2019.04.011. Underlying collection: "
        "Hughes & Salathé (2015), arXiv:1511.08060."
    ),
    manual_steps=(
        "Open https://data.mendeley.com/datasets/tywbtsjrjv/1 in a normal browser.",
        "Download 'Plant_leaf_diseases_dataset_without_augmentation.zip' (~828 MB). Use the WITHOUT-augmentation file only — augmented duplicates would leak into splits.",
        "Run: python -m ml.data.cli import --dataset plantvillage --archive <downloaded-zip> --accept-license",
        "Or, if you already have the extracted class-folder directory: python -m ml.data.cli import --dataset plantvillage --directory <folder> --accept-license",
    ),
    programmatic_status=ProgrammaticStatus.AUTO_BLOCKED,
    status_note=(
        "HTTP 403 from all Mendeley download endpoints for non-browser clients "
        "(observed 2026-08-08 on Windows and Linux). We do not bypass access controls "
        "(no UA spoofing / session tricks); the manual import route is the documented path."
    ),
    expected_min_mapped_class_dirs=20,
    notes=(
        "61,486 images across 39 classes per dataset description (38 disease/healthy classes "
        "+ Background_without_leaves, excluded by policy). Augmentation variants exist in the "
        "release; only the without-augmentation archive may feed splits."
    ),
)

PLANTDOC = DatasetSpec(
    key="plantdoc",
    name="PlantDoc (classification dataset; IIT Gandhinagar)",
    version="github-master-2026-08-08",
    page_url="https://github.com/pratikkayal/PlantDoc-Dataset",
    license_id="CC-BY-4.0",
    license_url="https://creativecommons.org/licenses/by/4.0/",
    candidates=("https://github.com/pratikkayal/PlantDoc-Dataset/archive/refs/heads/master.zip",),
    archive_name="plantdoc-master.zip",
    license_observed="CC BY 4.0 LICENSE.txt fetched verbatim from repo (verified 2026-08-08)",
    doi=None,
    citation=(
        "Singh, D., Jain, N., Jain, P., Kayal, P., Kumawat, S., & Batra, N. (2020). "
        "PlantDoc: A Dataset for Visual Plant Disease Detection. CoDS-COMAD 2020. "
        "doi:10.1145/3371158.3371196. Dataset: github.com/pratikkayal/PlantDoc-Dataset (CC BY 4.0)."
    ),
    manual_steps=(
        "Either let this CLI download it (currently works), or download https://github.com/pratikkayal/PlantDoc-Dataset/archive/refs/heads/master.zip in a browser.",
        "Run: python -m ml.data.cli import --dataset plantdoc --archive <downloaded-zip> --accept-license",
    ),
    programmatic_status=ProgrammaticStatus.AUTO_OK,
    status_note="GitHub archive endpoint verified live 2026-08-08.",
    expected_min_mapped_class_dirs=15,
    notes=(
        "train/ + test/ trees, 28 class folders (verified via GitHub API 2026-08-08); "
        "17 folders map to V1 disease_ids. No healthy-Potato folder in train/ (recorded limitation). "
        "Bounding-box mirror (PlantDoc-Object-Detection-Dataset) is for Phase 4 detection training."
    ),
)

REGISTRY: dict[str, DatasetSpec] = {s.key: s for s in (PLANTVILLAGE, PLANTDOC)}
