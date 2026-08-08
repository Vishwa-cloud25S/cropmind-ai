"""Inference contract (docs/05-ml-pipeline §5).

Every prediction carries: prediction_id, crop, condition, confidence, band,
uncertainty, estimated_visual_severity, regions, model_version, dataset_version,
threshold_version, latency_ms, timestamp — plus Grad-CAM artifact and the honest
client notices. Bands come from ml/configs/model.yaml, never hardcoded.

Below the LOW band the result is status INCONCLUSIVE with retake/review advice —
the API must never present a confident diagnosis.
"""

import math
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import torch
import yaml
from PIL import Image

from ml.explainability.gradcam import GradCAM, overlay_heatmap, regions_from_heat
from ml.preprocessing.transforms import build_inference_transform
from ml.training.classes import class_list, condition_name, crop_of
from ml.training.model import build_model

DEFAULT_CONFIG_DIR = Path(__file__).resolve().parents[1] / "configs"


@dataclass
class Prediction:
    prediction_id: str
    status: str  # SUSPECTED | INCONCLUSIVE
    phrasing: str  # e.g. "Suspected Tomato - Early blight - 87% confidence"
    crop: str
    condition: dict  # {disease_id, name}
    confidence: float
    confidence_band: str | None  # HIGH | MEDIUM | LOW | None when inconclusive
    uncertainty: float  # normalized predictive entropy [0,1]
    estimated_visual_severity: float  # proxy, labeled
    severity_label: str
    regions: dict
    gradcam_overlay: str | None
    model_version: str
    dataset_version: str | None
    threshold_version: str | None
    latency_ms: float
    timestamp: str
    top_k: list = field(default_factory=list)
    limitation_notice: str = ""
    explainability_caveat: str = ""


class Predictor:
    def __init__(self, checkpoint_path: Path, config_dir: Path | None = None, device: str = "auto"):
        self.config_dir = Path(config_dir) if config_dir else DEFAULT_CONFIG_DIR
        self.thresholds_cfg = yaml.safe_load((self.config_dir / "model.yaml").read_text(encoding="utf-8"))
        self.bands = self.thresholds_cfg["confidence_bands"]
        self.threshold_version = self.thresholds_cfg.get("version")
        self.explainability_caveat = self.thresholds_cfg.get("explainability", {}).get("ui_caveat", "")
        self.severity_label = self.thresholds_cfg.get("severity", {}).get("label", "Estimated visual severity")

        ckpt = torch.load(Path(checkpoint_path), map_location="cpu", weights_only=False)
        self.meta = ckpt["meta"]
        self.classes: list[str] = self.meta["classes"]
        self.image_size = self.meta.get("image_size", 224)
        tax_classes = class_list(self.config_dir)
        if set(self.classes) != set(tax_classes):
            raise ValueError("checkpoint class list does not match taxonomy.yaml")
        self.model = build_model(len(self.classes), pretrained=False, arch=ckpt["arch"])
        self.model.load_state_dict(ckpt["state_dict"])
        self.device = torch.device("cuda" if (device == "auto" and torch.cuda.is_available()) else "cpu") if device == "auto" else torch.device(device)
        self.model.to(self.device).eval()
        self.transform = build_inference_transform(self.image_size)
        self._idx_to_class = {i: c for i, c in enumerate(self.classes)}

    def band_for(self, confidence: float) -> str | None:
        if confidence >= self.bands["high"]:
            return "HIGH"
        if confidence >= self.bands["medium"]:
            return "MEDIUM"
        if confidence >= self.bands["low"]:
            return "LOW"
        return None  # below LOW band -> inconclusive

    def predict(self, image_path: Path, explain_dir: Path | None = None, top_k: int = 3) -> dict:
        started = time.perf_counter()
        pil = Image.open(image_path).convert("RGB")
        input_tensor = self.transform(pil).unsqueeze(0).to(self.device)

        input_for_cam = input_tensor.clone().requires_grad_(True)
        with torch.no_grad():
            logits = self.model(input_tensor)
        probs = torch.softmax(logits, dim=1)[0]
        k = min(top_k, probs.numel())
        top_probs, top_idx = torch.topk(probs, k=k)
        class_idx = int(top_idx[0].item())
        confidence = float(top_probs[0].item())
        entropy = float(-(probs * probs.clamp(min=1e-12).log()).sum().item())
        uncertainty = entropy / math.log(probs.numel())

        # Grad-CAM (also feeds the visual-severity proxy)
        overlay_path = None
        cam = GradCAM(self.model)
        try:
            heat = cam.generate(input_for_cam, class_idx)
        finally:
            cam.close()
        regions = regions_from_heat(heat, threshold=self.thresholds_cfg.get("localization", {}).get("region_threshold", 0.5))
        if explain_dir is not None:
            explain_dir = Path(explain_dir)
            explain_dir.mkdir(parents=True, exist_ok=True)
            overlay_path = str(explain_dir / f"{uuid.uuid4().hex[:12]}-gradcam.png")
            overlay_heatmap(pil, heat).save(overlay_path)

        band = self.band_for(confidence)
        status = "SUSPECTED" if band is not None else "INCONCLUSIVE"
        disease_id = self._idx_to_class[class_idx]
        crop = crop_of(disease_id, self.config_dir)
        name = condition_name(disease_id, self.config_dir)
        phrasing = (
            f"Suspected {crop} - {name} - {confidence * 100:.0f}% confidence"
            if status == "SUSPECTED"
            else f"Inconclusive ({crop} - {name} at {confidence * 100:.0f}% is below the LOW band) - retake photo or request agronomist review"
        )
        result = Prediction(
            prediction_id=uuid.uuid4().hex[:16],
            status=status,
            phrasing=phrasing,
            crop=crop,
            condition={"disease_id": disease_id, "name": name},
            confidence=round(confidence, 4),
            confidence_band=band,
            uncertainty=round(uncertainty, 4),
            estimated_visual_severity=round(float(regions["fraction"]), 4),
            severity_label=self.severity_label,
            regions=regions,
            gradcam_overlay=overlay_path,
            model_version=str(self.meta.get("model_version")),
            dataset_version=self.meta.get("dataset_version"),
            threshold_version=self.threshold_version,
            latency_ms=round((time.perf_counter() - started) * 1000, 1),
            timestamp=datetime.now(UTC).isoformat(timespec="seconds"),
            top_k=[
                {"disease_id": self._idx_to_class[int(i.item())], "confidence": round(float(p.item()), 4)}
                for p, i in zip(top_probs, top_idx, strict=True)
            ],
            limitation_notice=(
                "Decision support only - not a definitive diagnosis; verify with an agronomist. "
                "No chemical product or dosage guidance is provided."
            ),
            explainability_caveat=self.explainability_caveat,
        )
        return asdict(result)


def load_sample_checkpoint_path() -> Path:
    return Path(__file__).resolve().parents[1] / "models" / "pretrained" / "sample-mobilenetv3.pt"
