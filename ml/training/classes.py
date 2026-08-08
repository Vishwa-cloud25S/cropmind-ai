"""Canonical class list + crop mapping, driven by ml/configs/taxonomy.yaml.

The class ORDER is the sorted disease_id list and is embedded in every
checkpoint; training and inference must never diverge on this.
"""

from pathlib import Path

import yaml

DEFAULT_CONFIG_DIR = Path(__file__).resolve().parents[1] / "configs"


def load_taxonomy(config_dir: Path | None = None) -> dict:
    config_dir = Path(config_dir) if config_dir else DEFAULT_CONFIG_DIR
    return yaml.safe_load((config_dir / "taxonomy.yaml").read_text(encoding="utf-8"))


def class_list(config_dir: Path | None = None) -> list[str]:
    """Sorted disease_ids — the canonical class ordering for model heads."""
    taxonomy = load_taxonomy(config_dir)
    return sorted(
        condition["disease_id"]
        for crop in taxonomy.get("crops", [])
        for condition in crop.get("conditions", [])
    )


def crop_of(disease_id: str, config_dir: Path | None = None) -> str:
    """disease_id -> human crop name (e.g. tomato_early_blight -> 'Tomato')."""
    taxonomy = load_taxonomy(config_dir)
    for crop in taxonomy.get("crops", []):
        if any(c["disease_id"] == disease_id for c in crop.get("conditions", [])):
            return crop["name"]
    return "Unknown crop"


def condition_name(disease_id: str, config_dir: Path | None = None) -> str:
    taxonomy = load_taxonomy(config_dir)
    for crop in taxonomy.get("crops", []):
        for condition in crop.get("conditions", []):
            if condition["disease_id"] == disease_id:
                return condition["name"]
    return disease_id
