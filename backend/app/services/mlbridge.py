"""Worker-only bridge to the ML module (torch imported lazily — the API never does).

Checkpoint policy (honest, never silent — resolution order fixed by configuration):
- MODEL_CHECKPOINT set        → the real run (e.g. runs/20260808-180238-0.1.0/checkpoint.pt).
- MODEL_URL set (AD-009)      → the real checkpoint downloaded once from a private repo
  (Hugging Face + read-only token; optional sha256 pin) into the cache dir.
- both unset                  → DEMO sample model (synthetic patterns, `0.0.0-sample`),
  generated once via `python -m ml.training.sample_model`. Every prediction made with
  it is flagged `demo=True` at the API/DB level — demo output is plumbing evidence,
  never a field-performance claim.

A configured-but-unreachable real checkpoint fails loudly; it never silently
downgrades to the sample model (that would change model identity under the user).
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from app.services import model_delivery

logger = logging.getLogger("cropmind.mlbridge")

_cache: dict[str, ModelHandle] = {}

SAMPLE_CKPT = Path("ml/models/pretrained/sample-mobilenetv3.pt")


def find_repo_root(start: Path | None = None) -> Path:
    """Locate the repo root in BOTH layouts.

    - local checkout: ``<repo>/backend/app/...`` (ml/ sits beside backend/)
    - worker container: ``/app/app/...`` (Dockerfile COPYs backend/app → /app/app,
      ml/ → /app/ml), so a hardcoded parents[N] lands on the filesystem root and
      the sample-model subprocess exits instantly with "No module named ml"
      (live failure caught on first Docker acceptance run 2026-08-09).
    Walks upward until a directory contains the ml/configs marker; refuses to guess.
    """
    start = Path(start).resolve() if start else Path(__file__).resolve()
    start_dir = start if start.is_dir() else start.parent
    for candidate in [start_dir, *start_dir.parents]:
        if (candidate / "ml" / "configs").is_dir():
            return candidate
    raise RuntimeError(f"repo root not found above {start} (no ml/configs marker)")


@dataclass
class ModelHandle:
    predictor: object  # ml.inference.predictor.Predictor (typed loosely: torch is worker-only)
    checkpoint_path: Path
    demo: bool
    origin: str = model_delivery.ORIGIN_SAMPLE  # which delivery path produced these weights (AD-009)


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


def get_predictor(
    checkpoint: str | None,
    repo_root: Path,
    device: str = "cpu",
    *,
    model_url: str | None = None,
    model_url_token: str | None = None,
    model_url_sha256: str | None = None,
    model_cache_dir: Path | None = None,
) -> ModelHandle:
    """Cached per resolved checkpoint. Imports torch/torchvision only on first real use.

    Empty-string values (compose passthrough default) mean "unset". Resolution order
    is configuration-fixed (see module docstring): local path → remote URL (AD-009)
    → clearly-flagged DEMO sample model. A failing remote download raises —
    there is no silent downgrade.
    """
    checkpoint = checkpoint or None
    model_url = model_url or None
    origin = model_delivery.weights_origin(checkpoint, model_url)
    demo = origin == model_delivery.ORIGIN_SAMPLE
    if origin == model_delivery.ORIGIN_LOCAL:
        ckpt_path = Path(checkpoint)
        if not ckpt_path.exists():
            raise FileNotFoundError(f"checkpoint not found: {ckpt_path}")
    elif origin == model_delivery.ORIGIN_REMOTE:
        if model_cache_dir is None:
            raise RuntimeError("MODEL_URL set but no model cache dir resolved (see settings.resolved_model_cache_dir)")
        ckpt_path = model_delivery.download_checkpoint(
            model_url, token=model_url_token, sha256=model_url_sha256, cache_dir=model_cache_dir
        )
        if not ckpt_path.exists():  # pragma: no cover - download contract
            raise FileNotFoundError(f"downloaded checkpoint missing: {ckpt_path}")
    else:
        ckpt_path = _ensure_sample_checkpoint(repo_root)
    key = f"{origin}:{ckpt_path}"
    if key in _cache:
        return _cache[key]
    from ml.inference.predictor import Predictor

    predictor = Predictor(ckpt_path, device=device)
    if demo:
        logger.warning("DEMO model active (%s) — predictions are plumbing demos, never crop claims", ckpt_path)
    else:
        logger.info("real checkpoint active via %s (%s)", origin, ckpt_path)
    handle = ModelHandle(predictor=predictor, checkpoint_path=ckpt_path, demo=demo, origin=origin)
    _cache[key] = handle
    return handle


def reset_cache() -> None:
    _cache.clear()
