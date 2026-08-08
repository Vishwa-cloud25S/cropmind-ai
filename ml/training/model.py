"""Model builder — MobileNetV3-Small transfer baseline (registry decision, ADR-005).

Head is replaced with a fresh linear classifier sized to the taxonomy class list.
Param groups separate feature extractor (low lr) from head (higher lr).
"""

from torch import nn
from torchvision.models import MobileNet_V3_Small_Weights, mobilenet_v3_small


def build_model(num_classes: int, pretrained: bool = True, arch: str = "mobilenet_v3_small") -> nn.Module:
    if arch != "mobilenet_v3_small":
        raise ValueError(f"unsupported arch {arch!r} (registry keeps one baseline per version)")
    weights = MobileNet_V3_Small_Weights.DEFAULT if pretrained else None
    model = mobilenet_v3_small(weights=weights)
    in_features = model.classifier[-1].in_features
    model.classifier[-1] = nn.Linear(in_features, num_classes)
    model.class_list_head = num_classes  # introspection convenience
    return model


def param_groups(model: nn.Module, lr_features: float, lr_head: float) -> list[dict]:
    head_params = list(model.classifier.parameters())
    head_ids = {id(p) for p in head_params}
    feature_params = [p for p in model.parameters() if id(p) not in head_ids]
    return [
        {"params": feature_params, "lr": lr_features},
        {"params": head_params, "lr": lr_head},
    ]
