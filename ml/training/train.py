"""Training loop for the baseline (Phase 3).

Contract (docs/05-ml-pipeline §3): every run writes runs/<run_id>/ containing
config copy, metrics.json (per-epoch history + held-out test metrics + per-class
P/R/F1), checkpoint.pt (state_dict + meta incl. class list, dataset manifest
sha, model_version, seed), and checkpoint sha256. Checksums recorded, weights
never committed to git.

    python -m ml.training.train --config ml/configs/train_v1.yaml
"""

import argparse
import hashlib
import json
import random
import shutil
import time
from datetime import UTC, datetime
from pathlib import Path

import torch
import yaml
from torch import nn

from ml.preprocessing.dataset import make_dataloaders
from ml.training.model import build_model, param_groups


def set_seed(seed: int) -> None:
    random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


def pick_device(cfg_device: str) -> torch.device:
    if cfg_device == "auto":
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")
    return torch.device(cfg_device)


def _autocast(device: torch.device, enabled: bool):
    if device.type == "cuda" and enabled:
        return torch.autocast(device_type="cuda")
    return torch.autocast(device_type="cpu", enabled=False)


def train_one_epoch(model, loader, criterion, optimizer, device, amp_enabled: bool) -> float:
    model.train()
    total_loss, total_n = 0.0, 0
    for images, labels in loader:
        images, labels = images.to(device), labels.to(device)
        optimizer.zero_grad(set_to_none=True)
        with _autocast(device, amp_enabled):
            logits = model(images)
            loss = criterion(logits, labels)
        loss.backward()
        optimizer.step()
        total_loss += loss.item() * labels.size(0)
        total_n += labels.size(0)
    return total_loss / max(total_n, 1)


@torch.no_grad()
def evaluate(model, loader, criterion, device, num_classes: int) -> dict:
    model.eval()
    total_loss, total_n, correct = 0.0, 0, 0
    per_tp = torch.zeros(num_classes)
    per_fp = torch.zeros(num_classes)
    per_fn = torch.zeros(num_classes)
    for images, labels in loader:
        images, labels = images.to(device), labels.to(device)
        logits = model(images)
        loss = criterion(logits, labels)
        preds = logits.argmax(dim=1)
        correct += (preds == labels).sum().item()
        total_loss += loss.item() * labels.size(0)
        total_n += labels.size(0)
        for c in range(num_classes):
            per_tp[c] += ((preds == c) & (labels == c)).sum().item()
            per_fp[c] += ((preds == c) & (labels != c)).sum().item()
            per_fn[c] += ((preds != c) & (labels == c)).sum().item()
    precision = (per_tp / (per_tp + per_fp).clamp(min=1)).tolist()
    recall = (per_tp / (per_tp + per_fn).clamp(min=1)).tolist()
    f1 = [
        2 * p * r / max(p + r, 1e-12) if (p + r) > 0 else 0.0
        for p, r in zip(precision, recall, strict=True)
    ]
    return {
        "top1": correct / max(total_n, 1),
        "loss": total_loss / max(total_n, 1),
        "support": int((per_tp + per_fn).sum().item()),
        "per_class": {"precision": precision, "recall": recall, "f1": f1, "support": (per_tp + per_fn).int().tolist()},
    }


def _scheduler(optimizer, warmup_epochs: int, total_epochs: int):
    def factor(epoch: int) -> float:
        if epoch < warmup_epochs:
            return (epoch + 1) / max(warmup_epochs, 1)
        progress = (epoch - warmup_epochs) / max(total_epochs - warmup_epochs, 1)
        return 0.5 * (1 + torch.cos(torch.tensor(progress * 3.14159265)).item())

    return torch.optim.lr_scheduler.LambdaLR(optimizer, factor)


def train(cfg: dict, config_dir: Path | None = None) -> dict:
    seed = cfg["run"].get("seed", 42)
    set_seed(seed)
    device = pick_device(cfg["train"].get("device", "auto"))
    built = make_dataloaders(cfg, config_dir)
    loaders, classes, manifest = built["loaders"], built["classes"], built["manifest"]
    num_classes = len(classes)

    model = build_model(num_classes, pretrained=cfg["model"].get("pretrained", True)).to(device)
    criterion = nn.CrossEntropyLoss(label_smoothing=cfg["train"].get("label_smoothing", 0.0))
    optimizer = torch.optim.AdamW(
        param_groups(model, cfg["train"]["lr_features"], cfg["train"]["lr_head"]),
        weight_decay=cfg["train"].get("weight_decay", 0.01),
    )
    scheduler = _scheduler(optimizer, cfg["train"].get("warmup_epochs", 1), cfg["train"]["epochs"])
    amp = bool(cfg["train"].get("amp", True))

    run_id = f"{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}-{cfg['run']['model_version']}"
    out_dir = Path(cfg["run"].get("out_dir", "runs")) / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    history, best_val, best_state, patience_left = [], 0.0, None, cfg["train"]["early_stopping_patience"]
    for epoch in range(cfg["train"]["epochs"]):
        started = time.time()
        train_loss = train_one_epoch(model, loaders["train"], criterion, optimizer, device, amp)
        val = evaluate(model, loaders["val"], criterion, device, num_classes)
        scheduler.step()
        row = {"epoch": epoch, "train_loss": train_loss, "val_top1": val["top1"], "val_loss": val["loss"], "seconds": round(time.time() - started, 2)}
        history.append(row)
        print(f"epoch {epoch:02d} | train_loss {train_loss:.4f} | val_top1 {val['top1']:.4f} | {row['seconds']}s")
        if val["top1"] > best_val:
            best_val = val["top1"]
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
            patience_left = cfg["train"]["early_stopping_patience"]
        else:
            patience_left -= 1
            if patience_left <= 0:
                print(f"early stop at epoch {epoch} (best val_top1 {best_val:.4f})")
                break

    if best_state is not None:
        model.load_state_dict(best_state)
    test = evaluate(model, loaders["test"], criterion, device, num_classes) if cfg["eval"].get("report_test_split", True) else None

    ckpt = {
        "format_version": 1,
        "arch": cfg["model"]["arch"],
        "state_dict": {k: v.cpu() for k, v in model.state_dict().items()},
        "meta": {
            "model_version": cfg["run"]["model_version"],
            "classes": classes,
            "num_classes": num_classes,
            "image_size": cfg["image"]["size"],
            "dataset": cfg["data"]["dataset"],
            "dataset_version": f"{cfg['data']['dataset']}@{manifest.get('version', 'unknown')}",
            "splits_content_sha256": manifest.get("content_sha256"),
            "seed": seed,
            "trained_utc": datetime.now(UTC).isoformat(timespec="seconds"),
            "trained_on": cfg["data"]["dataset"],
            "purpose": "baseline (docs/01 §6 M1)",
            "val_top1": best_val,
            "test_top1": test["top1"] if test else None,
        },
    }
    ckpt_path = out_dir / "checkpoint.pt"
    torch.save(ckpt, ckpt_path)
    sha = hashlib.sha256(ckpt_path.read_bytes()).hexdigest()
    (out_dir / "checkpoint.sha256").write_text(sha + "\n", encoding="utf-8")
    ckpt["meta"]["checkpoint_sha256"] = sha
    torch.save(ckpt, ckpt_path)  # re-save with sha embedded for the predictor

    shutil.copy(cfg.get("_config_path") or "", out_dir / "config.yaml") if cfg.get("_config_path") else None
    metrics = {
        "run_id": run_id,
        "device": str(device),
        "best_val_top1": best_val,
        "history": history,
        "test": test,
        "classes": classes,
        "dataset": ckpt["meta"]["dataset_version"],
        "splits_content_sha256": manifest.get("content_sha256"),
        "note": "Held-out test metrics, honest — do not cherry-pick. Phase 4 produces the full eval report incl. out-of-domain.",
    }
    (out_dir / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    return {"run_dir": str(out_dir), "checkpoint": str(ckpt_path), "sha256": sha, "best_val_top1": best_val, "test_top1": test["top1"] if test else None}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args(argv)
    cfg = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    cfg["_config_path"] = str(args.config)
    summary = train(cfg)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
