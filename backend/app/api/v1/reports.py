"""Reports API (Phase 9, FR-19): audit-ready PDF field reports.

A report is the honest written record of one analysis: Suspected-phrasing
verbatim, review ledger included, INCONCLUSIVE rendered as abstention, demo
runs bannered. Generation is explicit (user-driven), audited, and idempotent —
one report row per analysis, regeneration keeps the human report_id and
overwrites the same file (files win; no stale copies survive silently).
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse
from sqlalchemy import func, select

from app.core.logging import request_id_ctx
from app.db import models
from app.db.session import DbSession
from app.services import reporting

router = APIRouter(tags=["reports"])


def _get_analysis_or_404(db, analysis_id: str) -> models.Analysis:
    analysis = db.get(models.Analysis, analysis_id)
    if analysis is None:
        raise HTTPException(404, "analysis not found")
    return analysis


def _get_report_or_404(db, report_id: str) -> models.Report:
    report = db.get(models.Report, report_id)
    if report is None:
        raise HTTPException(404, "report not found")
    return report


@router.post("/analyses/{analysis_id}/report", status_code=201)
def create_or_regenerate_report(analysis_id: str, db: DbSession, request: Request) -> dict:
    """Generate (or regenerate) the PDF field report for an analysis.

    404 unknown analysis; 409 via ReportNotReady when the prediction is not
    complete, or when a SUSPECTED analysis has no intervention zones yet (the
    report must carry the full review ledger — generate zones on the Map page
    first; INCONCLUSIVE analyses legitimately have none).
    """
    analysis = _get_analysis_or_404(db, analysis_id)
    try:
        report = reporting.generate_report(db, analysis)
    except reporting.ReportNotReady as exc:
        raise HTTPException(409, exc.detail) from exc

    db.add(
        models.AuditLog(
            user_id=None,
            action="REPORT_GENERATED",
            entity="report",
            entity_id=report.id,
            ip=request.client.host if request.client else None,
            request_id=request_id_ctx.get(),
        )
    )
    db.flush()
    return {
        "report": reporting.report_payload(report, analysis),
        "note": "201 — the PDF file is the artifact of record; download via download_url",
    }


@router.get("/analyses/{analysis_id}/report")
def get_analysis_report(analysis_id: str, db: DbSession) -> dict:
    """Report state for one analysis (the analysis-view sidebar flow).

    Always 200 for a known analysis: {"status": "READY", "report": {...}} or
    {"status": "GENERATE", "report": null, "why": ...} — the UI renders a
    Generate button instead of forcing the user through a 404.
    """
    analysis = _get_analysis_or_404(db, analysis_id)
    report = analysis.report
    if report is None:
        why = "no report generated yet"
        if analysis.status != "COMPLETED" or analysis.prediction is None:
            why = f"analysis is {analysis.status} — a report needs a completed prediction"
        elif analysis.prediction.status == "SUSPECTED" and not (analysis.intervention_zones or []):
            why = "generate intervention zones first (Map page → Generate zones) — the report carries the review ledger"
        return {"status": "GENERATE", "report": None, "why": why}
    return {"status": "READY", "report": reporting.report_payload(report, analysis), "why": None}


@router.get("/reports")
def list_reports(
    db: DbSession,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = 0,
) -> dict:
    """History surface (Phase 9 UI): newest-first summaries with key facts."""
    total = db.execute(select(func.count()).select_from(models.Report)).scalar_one()
    rows = (
        db.execute(select(models.Report).order_by(models.Report.generated_at.desc(), models.Report.id.desc()).limit(limit).offset(offset))
        .scalars()
        .all()
    )
    return {
        "count": len(rows),
        "total": total,
        "reports": [reporting.report_payload(report, report.analysis, summary=True) for report in rows],
        "note": "each row summarises a stored PDF artifact; regeneration keeps the human report_id stable (files win)",
    }


@router.get("/reports/{report_id}")
def get_report(report_id: str, db: DbSession) -> dict:
    report = _get_report_or_404(db, report_id)
    return {"report": reporting.report_payload(report, report.analysis)}


@router.get("/reports/{report_id}/download")
def download_report(report_id: str, db: DbSession) -> FileResponse:
    """The PDF artifact itself — Content-Disposition filename carries the human ID."""
    report = _get_report_or_404(db, report_id)
    target = reporting.read_report_file(report)
    if target is None:
        raise HTTPException(
            409,
            {
                "detail": "stored PDF missing on disk — regenerate it (POST /analyses/{id}/report)",
                "analysis_id": report.analysis_id,
            },
        )
    return FileResponse(
        target,
        media_type="application/pdf",
        filename=f"cropmind-field-report-{report.report_id}.pdf",
    )
