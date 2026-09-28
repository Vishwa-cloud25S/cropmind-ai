"""Pins the sample-model eval-mode contract (2026-09-28 live finding).

The sample checkpoint exists so the demo can exercise the FULL pipeline — including
SUSPECTED flows (zones, review, report). Without BN stat re-estimation the model
memorised its tiny synthetic corpus (train acc 1.0) while serving ~uniform softmax
( observed live: top-1 0.075 on every input => INCONCLUSIVE forever). This test
verifies the fixed recipe separates its own synthetic classes in EVAL mode. It says
nothing about real crop performance — the checkpoint meta says that too.
"""

from __future__ import annotations

import torch

from ml.training.classes import class_list
from ml.training.model import build_model
from ml.training.sample_model import _reestimate_bn_stats, build_sample_dataset
from ml.training.train import set_seed


def _train_small(model: torch.nn.Module, xs: torch.Tensor, ys: torch.Tensor, epochs: int = 25) -> None:
    optimizer = torch.optim.AdamW(model.parameters(), lr=2e-3)
    criterion = torch.nn.CrossEntropyLoss()
    model.train()
    for _ in range(epochs):
        order = torch.randperm(len(ys))
        for start in range(0, len(ys), 32):
            idx = order[start : start + 32]
            optimizer.zero_grad(set_to_none=True)
            loss = criterion(model(xs[idx]), ys[idx])
            loss.backward()
            optimizer.step()


def test_sample_recipe_separates_own_classes_in_eval_mode() -> None:
    set_seed(13)
    classes = class_list()
    model = build_model(len(classes), pretrained=False)
    xs, ys = build_sample_dataset(classes, per_class=4)  # small: keeps the test under ~a minute
    _train_small(model, xs, ys)
    _reestimate_bn_stats(model, xs)

    model.eval()
    with torch.no_grad():
        logits = model(xs)
        acc = (logits.argmax(dim=1) == ys).float().mean().item()
        top_conf = torch.softmax(logits, dim=1).max(dim=1).values.mean().item()
    # Contract: served-in-eval-mode behaviour must not collapse — otherwise demos can only
    # ever show INCONCLUSIVE (the pre-fix live behaviour, observed 2026-09-28). Training on
    # the tiny corpus is noisy (scaled recipe here: 0.905 acc / 0.829 conf; the committed
    # generator recipe per_class=10/20 epochs: 0.938 / 0.861), so thresholds are set wide:
    # they exist to catch the observed collapse regime (0.048 acc / 0.075 conf), not to
    # grade quality. This is plumbing consistency, never crop performance.
    assert acc >= 0.75, f"eval-mode acc collapsed: {acc}"
    assert top_conf >= 0.5, f"eval-mode confidence collapsed: {top_conf}"
