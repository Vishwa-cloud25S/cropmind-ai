"""Loads shared ML configuration (crop taxonomy + model thresholds) from ml/configs."""

from functools import lru_cache
from pathlib import Path

import yaml


class ConfigNotFoundError(RuntimeError):
    pass


def _load_yaml(path: Path) -> dict:
    if not path.exists():
        raise ConfigNotFoundError(f"missing config file: {path}")
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


@lru_cache(maxsize=8)
def load_taxonomy(config_dir: str) -> dict:
    return _load_yaml(Path(config_dir) / "taxonomy.yaml")


@lru_cache(maxsize=8)
def load_model_config(config_dir: str) -> dict:
    return _load_yaml(Path(config_dir) / "model.yaml")
