"""Generates the SAMPLE checkpoint used for pipeline/demo plumbing.

The sample model is trained for a few steps on SYNTHETIC class-dependent color
patterns (never on real field data). It exists so the inference/UX pipeline can
be exercised end-to-end before the real PlantVillage run completes. Its meta is
labelled accordingly and it MUST NOT be cited as field performance.

    python -m ml.training.sample_model
"""

from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import torch
from PIL import Image

from ml.training.classes import class_list
from ml.training.model import build_model
from ml.training.train import set_seed

OUT = Path(__file__).resolve().parents[1] / "models" / "pretrained" / "sample-mobilenetv3.pt"


def _pattern_image(disease_id: str, idx: int, size: int = 96) -> Image.Image:
    """Class-dependent dominant channel + light noise — trivially learnable signal."""
    crc = sum(ord(c) for c in disease_id)
    rng = np.random.default_rng(crc * 997 + idx)
    base = np.array([30 + (crc * 53) % 150, 30 + (crc * 91) % 150, 30 + (crc * 37) % 150], dtype=np.float32)
    base[crc % 3] = 230.0  # dominant channel per class
    noise = rng.normal(0, 8, size=(size, size, 3)).astype(np.float32)
    img = np.clip(base + noise, 0, 255).astype(np.uint8)
    return Image.fromarray(img)


def build_sample_dataset(classes: list[str], per_class: int = 10, size: int = 96):
    from ml.preprocessing.transforms import build_inference_transform

    transform = build_inference_transform(size)
    xs, ys = [], []
    for label, disease_id in enumerate(classes):
        for i in range(per_class):
            xs.append(transform(_pattern_image(disease_id, i, size)))
            ys.append(label)
    return torch.stack(xs), torch.tensor(ys)


def _reestimate_bn_stats(model: torch.nn.Module, xs: torch.Tensor, passes: int = 4) -> None:
    """Re-estimate BatchNorm running statistics over the sample corpus (no learning).

    The synthetic corpus is tiny and gets memorised within a few epochs; the default
    momentum-averaged BN running stats then mismatch eval mode so badly that served
    confidence collapses to ~1/num_classes on every input (measured 2026-09-28:
    train acc 1.000, served top-1 0.075 uniform). A few full-corpus forward passes
    with cumulative statistics restore eval-mode behaviour. The checkpoint stays what
    its meta says: synthetic-pattern plumbing, never performance evidence.
    """
    for module in model.modules():
        if isinstance(module, torch.nn.modules.batchnorm._BatchNorm):
            module.reset_running_stats()
            module.momentum = None  # cumulative moving average over the passes below
    model.train()
    with torch.no_grad():
        for _ in range(passes):
            model(xs)


def main() -> int:
    set_seed(13)
    classes = class_list()
    model = build_model(len(classes), pretrained=False)
    xs, ys = build_sample_dataset(classes, per_class=10)
    optimizer = torch.optim.AdamW(model.parameters(), lr=2e-3)
    criterion = torch.nn.CrossEntropyLoss()
    model.train()
    batch = 32
    for epoch in range(20):  # 2026-09-28: 10 -> 20 epochs — see _reestimate_bn_stats note
        order = torch.randperm(len(ys))
        total = 0.0
        for start in range(0, len(ys), batch):
            idx = order[start : start + batch]
            optimizer.zero_grad(set_to_none=True)
            loss = criterion(model(xs[idx]), ys[idx])
            loss.backward()
            optimizer.step()
            total += loss.item()
        print(f"sample epoch {epoch} | loss {total:.3f}")
    # Serve in eval mode, honestly: without stat re-estimation the memorised tiny
    # corpus trains to acc 1.0 while served predictions collapse to ~uniform
    # (batchnorm momentum-running stats mismatch) — the demo could then only ever
    # answer INCONCLUSIVE (observed live 2026-09-28).
    _reestimate_bn_stats(model, xs)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    meta = {
        "model_version": "0.0.0-sample",
        "classes": classes,
        "num_classes": len(classes),
        "image_size": 96,
        "dataset": "synthetic-patterns",
        "dataset_version": None,
        "splits_content_sha256": None,
        "seed": 13,
        "trained_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "trained_on": "SYNTHETIC class-color patterns (not real field imagery)",
        "purpose": "pipeline/demo plumbing only — MUST NOT be cited as field performance",
        "val_top1": None,
        "test_top1": None,
    }
    torch.save({"format_version": 1, "arch": "mobilenet_v3_small", "state_dict": model.state_dict(), "meta": meta}, OUT)
    print(f"sample checkpoint written: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
