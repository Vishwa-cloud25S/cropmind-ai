"""Analysis execution: image + predictor contract -> rows (predictions, regions, model_versions).

Field-honesty mapping: every stored column comes from the shipped Predictor's dict —
status/phrasing/bands/INCONCLUSIVE semantics are never re-derived API-side. Regions are
IMAGE-SPACE (normalized xyxy polygon in GeoJSON shape with an explicit coordinate_space
label) — geographic mapping is the FieldMappingProvider interface (docs/02 §8).
The full contract is preserved verbatim in predictions.raw_json.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.db import models
from app.services.mlbridge import ModelHandle

logger = logging.getLogger("cropmind.analysis")

_EXPLAIN_SUBDIR = "explain"


def _region_geojson(bbox_xyxy_norm: list[float] | None) -> dict | None:
    if not bbox_xyxy_norm:
        return None
    x0, y0, x1, y1 = bbox_xyxy_norm
    return {
        "type": "Polygon",
        "coordinate_space": "image-normalized-xyxy",  # NOT geographic (docs/02 §8 provider later)
        "coordinates": [[[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]],
    }


def _register_model_version(
    session: Session, result: dict, ckpt_path: Path, ckpt_sha256: str | None, demo: bool
) -> models.ModelVersion:
    name, version = str(result.get("model_name") or "cropmind-leaf-classifier"), str(result["model_version"])
    existing = session.execute(
        select(models.ModelVersion).where(models.ModelVersion.name == name, models.ModelVersion.version == version)
    ).scalars().first()
    if existing is not None:
        return existing
    mv = models.ModelVersion(
        name=name,
        version=version,
        dataset_version=result.get("dataset_version"),
        threshold_version=result.get("threshold_version"),
        checkpoint_uri=str(ckpt_path),
        sha256=ckpt_sha256,
        demo=demo,
    )
    session.add(mv)
    session.flush()
    return mv


def _ckpt_sha256(handle: ModelHandle) -> str | None:
    """Predictor-side recorded sha when available (checkpoint.sha256 next to the weights)."""
    sidecar = handle.checkpoint_path.with_suffix(".sha256")
    try:
        return sidecar.read_text(encoding="utf-8").strip().split()[0] or None
    except OSError:
        return None


def process_analysis(
    session_factory: sessionmaker[Session],
    analysis_id: str,
    *,
    handle: ModelHandle,
    upload_dir: Path,
) -> None:
    """Idempotent executor: COMPLETED analyses are never re-processed."""
    with session_factory() as session:
        analysis = session.get(models.Analysis, analysis_id)
        if analysis is None:
            raise KeyError(f"analysis not found: {analysis_id}")
        if analysis.status == "COMPLETED":
            logger.info("analysis %s already COMPLETED — skipping", analysis_id)
            return
        image = analysis.image
        if image is None:
            raise LookupError(f"analysis {analysis_id} has no image")
        image_path = Path(upload_dir) / image.path
        explain_dir = Path(upload_dir) / _EXPLAIN_SUBDIR / analysis.id

        result: dict = handle.predictor.predict(image_path, explain_dir=explain_dir)  # full contract dict

        gradcam_rel = None
        if result.get("gradcam_overlay"):
            src = Path(result["gradcam_overlay"])
            if src.is_file():
                # Keep every stored path upload_dir-relative, like image rows.
                gradcam_rel = str(src.relative_to(Path(upload_dir).resolve()).as_posix()
                                   ) if src.is_relative_to(Path(upload_dir).resolve()) else None
                if gradcam_rel is None:
                    moved = explain_dir / src.name
                    explain_dir.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, moved)
                    gradcam_rel = f"{_EXPLAIN_SUBDIR}/{analysis.id}/{src.name}"

        mv = _register_model_version(session, result, handle.checkpoint_path, _ckpt_sha256(handle), handle.demo)
        regions = result.get("regions") or {}
        session.add(
            models.Prediction(
                analysis_id=analysis.id,
                model_version_id=mv.id,
                status=result["status"],
                crop=result["crop"],
                condition=result["condition"]["disease_id"],
                condition_name=result["condition"]["name"],
                confidence=float(result["confidence"]),
                band=result.get("confidence_band"),
                uncertainty=float(result["uncertainty"]),
                severity=result.get("estimated_visual_severity"),
                latency_ms=float(result["latency_ms"]),
                phrasing=result["phrasing"],
                demo=handle.demo,
                raw_json=result,
                gradcam_path=gradcam_rel,
            )
        )
        session.flush()
        prediction = session.execute(
            select(models.Prediction).where(models.Prediction.analysis_id == analysis_id)
        ).scalars().one()
        geometry = _region_geojson(regions.get("bbox_xyxy_norm"))
        if geometry is not None:
            area_px = None
            if regions.get("fraction") is not None and image.width and image.height:
                area_px = round(float(regions["fraction"]) * image.width * image.height)
            session.add(
                models.DetectionRegion(
                    prediction_id=prediction.id,
                    geometry_geojson=geometry,
                    area_px=area_px,
                    confidence=float(result["confidence"]),
                )
            )
        session.add(
            models.AuditLog(
                action="ANALYSIS_COMPLETED",
                entity="analysis",
                entity_id=analysis.id,
            )
        )
        session.commit()
