import json
from pathlib import Path

import pytest
import torch
from PIL import Image

from ml.data import split as split_mod
from ml.preprocessing.transforms import build_inference_transform, build_transforms
from ml.training import train as train_mod
from ml.training.classes import class_list, condition_name, crop_of
from ml.training.model import build_model

EXPECTED_CLASS_COUNT = 21  # 10 tomato + 3 potato + 4 corn + 4 apple


def test_class_list_from_taxonomy():
    classes = class_list()
    assert len(classes) == EXPECTED_CLASS_COUNT
    assert classes == sorted(classes)
    assert {"tomato_early_blight", "potato_late_blight", "corn_common_rust", "apple_scab"} <= set(classes)


def test_crop_and_condition_lookup():
    assert crop_of("tomato_early_blight") == "Tomato"
    assert crop_of("corn_common_rust") == "Corn (maize)"
    assert crop_of("apple_scab") == "Apple"
    assert condition_name("potato_late_blight") == "Late blight"
    assert condition_name("unknown_x") == "unknown_x"


def test_model_build_output_dim():
    model = build_model(EXPECTED_CLASS_COUNT, pretrained=False)
    out = model(torch.zeros(1, 3, 64, 64))
    assert out.shape == (1, EXPECTED_CLASS_COUNT)


def test_transforms_shapes_and_no_aug_on_eval(tmp_path):
    img = Image.new("RGB", (200, 100), (10, 200, 30))
    eval_t = build_inference_transform(image_size=64)
    tensor = eval_t(img)
    assert tensor.shape == (3, 64, 64)
    assert tensor.dtype == torch.float32
    train_t = build_transforms(image_size=64, train=True, aug_cfg={"hflip_prob": 0.5})
    assert train_t(img).shape == (3, 64, 64)


@pytest.fixture()
def toy_split_dir(tmp_path, toy_images_root):
    out_dir = tmp_path / "splits" / "plantvillage" / "v1"
    split_mod.split_dataset(toy_images_root, out_dir, "plantvillage", seed=7)
    return out_dir


def _smoke_config(tmp_path, toy_split_dir):
    return {
        "run": {"name": "smoke", "model_version": "0.0.0-test", "out_dir": str(tmp_path / "runs"), "seed": 5},
        "data": {"dataset": "plantvillage", "splits_dir": str(toy_split_dir), "class_source": "taxonomy"},
        "image": {"size": 64},
        "model": {"arch": "mobilenet_v3_small", "pretrained": False},
        "train": {
            "device": "cpu",
            "epochs": 1,
            "batch_size": 4,
            "num_workers": 0,
            "optimizer": "adamw",
            "lr_head": 0.001,
            "lr_features": 0.0001,
            "weight_decay": 0.01,
            "scheduler": "cosine",
            "warmup_epochs": 1,
            "early_stopping_patience": 3,
            "amp": False,
        },
        "augmentation": {},
        "eval": {"report_test_split": True},
    }


def test_training_smoke_run_writes_config_metrics_checkpoint(tmp_path, toy_split_dir):
    cfg = _smoke_config(tmp_path, toy_split_dir)
    summary = train_mod.train(cfg)

    assert summary["best_val_top1"] is not None
    ckpt_path = Path(summary["checkpoint"])
    assert ckpt_path.exists()
    ckpt = torch.load(ckpt_path, map_location="cpu", weights_only=False)
    assert ckpt["meta"]["num_classes"] == EXPECTED_CLASS_COUNT
    assert ckpt["meta"]["classes"] == class_list()
    assert len(ckpt["meta"]["checkpoint_sha256"]) == 64

    run_dir = Path(summary["run_dir"])
    metrics = json.loads((run_dir / "metrics.json").read_text())
    assert metrics["test"]["support"] > 0
    assert 0.0 <= metrics["test"]["top1"] <= 1.0
    assert len(metrics["history"]) == 1
    assert metrics["splits_content_sha256"] is not None
