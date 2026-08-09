"""Worker-only bridge to the ML module (torch imported lazily — the API never does).

Checkpoint policy (honest, never silent):
- MODEL_CHECKPOINT set  → the real run (e.g. runs/20260808-180238-0.1.0/checkpoint.pt).
- unset                 → DEMO sample model (synthetic patterns, `0.0.0-sample`),
  generated once via `python -m ml.training.sample_model`. Every prediction made with
  it is flagged `demo=True` at the API/DB level — demo output is plumbing evidence,
  never a field-performance claim.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger("cropmind.mlbridge")

_cache: dict[str, ModelHandle] = {}

SAMPLE_CKPT = Path("ml/models/pretrained/sample-mobilenetv3.pt")


@dataclass
class ModelHandle:
    predictor: object  # ml.inference.predictor.Predictor (typed loosely: torch is worker-only)
    checkpoint_path: Path
    demo: bool


def _ensure_sample_checkpoint(repo_root: Path) -> Path:
    target = repo_root / SAMPLE_CKPT
    if not target.exists():
        logger.warning("DEMO mode: generating the synthetic sample checkpoint once (%s)", target)
        subprocess.run(
            [sys.executable, "-m", "ml.training.sample_model"],
            cwd=repo_root,
            check=True,
            timeout=1200,
            env={**os.environ, "CROPMIND_QUIET": "1"},
        )
    if not target.exists():  # pragma: no cover - generator contract
        raise RuntimeError(f"sample checkpoint generation failed: {target}")
    return target


def get_predictor(checkpoint: str | None, repo_root: Path, device: str = "cpu") -> ModelHandle:
    """Cached per checkpoint path. Imports torch/torchvision only on first real use.

    Empty-string checkpoint values (compose passthrough default) mean "unset" => DEMO.
    """
    checkpoint = checkpoint or None
    key = checkpoint or "DEMO"
    if key in _cache:
        return _cache[key]
    demo = checkpoint is None
    ckpt_path = _ensure_sample_checkpoint(repo_root) if demo else Path(checkpoint)
    if not ckpt_path.exists():
        raise FileNotFoundError(f"checkpoint not found: {ckpt_path}")
    from ml.inference.predictor import Predictor

    predictor = Predictor(ckpt_path, device=device)
    if demo:
        logger.warning("DEMO model active (%s) — predictions are plumbing demos, never crop claims", ckpt_path)
    handle = ModelHandle(predictor=predictor, checkpoint_path=ckpt_path, demo=demo)
    _cache[key] = handle
    return handle


def reset_cache() -> None:
    _cache.clear()
