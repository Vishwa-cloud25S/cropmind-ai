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


def main() -> int:
    set_seed(13)
    classes = class_list()
    model = build_model(len(classes), pretrained=False)
    xs, ys = build_sample_dataset(classes, per_class=10)
    optimizer = torch.optim.AdamW(model.parameters(), lr=2e-3)
    criterion = torch.nn.CrossEntropyLoss()
    model.train()
    batch = 32
    for epoch in range(10):
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
