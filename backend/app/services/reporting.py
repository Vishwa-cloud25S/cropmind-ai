"""PDF field reports (Phase 9, FR-19, docs/04 §3.9).

Honesty rules enforced here (this is a document a user may print and act on):

  * The PDF states *suspected* findings only — the prediction phrasing
    ("Suspected {crop} - {condition} - {x}% confidence") is carried verbatim;
    a report never upgrades a suspicion to a diagnosis.
  * INCONCLUSIVE reports say the system abstained and why (below the LOW
    confidence band), with retake guidance — never a dressed-up guess.
  * Zone sections are review ledgers, not prescriptions: geometry is labelled
    image-space (`image-normalized-xyxy`, georeference "none"), no areas in
    hectares, no product / chemical / dosage content anywhere.
  * Human review status is printed per zone and in totals (PENDING /
    APPROVED / REJECTED) — a report can never make an unreviewed zone look
    endorsed.
  * Demo predictions (sample model) carry a bold DEMO banner; limitations and
    confidence bands are always printed (docs/06 model card).
  * "Files win": the persisted Report row's pdf_path is the artifact of
    record; regeneration refreshes the same row (human report_id stable) and
    overwrites the same file so no stale copy survives silently.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db import models

REPORT_PREFIX = "CMA"
REPORTS_SUBDIR = "reports"  # inside upload_dir
GENERATOR = {"name": "reportlab", "feature": "field-report", "version": "1"}  # bump on layout change

# Shared-band text mirrors ml/configs/model.yaml (the live values also served by
# /supported-crops); printed verbatim so a paper reader knows the abstain rule.
BAND_TEXT = "HIGH >= 0.60 | MEDIUM >= 0.45 | LOW >= 0.25 | below LOW = INCONCLUSIVE (abstain)"


class ReportNotReady(Exception):
    """409-condition with a structured API detail (matches prediction-not-ready shape)."""

    def __init__(self, detail: dict[str, Any]):
        super().__init__(detail.get("detail", "report not ready"))
        self.detail = detail


def new_report_id(now: datetime | None = None) -> str:
    """Human-facing report ID: CMA-YYYYMMDD-XXXXXX (6 uppercase hex chars).

    One report row per analysis makes collisions a non-issue in practice; the
    unique constraint stands as the DB-level guard.
    """
    stamp = (now or datetime.now(UTC)).strftime("%Y%m%d")
    return f"{REPORT_PREFIX}-{stamp}-{uuid.uuid4().hex[:6].upper()}"


def generate_report(db: Session, analysis: models.Analysis) -> models.Report:
    """Create (or regenerate) the PDF field report for an analysis.

    One report per analysis (unique analysis_id): regeneration keeps the human
    report_id and overwrites the same file with a fresh build-basis snapshot.

    Rejects (ReportNotReady → 409) when the prediction is not complete, or when
    a SUSPECTED analysis has no intervention zones yet — a report must carry the
    full zone review ledger, so the user is told to generate zones first.
    INCONCLUSIVE analyses legitimately have zero zones (abstention by design).
    """
    if analysis.status != "COMPLETED" or analysis.prediction is None:
        raise ReportNotReady(
            {
                "detail": "report not ready — analysis has no completed prediction",
                "analysis_status": analysis.status,
                "poll": f"/analyses/{analysis.id}",
            }
        )
    prediction = analysis.prediction
    zones = sorted(analysis.intervention_zones or [], key=lambda z: (z.created_at, z.id))
    if prediction.status == "SUSPECTED" and not zones:
        raise ReportNotReady(
            {
                "detail": "no intervention zones yet — generate them first (Map page → Generate zones); "
                "a field report must carry the full zone review ledger",
                "hint": f"POST /analyses/{analysis.id}/intervention-zones",
            }
        )

    report = analysis.report
    if report is None:
        report = models.Report(analysis_id=analysis.id, report_id=new_report_id(), pdf_path="")
        db.add(report)
        db.flush()
        report.pdf_path = f"{REPORTS_SUBDIR}/cropmind-report-{report.report_id}.pdf"
        db.flush()

    basis = report_basis(analysis, prediction, zones)
    target = Path(get_settings().upload_dir) / report.pdf_path
    target.parent.mkdir(parents=True, exist_ok=True)
    build_field_report_pdf(target, basis, report)

    report.generated_at = datetime.now(UTC)  # explicit refresh: regeneration is visible, never silent
    db.flush()
    return report


def report_basis(
    analysis: models.Analysis,
    prediction: models.Prediction,
    zones: Sequence[models.InterventionZone],
) -> dict[str, Any]:
    """Assemble every fact printed on the PDF — stored state only, never re-derived.

    Field identity comes from the analysis's own field link first, then the
    image's; either way it is resolved via the relationship graph the session
    already loaded — nothing is invented when there is no link (printed as
    "not specified").
    """
    image = analysis.image
    field = _analysis_field(analysis, image)
    farm = field.farm if field is not None else None
    model_version = prediction.model_version
    raw = prediction.raw_json or {}

    review_totals = {"PENDING": 0, "APPROVED": 0, "REJECTED": 0}
    for zone in zones:
        review_totals[zone.review_status] = review_totals.get(zone.review_status, 0) + 1

    return {
        "analysis_id": analysis.id,
        "analysis_status": analysis.status,
        "demo": bool(analysis.demo or prediction.demo or (model_version.demo if model_version else False)),
        "generated_at_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "prediction": {
            "phrasing": prediction.phrasing,
            "status": prediction.status,
            "crop": prediction.crop,
            "condition": prediction.condition,
            "condition_name": prediction.condition_name,
            "confidence": prediction.confidence,
            "band": prediction.band,
            "uncertainty": prediction.uncertainty,
            "severity": prediction.severity,
            "severity_label": raw.get("severity_label", "Estimated visual severity"),
            "latency_ms": prediction.latency_ms,
            "limitation_notice": raw.get("limitation_notice", "Decision support only - not a definitive diagnosis."),
            "explainability_caveat": raw.get(
                "explainability_caveat", "Highlighted regions contribute strongly; not a disease-location guarantee."
            ),
        },
        "model": {
            "name": model_version.name if model_version else "unknown",
            "version": model_version.version if model_version else "unknown",
            "dataset_version": model_version.dataset_version if model_version else None,
            "demo": bool(model_version.demo) if model_version else None,
        },
        "image": {
            "id": image.id,
            "captured_at": image.captured_at.isoformat() if image.captured_at else None,
            "width": image.width,
            "height": image.height,
            "source_type": image.source_type,
            "sha256_12": (image.sha256 or "")[:12],
        },
        "field": (
            {"farm": farm.name if farm else None, "name": field.name, "crop_id": field.crop_id, "area_ha": field.area_ha}
            if field is not None
            else None
        ),
        "zones": [
            {
                "id": zone.id,
                "risk_level": zone.risk_level,
                "condition": zone.condition,
                "confidence": zone.confidence,
                "severity": zone.severity,
                "review_status": zone.review_status,
                "review_note": zone.review_note,
                "reviewed_at": zone.reviewed_at.isoformat() if zone.reviewed_at else None,
                "coordinate_space": (zone.zone_geojson or {}).get("coordinate_space", "image-normalized-xyxy"),
                "georeference_source": (zone.zone_geojson or {}).get("georeference_source", "none"),
            }
            for zone in zones
        ],
        "zone_review_totals": review_totals,
    }


def _analysis_field(analysis: models.Analysis, image: models.Image | None) -> models.Field | None:
    """Resolve the report's field: analysis link wins, else the image's, else None.

    Uses SQLAlchemy's identity map / attribute loading on the live session —
    the session is always available because callers operate inside a request.
    """
    state = sa_inspect(analysis)
    session = state.session
    if analysis.field_id and session is not None:
        field = session.get(models.Field, analysis.field_id)
        if field is not None:
            return field
    if image is not None and image.field is not None:
        return image.field
    return None


def report_payload(report: models.Report, analysis: models.Analysis, *, summary: bool = False) -> dict[str, Any]:
    """API payload. The full variant embeds the PDF's build basis (what the file says)."""
    prediction = analysis.prediction
    zones = sorted(analysis.intervention_zones or [], key=lambda z: (z.created_at, z.id))
    base = {
        "id": report.id,
        "report_id": report.report_id,
        "analysis_id": analysis.id,
        "generated_at": report.generated_at.isoformat() if report.generated_at else None,
        "demo": bool(analysis.demo or (prediction.demo if prediction else False)),
        "generator": dict(GENERATOR),
        "download_url": f"/reports/{report.id}/download",
        "hint": "the PDF file is the artifact of record (files win); this payload is a snapshot of its build basis",
    }
    if summary:
        base["key_facts"] = {
            "analysis_status": analysis.status,
            "prediction_status": prediction.status if prediction else None,
            "prediction_phrasing": prediction.phrasing if prediction else None,
            "zones_total": len(zones),
            "zone_review_totals": {
                status: sum(1 for zone in zones if zone.review_status == status)
                for status in ("PENDING", "APPROVED", "REJECTED")
            },
        }
    else:
        base["basis"] = report_basis(analysis, prediction, zones) if prediction is not None else None
    return base


# ── PDF rendering (ReportLab, deterministic layout) ────────────────────────────


def _kv(label: str, value: Any) -> str:
    return f"{label:<34} {value}"


def _report_lines(report: models.Report, basis: dict[str, Any]) -> list[str]:
    """Text layout of the field report.

    Every section maps 1:1 to an FR-19 spec field, and every honesty string
    printed here is asserted by tests so a future edit cannot quietly drop one.
    """
    prediction = basis["prediction"]
    model = basis["model"]
    image = basis["image"]
    field = basis["field"]
    zones = basis["zones"]
    totals = basis["zone_review_totals"]

    lines: list[str] = []
    lines.append("CROPMIND AI — FIELD REPORT")
    if basis["demo"]:
        lines.append(
            "**DEMO REPORT — produced by the clearly-flagged synthetic sample model; "
            "NOT a real finding. Do not act on this document.**"
        )
    lines.append("—")
    lines.append(f"Report ID: {report.report_id}")
    lines.append(_kv("Generated at (UTC):", basis["generated_at_utc"]))
    lines.append(_kv("Analysis ID:", basis["analysis_id"]))
    lines.append("")

    # 1. Identification — crop / field / image / date (FR-19)
    lines.append("1. IDENTIFICATION")
    lines.append("—")
    if field is not None:
        lines.append(_kv("Farm:", field["farm"] or "—"))
        lines.append(_kv("Field:", field["name"]))
        lines.append(_kv("Declared crop (field record):", field["crop_id"] or "not set"))
        if field["area_ha"] is not None:
            lines.append(_kv("Field area (drawn boundary):", f"{field['area_ha']} ha"))
    else:
        lines.append("Field: not specified — this image was analysed without a field link.")
    lines.append(_kv("Image ID:", image["id"]))
    lines.append(_kv("Image captured at:", image["captured_at"] or "camera timestamp unavailable"))
    lines.append(_kv("Image size:", f"{image['width']} x {image['height']} px ({image['source_type']})"))
    lines.append(_kv("Image checksum (SHA-256):", f"{image['sha256_12']}… (integrity-verifiable)"))
    lines.append("")

    # 2. Suspected finding — condition + confidence, phrasing verbatim
    lines.append("2. SUSPECTED FINDING (decision support — not a diagnosis)")
    lines.append("—")
    lines.append(f"  {prediction['phrasing']}")
    if prediction["status"] == "INCONCLUSIVE":
        lines.append("  The system ABSTAINED: best-guess confidence fell below the LOW band on this evidence.")
        lines.append("  Action: retake the photo (focus, lighting, single leaf) or consult an agronomist.")
        lines.append("  No condition is claimed and no intervention zones exist (abstention by design).")
    else:
        lines.append(_kv("Status:", prediction["status"]))
        lines.append(_kv("Crop (predicted):", prediction["crop"]))
        lines.append(_kv("Suspected condition:", f"{prediction['condition_name']} ({prediction['condition']})"))
        lines.append(_kv("Confidence:", f"{prediction['confidence']:.1%} (band {prediction['band']})"))
        lines.append(_kv("Uncertainty (norm. entropy):", f"{prediction['uncertainty']:.3f}"))
        if prediction["severity"] is not None:
            lines.append(
                _kv(
                    f"{prediction['severity_label']}:",
                    f"{prediction['severity']:.1%} of the leaf area appears affected (visual proxy, not a measurement)",
                )
            )
        lines.append(_kv("Inference latency:", f"{prediction['latency_ms']:.0f} ms"))
    lines.append(f"  Limitation: {prediction['limitation_notice']}")
    lines.append(f"  Explainability caveat: {prediction['explainability_caveat']}")
    lines.append("")

    # 3. Intervention zones + human review status (FR-19)
    lines.append("3. INTERVENTION ZONES — SIMULATION PENDING HUMAN REVIEW")
    lines.append("—")
    lines.append("  Precision intervention zone simulation — zones are IMAGE-SPACE regions")
    lines.append("  (coordinate space: image-normalized-xyxy, georeference: none). They are")
    lines.append("  not mapped to hectares and carry NO product, chemical or dosage guidance.")
    if not zones:
        lines.append("  No zones on this report — see Section 2 (abstention or none requested).")
    else:
        lines.append(
            "  Human review totals: "
            + ", ".join(f"{status.lower()} {totals.get(status, 0)}" for status in ("PENDING", "APPROVED", "REJECTED"))
        )
        for index, zone in enumerate(zones, start=1):
            severity_txt = f"{zone['severity']:.1%}" if zone["severity"] is not None else "n/a"
            lines.append(
                f"  Zone {index}: risk {zone['risk_level']} | confidence {zone['confidence']:.1%} | "
                f"visual severity {severity_txt}"
            )
            review_line = f"    human review: {zone['review_status']}"
            review_line += f" (at {zone['reviewed_at']})" if zone["reviewed_at"] else " — awaiting review"
            lines.append(review_line)
            if zone["review_note"]:
                lines.append(f"    reviewer note: {_clip(zone['review_note'], 90)}")
        lines.append("  Status legend: PENDING = not yet reviewed; APPROVED/REJECTED = human decision recorded.")
    lines.append("")

    # 4. Model version + limitations (FR-19; docs/06 truths)
    lines.append("4. MODEL & LIMITATIONS")
    lines.append("—")
    lines.append(_kv("Model:", f"{model['name']} v{model['version']}"))
    lines.append(_kv("Dataset version:", model["dataset_version"] or "not recorded"))
    if model.get("demo") is not None:
        lines.append(_kv("Sample (demo) weights:", "yes — synthetic patterns only" if model["demo"] else "no"))
    lines.append(f"  Confidence bands: {BAND_TEXT}")
    lines.append("  Measured performance (test split AND out-of-distribution) is published in the")
    lines.append("  model card (docs/06); this document never quotes a number the card does not.")
    lines.append("")

    # 5. Human review & accountability
    lines.append("5. HUMAN REVIEW & ACCOUNTABILITY")
    lines.append("—")
    lines.append(f"  Zones awaiting human review: {totals.get('PENDING', 0)} of {len(zones)}")
    lines.append("  CropMind AI provides decision support only; final decisions stay with the")
    lines.append("  farmer/agronomist. This document contains no pesticide, product or dosage")
    lines.append("  advice. Verify any suspected finding with a qualified person before acting.")
    lines.append("")
    lines.append("—")
    lines.append(
        f"Generated by CropMind AI ({GENERATOR['name']} {GENERATOR['feature']} v{GENERATOR['version']}) | "
        f"Report {report.report_id} | files win: this PDF is the artifact of record"
    )
    return lines


def _clip(text: str, width: int) -> str:
    return text if len(text) <= width else text[: width - 1] + "…"


def build_field_report_pdf(target: Path, basis: dict[str, Any], report: models.Report) -> None:
    """Render the basis to an A4 PDF via ReportLab (plain, accessible layout)."""
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    lines = _report_lines(report, basis)
    page_width, page_height = A4
    margin, leading = 40, 13
    max_chars = 118  # 9-10pt Helvetica fits ~118 chars within the A4 margins
    pdf = canvas.Canvas(str(target), pagesize=A4)
    pdf.setTitle(f"CropMind AI field report {report.report_id}")
    pdf.setAuthor("CropMind AI (decision support)")
    pdf.setSubject("Suspected crop condition — decision support report (Review status included)")

    y = page_height - margin
    for raw_line in lines:
        if raw_line == "—":
            pdf.setStrokeGray(0.6)
            pdf.line(margin, y + 4, page_width - margin, y + 4)
            y -= leading
            continue
        line = raw_line
        if line.startswith("**"):  # DEMO banner — forced bold
            pdf.setFont("Helvetica-Bold", 10)
            line = line.strip("* ")
        elif line.startswith("CROPMIND AI —"):
            pdf.setFont("Helvetica-Bold", 13)  # document title
        elif line and line[0].isdigit() and ". " in line[:4]:
            pdf.setFont("Helvetica-Bold", 11)  # numbered section headers
        else:
            pdf.setFont("Helvetica", 9)
        for piece in _wrap(line, max_chars):
            if y < margin:
                pdf.showPage()
                y = page_height - margin
            pdf.drawString(margin, y, piece)
            y -= leading
    pdf.save()


def _wrap(line: str, width: int) -> list[str]:
    """Whitespace wrap so no printed line is ever clipped (files win verbatim)."""
    pieces: list[str] = []
    rest = line
    while len(rest) > width:
        cut = rest.rfind(" ", 0, width + 1)
        if cut <= 0:
            cut = width
        pieces.append(rest[:cut].rstrip())
        rest = rest[cut:].lstrip()
    pieces.append(rest)
    return pieces


def read_report_file(report: models.Report) -> Path | None:
    """Locate the stored PDF under upload_dir (None if the file vanished)."""
    target = Path(get_settings().upload_dir) / report.pdf_path
    return target if target.is_file() else None
