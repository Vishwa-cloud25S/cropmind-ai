"""Honest model + taxonomy metadata.

Every response states model availability explicitly — the UI must never imply
capability the configuration does not declare (spec §5, §9).
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.core.config import Settings, get_settings
from app.services.config_loader import ConfigNotFoundError, load_model_config, load_taxonomy

router = APIRouter(tags=["model"])

SettingsDep = Annotated[Settings, Depends(get_settings)]


@router.get("/supported-crops")
def supported_crops(settings: SettingsDep) -> dict:
    try:
        taxonomy = load_taxonomy(str(settings.resolved_ml_config_dir))
    except ConfigNotFoundError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    crops = taxonomy.get("crops", [])
    return {
        "taxonomy_version": taxonomy.get("version"),
        "updated": taxonomy.get("updated"),
        "model_available": taxonomy.get("model_available", False),
        "note": taxonomy.get("note"),
        "crop_count": len(crops),
        "crops": [
            {
                "crop_id": c["crop_id"],
                "name": c["name"],
                "status": c.get("status", "PLANNED"),
                "conditions": [
                    {
                        "disease_id": d["disease_id"],
                        "name": d["name"],
                        "dataset_source": d.get("dataset_source"),
                        "supported_by_model": d.get("supported_by_model", False),
                        "confidence_threshold": d.get("confidence_threshold"),
                    }
                    for d in c.get("conditions", [])
                ],
            }
            for c in crops
        ],
        "disclaimer": "Suspected-condition screening only — not a definitive diagnosis. "
        "Coverage grows only as licensed data and honest evaluation allow.",
    }


@router.get("/model-info")
def model_info(settings: SettingsDep) -> dict:
    try:
        config = load_model_config(str(settings.resolved_ml_config_dir))
    except ConfigNotFoundError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {
        "model": config.get("model", {}),
        "confidence_bands": config.get("confidence_bands"),
        "uncertainty_method": (config.get("uncertainty") or {}).get("method"),
        "severity_method": (config.get("severity") or {}).get("method"),
        "updated": config.get("updated"),
        "registry_note": "Model weights, evaluation reports and dataset provenance are versioned "
        "via model_versions / dataset_sources (Phase 5). Predictions will record "
        "model_version + dataset_version for reproducibility.",
        "client_notice": "Predictions are decision support requiring human verification. "
        "No chemical product or dosage guidance is provided.",
    }
