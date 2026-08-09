"""PDF field reports (Phase 9, FR-19).

Pins the honesty contract end to end: Suspected phrasing + every spec field
lands on the printed page (asserted via the deterministic text basis — files
win), INCONCLUSIVE renders as an honest abstention with no zones, demo runs get
a banner, regeneration keeps the human report_id, and generation is audited.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

from app.services import reporting
from app.workers.analysis_worker import tick
from tests.test_analysis_flow import StubPredictor, _contract, _handle, _upload

REPORT_ID_RE = re.compile(r"^CMA-\d{8}-[0-9A-F]{6}$")


def _completed(client, tmp_path, **contract_overrides) -> str:
    image_id = _upload(client)
    analysis_id = client.post("/analyses", json={"image_id": image_id}).json()["analysis_id"]
    stub = StubPredictor(_contract(**contract_overrides))
    assert tick("report-worker", handle=_handle(stub, tmp_path)) == 1
    return analysis_id


def _with_zones(client, analysis_id: str) -> dict:
    resp = client.post(f"/analyses/{analysis_id}/intervention-zones")
    assert resp.status_code == 201, resp.text
    return resp.json()


def _generate_report(client, analysis_id: str) -> dict:
    resp = client.post(f"/analyses/{analysis_id}/report")
    assert resp.status_code == 201, resp.text
    return resp.json()["report"]


def _report_text(report_row, basis: dict) -> list[str]:
    return reporting._report_lines(report_row, basis)


# ── generation gates ───────────────────────────────────────────────────────────


def test_report_requires_completed_prediction(client) -> None:
    image_id = _upload(client)
    analysis_id = client.post("/analyses", json={"image_id": image_id}).json()["analysis_id"]
    resp = client.post(f"/analyses/{analysis_id}/report")
    assert resp.status_code == 409
    detail = resp.json()["detail"]
    assert detail["analysis_status"] == "QUEUED"
    assert detail["poll"] == f"/analyses/{analysis_id}"
    assert client.post("/analyses/nope/report").status_code == 404


def test_suspected_report_requires_zones_first(client, tmp_path) -> None:
    analysis_id = _completed(client, tmp_path)  # SUSPECTED HIGH contract
    resp = client.post(f"/analyses/{analysis_id}/report")
    assert resp.status_code == 409
    assert "generate" in resp.json()["detail"]["detail"].lower()
    assert "zones" in resp.json()["detail"]["detail"].lower()

    state = client.get(f"/analyses/{analysis_id}/report").json()
    assert state["status"] == "GENERATE"
    assert state["report"] is None
    assert "zones" in state["why"]


def test_report_id_format_is_human_readable() -> None:
    report_id = reporting.new_report_id(datetime(2026, 8, 9, tzinfo=UTC))
    assert REPORT_ID_RE.match(report_id)
    assert report_id.startswith("CMA-20260809-")


# ── generation + content ───────────────────────────────────────────────────────


def test_generate_report_happy_path_contains_all_spec_fields(client, tmp_path, db_session_factory) -> None:
    analysis_id = _completed(client, tmp_path)
    zones_body = _with_zones(client, analysis_id)
    report = _generate_report(client, analysis_id)

    assert REPORT_ID_RE.match(report["report_id"])
    assert report["demo"] is True  # stub demo handle — never silent
    assert report["generator"]["name"] == "reportlab"
    assert report["download_url"] == f"/reports/{report['id']}/download"

    basis = report["basis"]
    # FR-19 fields verbatim from stored state
    assert basis["prediction"]["phrasing"] == "Suspected corn - Northern Leaf Blight - 92% confidence"
    assert basis["prediction"]["status"] == "SUSPECTED"
    assert basis["field"] is None  # analysis had no field link — stated, not invented
    assert basis["model"]["name"] and basis["model"]["version"]
    assert basis["zones"][0]["review_status"] == "PENDING"
    assert basis["zone_review_totals"] == {"PENDING": len(zones_body["zones"]), "APPROVED": 0, "REJECTED": 0}

    # the persisted row points at a real artifact
    with db_session_factory() as db:
        from app.db import models

        row = db.get(models.Report, report["id"])
        assert row is not None
        assert row.analysis_id == analysis_id
        assert row.pdf_path == f"reports/cropmind-report-{row.report_id}.pdf"
        assert reporting.read_report_file(row) is not None


def test_pdf_text_layout_carries_honesty_strings(client, tmp_path, db_session_factory) -> None:
    analysis_id = _completed(client, tmp_path)
    _with_zones(client, analysis_id)
    report = _generate_report(client, analysis_id)

    with db_session_factory() as db:
        from app.db import models

        row = db.get(models.Report, report["id"])
        analysis = row.analysis
        lines = _report_text(row, reporting.report_basis(analysis, analysis.prediction, analysis.intervention_zones))
        text = "\n".join(lines)

        # every spec field + honesty element is on the printed page
        assert f"Report ID: {row.report_id}" in text
        assert "Farm:" not in text and "not specified" in text  # no field link — said so
        assert "Suspected corn - Northern Leaf Blight - 92% confidence" in text
        assert "Confidence:" in text and "band HIGH" in text
        assert "Estimated visual severity" in text and "visual proxy" in text
        assert "image-normalized-xyxy" in text
        assert "georeference: none" in text
        assert "NO product, chemical or dosage guidance" in text
        assert "PENDING" in text and "awaiting review" in text
        assert "DEMO REPORT" in text  # stub analysis is demo — bold banner
        assert "HIGH >= 0.60" in text and "abstain" in text
        assert "decision support" in text.lower()
        assert "not a definitive diagnosis" in text

        # the artifact itself: real PDF bytes under upload_dir
        target = reporting.read_report_file(row)
        assert target is not None and target.name == f"cropmind-report-{row.report_id}.pdf"
        assert target.read_bytes()[:5] == b"%PDF-"


def test_inconclusive_report_abstains_honestly(client, tmp_path, db_session_factory) -> None:
    analysis_id = _completed(
        client,
        tmp_path,
        status="INCONCLUSIVE",
        phrasing="INCONCLUSIVE — below confidence threshold",
        confidence=0.0924,
        confidence_band=None,
        crop="unknown",
        condition={"disease_id": "unknown", "name": "Inconclusive"},
    )
    report = _generate_report(client, analysis_id)  # no zones needed — abstention by design
    assert report["basis"]["zones"] == []
    assert report["basis"]["prediction"]["status"] == "INCONCLUSIVE"

    with db_session_factory() as db:
        from app.db import models

        row = db.get(models.Report, report["id"])
        analysis = row.analysis
        text = "\n".join(_report_text(row, reporting.report_basis(analysis, analysis.prediction, [])))
        assert "ABSTAINED" in text
        assert "below the LOW band" in text
        assert "abstention by design" in text
        assert "retake the photo" in text
        assert "No zones" in text


def test_reviewed_zones_appear_with_notes(client, tmp_path, db_session_factory) -> None:
    analysis_id = _completed(client, tmp_path)
    zones_body = _with_zones(client, analysis_id)
    zone_id = zones_body["zones"][0]["id"]
    resp = client.patch(f"/intervention-zones/{zone_id}", json={"review_status": "APPROVED", "review_note": "scout first"})
    assert resp.status_code == 200, resp.text

    report = _generate_report(client, analysis_id)
    assert report["basis"]["zone_review_totals"] == {"PENDING": 0, "APPROVED": 1, "REJECTED": 0}

    with db_session_factory() as db:
        from app.db import models

        row = db.get(models.Report, report["id"])
        analysis = row.analysis
        text = "\n".join(_report_text(row, reporting.report_basis(analysis, analysis.prediction, analysis.intervention_zones)))
        assert "human review: APPROVED" in text
        assert "scout first" in text
        assert "approved 1" in text


# ── regeneration + retrieval ───────────────────────────────────────────────────


def test_regeneration_keeps_report_id_and_refreshes(client, tmp_path, db_session_factory) -> None:
    analysis_id = _completed(client, tmp_path)
    zones_body = _with_zones(client, analysis_id)
    first = _generate_report(client, analysis_id)

    zone_id = zones_body["zones"][0]["id"]
    client.patch(f"/intervention-zones/{zone_id}", json={"review_status": "REJECTED", "review_note": "not on this leaf"})

    second = _generate_report(client, analysis_id)
    assert second["id"] == first["id"]  # one report per analysis
    assert second["report_id"] == first["report_id"]  # human ID stable
    assert second["basis"]["zone_review_totals"]["REJECTED"] == 1  # refreshed basis

    with db_session_factory() as db:
        from app.db import models

        rows = db.query(models.Report).all()
        assert len(rows) == 1  # regeneration never forks a second row


def test_get_report_by_id_and_analysis_report_ready(client, tmp_path) -> None:
    analysis_id = _completed(client, tmp_path)
    _with_zones(client, analysis_id)
    report = _generate_report(client, analysis_id)

    fetched = client.get(f"/reports/{report['id']}").json()["report"]
    assert fetched["report_id"] == report["report_id"]
    assert fetched["basis"]["prediction"]["phrasing"].startswith("Suspected")

    state = client.get(f"/analyses/{analysis_id}/report").json()
    assert state["status"] == "READY"
    assert state["report"]["id"] == report["id"]

    assert client.get("/reports/nope").status_code == 404
    assert client.get("/reports/nope/download").status_code == 404
    assert client.get("/analyses/nope/report").status_code == 404


def test_download_serves_pdf_with_report_id_filename(client, tmp_path) -> None:
    analysis_id = _completed(client, tmp_path)
    _with_zones(client, analysis_id)
    report = _generate_report(client, analysis_id)

    resp = client.get(report["download_url"])
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content[:5] == b"%PDF-"
    disposition = resp.headers["content-disposition"]
    assert disposition.endswith(f'filename="cropmind-field-report-{report["report_id"]}.pdf"')


def test_list_reports_summaries(client, tmp_path) -> None:
    analysis_id = _completed(client, tmp_path)
    _with_zones(client, analysis_id)
    report = _generate_report(client, analysis_id)

    listing = client.get("/reports").json()
    assert listing["count"] == 1 and listing["total"] == 1
    summary = listing["reports"][0]
    assert summary["report_id"] == report["report_id"]
    assert "basis" not in summary  # summaries stay light
    facts = summary["key_facts"]
    assert facts["prediction_status"] == "SUSPECTED"
    assert facts["zones_total"] == 1
    assert facts["zone_review_totals"] == {"PENDING": 1, "APPROVED": 0, "REJECTED": 0}
    assert "files win" in listing["note"]


def test_report_generation_is_audited(client, tmp_path, db_session_factory) -> None:
    analysis_id = _completed(client, tmp_path)
    _with_zones(client, analysis_id)
    report = _generate_report(client, analysis_id)

    with db_session_factory() as db:
        from sqlalchemy import select

        from app.db import models

        actions = db.execute(
            select(models.AuditLog.action).where(models.AuditLog.entity == "report", models.AuditLog.entity_id == report["id"])
        ).scalars().all()
    assert actions == ["REPORT_GENERATED"]
