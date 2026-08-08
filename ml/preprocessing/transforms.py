"""Image transforms.

Augmentation exists ONLY for the training split (leakage policy,
docs/05-ml-pipeline §2): validation/test/inference use the deterministic
resize → CenterCrop → ImageNet-normalize pipeline.
"""

import torch
from torchvision.transforms import v2 as T

IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)


def build_transforms(image_size: int = 224, train: bool = False, aug_cfg: dict | None = None):
    base = [T.ToImage()]
    if train and aug_cfg:
        jitter = aug_cfg.get("color_jitter", {})
        base += [
            T.RandomResizedCrop(image_size, scale=tuple(aug_cfg.get("random_resized_crop_scale", (0.7, 1.0)))),
            T.RandomHorizontalFlip(p=aug_cfg.get("hflip_prob", 0.5)),
            T.RandomRotation(degrees=aug_cfg.get("rotation_deg", 15)),
            T.ColorJitter(
                brightness=jitter.get("brightness", 0.2),
                contrast=jitter.get("contrast", 0.2),
                saturation=jitter.get("saturation", 0.15),
            ),
        ]
    else:
        base += [T.Resize(image_size + 32), T.CenterCrop(image_size)]
    base += [
        T.ToDtype(torch.float32, scale=True),
        T.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
    ]
    return T.Compose(base)


def build_inference_transform(image_size: int = 224):
    return build_transforms(image_size=image_size, train=False)
