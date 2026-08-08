"""Class-directory → taxonomy disease_id mapping.

Mirror releases use different folder conventions (e.g. `Apple___Apple_scab` vs
`Apple_scab`), so lookup keys are normalized directory names. Mapping targets are
disease_ids from ml/configs/taxonomy.yaml; `excluded` entries (e.g. background)
are dropped deliberately and every skip is recorded in split manifests — nothing
is silently discarded or remapped.
"""

import re
from pathlib import Path

import yaml

EXCLUDE = object()  # sentinel: dataset class exists but is intentionally not used


def normalize(dirname: str) -> str:
    """Normalize raw class-directory names so naming conventions can share keys."""
    n = dirname.strip().lower()
    for ch in "()%-+,.":
        n = n.replace(ch, "")
    n = re.sub(r"[\s/\\]+", "_", n)
    n = re.sub(r"_+", "_", n)
    return n.strip("_")


PLANTVILLAGE_MAP: dict[str, object] = {
    # Mendeley naming (`Apple_scab`) and spMohanty-mirror naming
    # (`Apple___Apple_scab`) normalize onto the same keys.
    "apple_scab": "apple_scab",
    "apple_apple_scab": "apple_scab",
    "apple_black_rot": "apple_black_rot",
    "apple_cedar_apple_rust": "apple_cedar_rust",
    "apple_healthy": "apple_healthy",
    "background_without_leaves": EXCLUDE,
    "corn_gray_leaf_spot": "corn_cercospora_gray_leaf_spot",
    "corn_maize_cercospora_leaf_spot_gray_leaf_spot": "corn_cercospora_gray_leaf_spot",
    "corn_common_rust": "corn_common_rust",
    "corn_northern_leaf_blight": "corn_northern_leaf_blight",
    "corn_healthy": "corn_healthy",
    "potato_early_blight": "potato_early_blight",
    "potato_late_blight": "potato_late_blight",
    "potato_healthy": "potato_healthy",
    "tomato_bacterial_spot": "tomato_bacterial_spot",
    "tomato_early_blight": "tomato_early_blight",
    "tomato_late_blight": "tomato_late_blight",
    "tomato_leaf_mold": "tomato_leaf_mold",
    "tomato_septoria_leaf_spot": "tomato_septoria_leaf_spot",
    "tomato_spider_mites_two_spotted_spider_mite": "tomato_spider_mites",
    "tomato_target_spot": "tomato_target_spot",
    "tomato_mosaic_virus": "tomato_mosaic_virus",
    "tomato_yellow_leaf_curl_virus": "tomato_yellow_leaf_curl_virus",
    "tomato_healthy": "tomato_healthy",
    # WITHOUT-augmentation archive naming — a third `Crop___Condition` variant, verbatim
    # dirnames from the real extraction (2026-08-08): "Corn___Cercospora_leaf_spot Gray_leaf_spot",
    # "Tomato___Spider_mites Two-spotted_spider_mite" (hyphen), and doubled crop prefixes
    # ("Tomato___Tomato_mosaic_virus", "Tomato___Tomato_Yellow_Leaf_Curl_Virus"). Missing aliases
    # here silently dropped 4 of the 21 documented classes — caught by the coverage gate.
    "corn_cercospora_leaf_spot_gray_leaf_spot": "corn_cercospora_gray_leaf_spot",
    "tomato_spider_mites_twospotted_spider_mite": "tomato_spider_mites",
    "tomato_tomato_yellow_leaf_curl_virus": "tomato_yellow_leaf_curl_virus",
    "tomato_tomato_mosaic_virus": "tomato_mosaic_virus",
}

# Verbatim PlantDoc train/ class folders (GitHub API, verified 2026-08-08).
# 28 folders; only the 17 that belong to V1 crops map — the rest (other crops and
# crop folders PlantDoc lacks labels for, e.g. no healthy-Potato folder in train/)
# are intentionally unmapped and recorded as skipped, per docs/datasets.md scope.
PLANTDOC_MAP: dict[str, object] = {
    "apple_scab_leaf": "apple_scab",
    "apple_rust_leaf": "apple_cedar_rust",
    "apple_leaf": "apple_healthy",
    "corn_gray_leaf_spot": "corn_cercospora_gray_leaf_spot",
    "corn_leaf_blight": "corn_northern_leaf_blight",
    "corn_rust_leaf": "corn_common_rust",
    "potato_leaf_early_blight": "potato_early_blight",
    "potato_leaf_late_blight": "potato_late_blight",
    "tomato_early_blight_leaf": "tomato_early_blight",
    "tomato_septoria_leaf_spot": "tomato_septoria_leaf_spot",
    "tomato_leaf_bacterial_spot": "tomato_bacterial_spot",
    "tomato_leaf_late_blight": "tomato_late_blight",
    "tomato_leaf_mosaic_virus": "tomato_mosaic_virus",
    "tomato_leaf_yellow_virus": "tomato_yellow_leaf_curl_virus",
    "tomato_mold_leaf": "tomato_leaf_mold",
    "tomato_two_spotted_spider_mites_leaf": "tomato_spider_mites",
    "tomato_leaf": "tomato_healthy",
    # NOTE: PlantDoc train has no healthy-Potato folder (verified 2026-08-08).
}

MAPS: dict[str, dict[str, object]] = {"plantvillage": PLANTVILLAGE_MAP, "plantdoc": PLANTDOC_MAP}

UNMAPPED = None  # class dir exists but not in V1 scope


def map_class_dir(dataset: str, dirname: str) -> str | None | object:
    """Return disease_id, EXCLUDE sentinel, or None (unmapped/out of scope)."""
    return MAPS.get(dataset, {}).get(normalize(dirname), UNMAPPED)


def taxonomy_disease_ids(config_dir: Path) -> set[str]:
    taxonomy = yaml.safe_load((Path(config_dir) / "taxonomy.yaml").read_text(encoding="utf-8"))
    return {
        condition["disease_id"]
        for crop in taxonomy.get("crops", [])
        for condition in crop.get("conditions", [])
    }


def validate_against_taxonomy(config_dir: Path) -> list[str]:
    """Every mapping target must exist in the taxonomy. Returns problems (empty = OK)."""
    ids = taxonomy_disease_ids(config_dir)
    problems = []
    for dataset, mapping in MAPS.items():
        for key, target in mapping.items():
            if target is EXCLUDE:
                continue
            if target not in ids:
                problems.append(f"{dataset}: {key!r} -> {target!r} missing from taxonomy")
    return problems
