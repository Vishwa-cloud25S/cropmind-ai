"""Reading deterministic split files (train/val/test.txt) into torch datasets.

Split files are produced by ml.data.cli: lines of "relpath<TAB>disease_id"
relative to the manifest's images_root. Labels use the canonical class order
(ml.training.classes) — the SAME order saved into checkpoints.
"""

import json
from pathlib import Path

from PIL import Image
from torch.utils.data import DataLoader, Dataset

from ml.data.winpath import windows_safe
from ml.training.classes import class_list


class SplitDataset(Dataset):
    def __init__(self, images_root: Path, split_file: Path, classes: list[str], transform=None):
        self.images_root = Path(images_root)
        self.transform = transform
        self.class_to_idx = {c: i for i, c in enumerate(classes)}
        self.items: list[tuple[Path, int]] = []
        for line in Path(split_file).read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rel, disease_id = line.split("\t", 1)
            self.items.append((self.images_root / rel, self.class_to_idx[disease_id]))

    def __len__(self) -> int:
        return len(self.items)

    def __getitem__(self, idx: int):
        path, label = self.items[idx]
        image = Image.open(windows_safe(path)).convert("RGB")  # windows_safe: no-op on short/POSIX paths
        if self.transform is not None:
            image = self.transform(image)
        return image, label


def load_manifest(splits_dir: Path) -> dict:
    return json.loads((Path(splits_dir) / "split_manifest.json").read_text(encoding="utf-8"))


def make_dataloaders(cfg: dict, config_dir: Path | None = None) -> dict:
    data_cfg, img_cfg, train_cfg = cfg["data"], cfg["image"], cfg["train"]
    manifest = load_manifest(Path(data_cfg["splits_dir"]))
    images_root = Path(manifest["images_root"])
    classes = class_list(config_dir)
    transforms_by_split = {
        "train": True,
        "val": False,
        "test": False,
    }
    loaders = {}
    for name, is_train in transforms_by_split.items():
        transform = None
        from ml.preprocessing.transforms import build_transforms

        transform = build_transforms(
            image_size=img_cfg["size"],
            train=is_train,
            aug_cfg=cfg.get("augmentation") if is_train else None,
        )
        ds = SplitDataset(images_root, Path(data_cfg["splits_dir"]) / f"{name}.txt", classes, transform)
        loaders[name] = DataLoader(
            ds,
            batch_size=train_cfg["batch_size"],
            shuffle=is_train,
            num_workers=train_cfg.get("num_workers", 0),
            pin_memory=train_cfg.get("device", "auto") != "cpu",
        )
    return {"loaders": loaders, "classes": classes, "manifest": manifest}
