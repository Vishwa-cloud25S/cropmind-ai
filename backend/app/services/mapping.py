"""Field mapping + intervention zones (Phase 7).

Geo-honesty rules (these are the product's integrity, not implementation detail):

1. Image GPS coordinates are *deliberately stripped at upload* (privacy by design,
   docs/02 §9) — the system does not know where a leaf photo was taken and refuses
   to invent it. Zone geometry therefore stays in the coordinate space of its
   evidence (`image-normalized-xyxy`, same as the prediction regions) and every
   zone says `georeference_source: "none"` until a genuinely georeferenced source
   (drone orthomosaic with a GeoTIFF transform) provides an honest pixel→geo map.
2. Risk level + review priority are deterministic, documented rules over the
   prediction's own numbers (confidence band + labelled severity proxy) — never a
   second hidden model, never a marketing score.
3. INCONCLUSIVE analyses generate *no* zones: the system abstained, so there is
   nothing honest to intervene on.
4. No pesticide, product or dosage content anywhere in zone payloads — zones are
   precision-intervention *simulations* pending human review (PENDING →
   APPROVED/REJECTED), and exports carry the simulation label in filename + body.
"""

from __future__ import annotations

import csv
import io
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db import models

IMAGE_COORD_SPACE = "image-normalized-xyxy"
GEOREFERENCE_NONE = "none"

SIMULATION_LABEL = "precision intervention zone simulation"
AREA_NOTE_UNLOCATED = "area unknown in hectares — observation is not georeferenced (image-space evidence only)"

RISK_ORDER = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]

_REVIEW_PRIORITY = {  # 1 = review first; matches docs/04 §3.7
    "CRITICAL": (1, "review first"),
    "HIGH": (2, "review this week"),
    "MEDIUM": (3, "routine review"),
    "LOW": (4, "low priority"),
}


def derive_risk_level(band: str, severity: float | None) -> tuple[str, str]:
    """Deterministic risk from the prediction's own band + labelled severity proxy.

    score = band score (LOW→1, MEDIUM→2, HIGH→3) + 1 when the visual-severity
    proxy is at/above settings.zone_severity_critical. score → LOW/MEDIUM/HIGH/
    CRITICAL at 1/2/3/4. Returns (level, human-readable basis). INCONCLUSIVE
    predictions (band is None) never reach this function — no zones are made.
    """
    band_score = {"LOW": 1, "MEDIUM": 2, "HIGH": 3}[band]
    threshold = get_settings().zone_severity_critical
    severity_bonus = 1 if (severity is not None and severity >= threshold) else 0
    level = {1: "LOW", 2: "MEDIUM", 3: "HIGH", 4: "CRITICAL"}[band_score + severity_bonus]
    basis = f"band {band} (score {band_score})"
    if severity_bonus:
        basis += f" + visual severity ≥ {threshold}"
    return level, basis


def review_priority(risk_level: str) -> tuple[int, str]:
    """Review urgency derived from risk (1 = review first). Display science, not ML."""
    return _REVIEW_PRIORITY[risk_level]


# ── zone generation ────────────────────────────────────────────────────────────


def generate_zones(db: Session, analysis: models.Analysis) -> tuple[list[models.InterventionZone], str]:
    """Create zones from a COMPLETED analysis's prediction regions.

    Regenerate semantics: existing PENDING zones for the analysis are replaced;
    APPROVED/REJECTED zones are kept untouched (human decisions are never silently
    overwritten — a re-run adds fresh PENDING zones alongside the reviewed ones).

    Returns (created_zones, note). For INCONCLUSIVE predictions creates nothing and
    says so: abstaining analyses honestly have no zones.
    """
    prediction = analysis.prediction
    if prediction is None:
        raise ValueError("analysis has no prediction yet")
    if prediction.status == "INCONCLUSIVE" or prediction.band is None:
        return [], "no zones generated — the analysis is INCONCLUSIVE; the system abstained on this evidence"

    stale = db.execute(
        select(models.InterventionZone).where(
            models.InterventionZone.analysis_id == analysis.id,
            models.InterventionZone.review_status == "PENDING",
        )
    ).scalars().all()
    kept = db.execute(
        select(func.count())
        .select_from(models.InterventionZone)
        .where(
            models.InterventionZone.analysis_id == analysis.id,
            models.InterventionZone.review_status != "PENDING",
        )
    ).scalar_one()
    for zone in stale:
        db.delete(zone)

    created: list[models.InterventionZone] = []
    regions = prediction.regions or []
    risk, _basis = derive_risk_level(prediction.band, prediction.severity)
    for region in regions:
        geometry = dict(region.geometry_geojson)
        geometry["coordinate_space"] = IMAGE_COORD_SPACE  # stays in evidence space — see module docstring
        zone = models.InterventionZone(
            analysis_id=analysis.id,
            zone_geojson=geometry,
            risk_level=risk,
            condition=prediction.condition_name,
            confidence=prediction.confidence,
            severity=prediction.severity,
            est_area_ha=None,  # honest null: no scale without georeference (area_note in payload)
            review_status="PENDING",
        )
        db.add(zone)
        created.append(zone)
    if not regions:  # the prediction carried no regions: one image-wide zone is still honest evidence
        geometry = {
            "type": "Polygon",
            "coordinate_space": IMAGE_COORD_SPACE,
            "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]],
        }
        zone = models.InterventionZone(
            analysis_id=analysis.id,
            zone_geojson=geometry,
            risk_level=risk,
            condition=prediction.condition_name,
            confidence=prediction.confidence,
            severity=prediction.severity,
            est_area_ha=None,
            review_status="PENDING",
        )
        db.add(zone)
        created.append(zone)
    db.flush()

    note = f"{len(created)} zone(s) in {IMAGE_COORD_SPACE} (georeference: none — see docs)"
    if kept:
        note += f"; {kept} previously-reviewed zone(s) kept untouched"
    return created, note


# ── payloads ───────────────────────────────────────────────────────────────────


def zone_payload(zone: models.InterventionZone, analysis: models.Analysis | None = None) -> dict[str, Any]:
    analysis = analysis if analysis is not None else zone.analysis
    risk = zone.risk_level
    priority, priority_note = review_priority(risk)
    prediction = analysis.prediction
    band = prediction.band if prediction else None
    severity = zone.severity
    # Basis describes the stored evidence the documented rule consumed at generation
    # time (services/mapping.derive_risk_level) — the stored level is authoritative.
    basis = f"from band {band}" if band else "band unavailable on source prediction"
    if severity is not None:
        basis += f", visual severity {severity:.2f} (proxy)"
    return {
        "id": zone.id,
        "analysis_id": zone.analysis_id,
        "field_id": analysis.field_id if analysis else None,
        "image_id": analysis.image_id if analysis else None,
        "geometry": zone.zone_geojson,
        "condition": zone.condition,
        "confidence": zone.confidence,
        "severity": severity,
        "risk_level": risk,
        "risk_basis": basis,
        "review_priority": priority,
        "review_priority_note": priority_note,
        "review_status": zone.review_status,
        "review_note": zone.review_note,
        "reviewed_at": zone.reviewed_at.isoformat() if zone.reviewed_at else None,
        "georeference_source": GEOREFERENCE_NONE,
        "est_area_ha": zone.est_area_ha,
        "area_note": AREA_NOTE_UNLOCATED if zone.est_area_ha is None else None,
        "simulation_label": SIMULATION_LABEL,
        "created_at": zone.created_at.isoformat() if zone.created_at else None,
    }


# ── field boundary validation (real geographic data the user draws) ────────────


def validate_wgs84_polygon(value: Any) -> dict[str, Any]:
    """Strict GeoJSON Polygon in lon/lat — the only geographic geometry we store.

    Raises ValueError with a precise human reason on violation; returns the polygon
    unchanged on success. Auto-fixing user geometry silently is not done here:
    the client previews and the API states exactly what is wrong.
    """
    if not isinstance(value, dict) or value.get("type") != "Polygon":
        raise ValueError("boundary must be a GeoJSON Polygon")
    rings = value.get("coordinates")
    if not isinstance(rings, list) or not rings or not all(isinstance(r, list) for r in rings):
        raise ValueError("Polygon coordinates must be a non-empty list of linear rings")
    for which, ring in enumerate(rings):
        label = "outer ring" if which == 0 else f"hole {which}"
        if len(ring) < 4:
            raise ValueError(f"{label} needs at least 4 positions (3 unique corners + closing point)")
        if ring[0] != ring[-1]:
            raise ValueError(f"{label} is not closed — first and last position must match exactly")
        unique = set()
        for pos in ring:
            if not (isinstance(pos, (list, tuple)) and len(pos) == 2 and all(isinstance(n, (int, float)) for n in pos)):
                raise ValueError(f"{label} positions must be [longitude, latitude] number pairs")
            lon, lat = pos
            if not -180 <= lon <= 180 or not -90 <= lat <= 90:
                raise ValueError(f"{label} position [{lon}, {lat}] is outside valid lon/lat ranges")
            unique.add((lon, lat))
        if which == 0 and len(unique) < 3:
            raise ValueError("outer ring needs at least 3 distinct corners")
    return value


# ── exports (simulation-labelled in filename + body) ───────────────────────────


def zones_geojson_export(zones: list[models.InterventionZone]) -> dict[str, Any]:
    """GeoJSON FeatureCollection. Foreign member `simulation` + per-feature labels:
    the file can never be mistaken for field-validated geo data."""
    features = []
    for zone in zones:
        payload = zone_payload(zone)
        features.append(
            {
                "type": "Feature",
                "id": zone.id,
                "geometry": zone.zone_geojson,
                "properties": {
                    "zone_id": zone.id,
                    "analysis_id": zone.analysis_id,
                    "field_id": payload["field_id"],
                    "condition": zone.condition,
                    "confidence": zone.confidence,
                    "risk_level": zone.risk_level,
                    "review_priority": payload["review_priority"],
                    "review_status": zone.review_status,
                    "coordinate_space": zone.zone_geojson.get("coordinate_space"),
                    "georeference_source": GEOREFERENCE_NONE,
                    "est_area_ha": zone.est_area_ha,
                    "area_note": payload["area_note"],
                    "simulation": SIMULATION_LABEL,
                },
            }
        )
    return {
        "type": "FeatureCollection",
        "simulation": f"{SIMULATION_LABEL} — decision support pending human review; locations are evidence-space, not verified field positions",
        "generated_at": datetime.now(UTC).isoformat(),
        "zone_count": len(features),
        "features": features,
    }


_CSV_HEADER = [
    "zone_id",
    "analysis_id",
    "field_id",
    "condition",
    "confidence",
    "risk_level",
    "review_priority",
    "review_status",
    "coordinate_space",
    "georeference_source",
    "est_area_ha",
    "area_note",
    "simulation_label",
    "created_at",
]


def zones_csv_export(zones: list[models.InterventionZone]) -> str:
    buffer = io.StringIO()
    buffer.write(f"# {SIMULATION_LABEL} — decision support pending human review; not verified field positions\n")
    writer = csv.writer(buffer)
    writer.writerow(_CSV_HEADER)
    for zone in zones:
        payload = zone_payload(zone)
        writer.writerow(
            [
                zone.id,
                zone.analysis_id,
                payload["field_id"] or "",
                zone.condition,
                f"{zone.confidence:.4f}",
                zone.risk_level,
                payload["review_priority"],
                zone.review_status,
                zone.zone_geojson.get("coordinate_space"),
                GEOREFERENCE_NONE,
                "" if zone.est_area_ha is None else zone.est_area_ha,
                payload["area_note"] or "",
                SIMULATION_LABEL,
                payload["created_at"] or "",
            ]
        )
    return buffer.getvalue()
