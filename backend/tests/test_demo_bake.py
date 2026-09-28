"""Phase 12 addendum (2026-09-28) — demo image bakes the sample checkpoint.

Runtime checkpoint generation starved/OOM-looped the free 512 MB instance at the
first analysis (live-observed, docs/12 §7). The bake must stay in the Dockerfile,
and it must stay the SYNTHETIC sample model (AD-008: no real checkpoint ships).
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_demo_image_bakes_only_the_synthetic_sample_checkpoint() -> None:
    dockerfile = (REPO_ROOT / "docker" / "demo.Dockerfile").read_text(encoding="utf-8")
    assert "python -m ml.training.sample_model" in dockerfile, (
        "demo image must bake the sample checkpoint at build time "
        "(runtime generation starves the free instance — docs/12 §7)"
    )
    assert "test -f /app/ml/models/pretrained/sample-mobilenetv3.pt" in dockerfile
    # AD-008 stays true textually: the header keeps declaring no real checkpoint ships.
    assert "No real checkpoint is ever shipped here (AD-008)" in dockerfile
    assert "0.0.0-sample" in dockerfile
