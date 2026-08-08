"""In-house Grad-CAM for MobileNetV3-Small + overlay/region extraction.

Honesty contract (model.yaml explainability.ui_caveat): heatmaps show which
regions contributed strongly to the model's prediction — they are correlation,
not proof of disease location. Regions derived from heat thresholding are an
explicitly-labelled proxy until the licensed detector (Phase 4) exists.
"""

import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image

DEFAULT_TARGET = "features.-1"  # last conv block of MobileNetV3 features


class GradCAM:
    def __init__(self, model: torch.nn.Module, target_layer: torch.nn.Module | None = None):
        self.model = model
        self.target = target_layer if target_layer is not None else infer_target(model)
        self._activations: torch.Tensor | None = None
        self._gradients: torch.Tensor | None = None
        self._handles = [
            self.target.register_forward_hook(self._fw_hook),
            self.target.register_full_backward_hook(self._bw_hook),
        ]

    def _fw_hook(self, module, args, output):
        self._activations = output.detach()

    def _bw_hook(self, module, grad_input, grad_output):
        self._gradients = grad_output[0].detach()

    def close(self):
        for handle in self._handles:
            handle.remove()

    def generate(self, input_tensor: torch.Tensor, class_idx: int) -> np.ndarray:
        """input_tensor: (1,C,H,W) with grad enabled graph; returns heat (H,W) in [0,1]."""
        self.model.zero_grad(set_to_none=True)
        logits = self.model(input_tensor)
        score = logits[0, class_idx]
        score.backward(retain_graph=False)
        act, grad = self._activations, self._gradients
        if act is None or grad is None:
            raise RuntimeError("hooks captured nothing - check target layer")
        weights = grad.mean(dim=(2, 3), keepdim=True)
        cam = torch.relu((weights * act).sum(dim=1, keepdim=True))
        cam = F.interpolate(cam, size=input_tensor.shape[-2:], mode="bilinear", align_corners=False)
        heat = cam[0, 0].cpu().numpy()
        heat -= heat.min()
        peak = heat.max()
        return heat / peak if peak > 0 else np.zeros_like(heat)


def infer_target(model: torch.nn.Module) -> torch.nn.Module:
    """Last block of the features stack (explicit, introspectable target layer)."""
    return model.features[-1]


_COLOR_LUT = np.array(
    [
        [int(255 * t), int(255 * min(1.0, 2 * t if t < 0.5 else 2 - 2 * t)), int(255 * (1 - t))]
        for t in np.linspace(0, 1, 256)
    ],
    dtype=np.uint8,
)  # simple blue→green→red ramp, no OpenCV dependency


def overlay_heatmap(pil_image: Image.Image, heat: np.ndarray, alpha: float = 0.45) -> Image.Image:
    """Blend RGB image with heatmap colorized via LUT. Returns PIL Image (same size)."""
    base_rgb = np.asarray(pil_image.convert("RGB")).astype(np.float32)
    heat_resized = np.asarray(
        Image.fromarray((heat * 255).astype(np.uint8)).resize(pil_image.size, Image.BILINEAR)
    )
    color = _COLOR_LUT[heat_resized].astype(np.float32)
    blended = (1 - alpha) * base_rgb + alpha * color
    return Image.fromarray(np.clip(blended, 0, 255).astype(np.uint8))


def regions_from_heat(heat: np.ndarray, threshold: float = 0.5, grid: int = 16) -> dict:
    """Coarse affected-region proxy: fraction of grid cells whose mean heat >= threshold,
    plus their bounding box in normalized xyxy coords. Label: proxy regions."""
    if heat.size == 0:
        return {"num_cells": 0, "fraction": 0.0, "bbox_xyxy_norm": None, "threshold": threshold}
    h, w = heat.shape
    gh, gw = max(h // grid, 1), max(w // grid, 1)
    cells = []
    for y in range(0, h, gh):
        for x in range(0, w, gw):
            if heat[y : y + gh, x : x + gw].mean() >= threshold:
                cells.append((x / w, y / h, min(x + gw, w) / w, min(y + gh, h) / h))
    if not cells:
        return {"num_cells": 0, "fraction": 0.0, "bbox_xyxy_norm": None, "threshold": threshold}
    xs0, ys0, xs1, ys1 = zip(*cells, strict=True)
    return {
        "num_cells": len(cells),
        "fraction": len(cells) / ((len(range(0, h, gh))) * (len(range(0, w, gw)))),
        "bbox_xyxy_norm": [min(xs0), min(ys0), max(xs1), max(ys1)],
        "threshold": threshold,
    }
