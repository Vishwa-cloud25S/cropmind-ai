"""Registry of external datasets: the machine-readable mirror of docs/datasets.md.

The markdown register is the audited human record (license verification dates,
decisions, limitations). This module carries the identifiers the pipeline needs.
Nothing downloads or trains without a row here AND an APPROVED/decision in
docs/datasets.md (gate rule NFR-09).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class DatasetSpec:
    key: str
    name: str
    version: str
    page_url: str
    license_id: str
    license_url: str
    candidates: tuple[str, ...]  # download URLs tried in order
    archive_name: str
    license_observed: str  # what the page showed, and when we checked
    notes: str = ""


PLANTVILLAGE = DatasetSpec(
    key="plantvillage",
    name="PlantVillage (Mendeley Data mirror of the public plant-disease image collection)",
    version="mendeley-v1",
    page_url="https://data.mendeley.com/datasets/tywbtsjrjv/1",
    license_id="CC0-1.0",
    license_url="https://creativecommons.org/publicdomain/zero/1.0/",
    candidates=(
        # Preferred: the WITHOUT-augmentation archive (828 MB). We do our own
        # splitting/augmentation later, so augmented duplicates must never leak into splits.
        "https://data.mendeley.com/public-files/datasets/tywbtsjrjv/files/d5652a28-c1d8-4b76-97f3-72fb80f9b11c/file_downloaded",
        # Fallback: full "Download All" (1.67 GB) containing nested with/without archives;
        # the downloader opens a nested without-augmentation zip if present.
        "https://data.mendeley.com/public-api/zip/tywbtsjrjv/download/1",
        # Legacy CDN path used by older notebooks (often 403 today).
        "https://prod-dcd-datasets-cache-zipfiles.s3.eu-west-1.amazonaws.com/tywbtsjrjv-1.zip",
    ),
    archive_name="plantvillage-mendeley-v1.zip",
    license_observed="CC0 1.0 shown on dataset page 'Licence' section (verified 2026-08-08)",
    notes=(
        "Arun Pandian & Geetharamani (2019) mirror: 61,486 images across 39 classes "
        "(38 disease/healthy classes + Background_without_leaves, which we exclude). "
        "Attribution given to this release and to the underlying PlantVillage collection."
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
    notes=(
        "train/ + test/ trees, 28 class folders (verified via GitHub API 2026-08-08). "
        "Field imagery: used for honest out-of-domain evaluation of PlantVillage-trained models. "
        "The bounding-box mirror (PlantDoc-Object-Detection-Dataset) is for Phase 4 detection training."
    ),
)

REGISTRY: dict[str, DatasetSpec] = {s.key: s for s in (PLANTVILLAGE, PLANTDOC)}
