"""Phase 11 — the one unbroken critical flow, asserted end to end in CI.

register → login → farm → field (boundary + crop) → upload (field-scoped) →
analysis → worker tick → prediction → zones → human review → zone export →
report generate → report download → feedback → logout revocation.

Plus the regression pins for the two honesty rules this flow depends on:
  * owner-scoped artifacts answer 404 to a *different* account and to anonymous
    callers (the 2026-08-11 bare-link bug proved this must be tested, not assumed);
  * a revoked token is dead immediately (server-side denylist, not wishful TTL).

The worker never loads torch: a stub predictor returns the exact shipped
Predictor contract (see tests/test_analysis_flow.py), so this asserts the
HTTP/DB/honesty pipeline, not model quality (model quality lives in ml/ tests
and the model card).
"""

from __future__ import annotations

import io
import re

from PIL import Image as PILImage

from app.workers.analysis_worker import tick
from tests.test_analysis_flow import StubPredictor, _contract, _handle

REPORT_ID_RE = re.compile(r"^CMA-\d{8}-[0-9A-F]{6}$")

BOUNDARY = {
    "type": "Polygon",
    "coordinates": [[[-0.70, 51.10], [-0.69, 51.10], [-0.69, 51.11], [-0.70, 51.11], [-0.70, 51.10]]],
}


def _jpeg() -> bytes:
    buf = io.BytesIO()
    PILImage.new("RGB", (96, 72), (24, 150, 60)).save(buf, "JPEG")
    return buf.getvalue()


def test_critical_flow_register_to_report(anon_client, tmp_path) -> None:
    client = anon_client

    # ── 1. register (first account bootstraps ADMIN — stated, not silent) ──
    reg = client.post("/auth/register", json={"email": "grower@e2e.test", "password": "S3cure-pass1"})
    assert reg.status_code == 201, reg.text
    assert "first registered account becomes ADMIN" in reg.json()["role_note"]
    assert reg.json()["user"]["role"] == "ADMIN"

    # second account for the cross-owner visibility pins (a plain FARMER)
    other = client.post("/auth/register", json={"email": "other@e2e.test", "password": "S3cure-pass2"})
    assert other.status_code == 201, other.text
    assert other.json()["user"]["role"] == "FARMER"
    other_token = other.json()["access_token"]

    # ── 2. login → bearer token ──
    login = client.post("/auth/login", json={"email": "grower@e2e.test", "password": "S3cure-pass1"})
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]
    client.headers["Authorization"] = f"Bearer {token}"
    assert client.get("/auth/me").status_code == 200

    # ── 3. farm → 4. field (crop declared) → boundary drawn on the map (PATCH) ──
    farm = client.post("/farms", json={"name": "E2E Farm", "location": "Shropshire"})
    assert farm.status_code == 201, farm.text
    farm_id = farm.json()["farm"]["id"]
    field = client.post(f"/farms/{farm_id}/fields", json={"name": "North 1", "crop_id": "tomato"})
    assert field.status_code == 201, field.text
    field_id = field.json()["field"]["id"]
    bound = client.patch(f"/fields/{field_id}", json={"boundary_geojson": BOUNDARY})
    assert bound.status_code == 200, bound.text
    assert bound.json()["field"]["boundary_geojson"] == BOUNDARY

    # ── 5. field-scoped upload → 6. analysis carries the field link ──
    up = client.post(f"/images?field_id={field_id}", files={"file": ("leaf.jpg", _jpeg(), "image/jpeg")})
    assert up.status_code == 201, up.text
    image_id = up.json()["image"]["id"]
    assert up.json()["image"]["field_id"] == field_id

    created = client.post("/analyses", json={"image_id": image_id})
    assert created.status_code == 202, created.text  # queued asynchronously — never a fake instant result
    analysis_id = created.json()["analysis_id"]

    # never serves a partial prediction
    not_ready = client.get(f"/analyses/{analysis_id}/prediction")
    assert not_ready.status_code == 409

    # ── 7. worker tick (stub predictor, HIGH-band SUSPECTED) ──
    stub = StubPredictor(_contract())
    assert tick("e2e-worker", handle=_handle(stub, tmp_path, demo=False)) == 1
    assert stub.calls == 1

    pred = client.get(f"/analyses/{analysis_id}/prediction")
    assert pred.status_code == 200, pred.text
    payload = pred.json()
    assert payload["phrasing"] == "Suspected corn - Northern Leaf Blight - 92% confidence"
    assert payload["status"] == "SUSPECTED"
    assert payload["band"] == "HIGH"
    assert payload["demo"] is False  # authenticated, non-demo run

    # ── 8. intervention zones (SUSPECTED ⇒ zones by design) ──
    zones = client.post(f"/analyses/{analysis_id}/intervention-zones")
    assert zones.status_code == 201, zones.text
    zone_list = zones.json()["zones"]
    assert len(zone_list) >= 1
    zone_id = zone_list[0]["id"]
    assert zone_list[0]["review_status"] == "PENDING"

    # ── 9. human review (audited APPROVE) ──
    review = client.patch(
        f"/intervention-zones/{zone_id}",
        json={"review_status": "APPROVED", "review_note": "matches field walk"},
    )
    assert review.status_code == 200, review.text

    # ── 10. zone export carries the SIMULATION label and real rows ──
    export = client.get("/intervention-zones/export", params={"field_id": field_id, "format": "csv"})
    assert export.status_code == 200, export.text
    disposition = export.headers.get("content-disposition", "")
    assert "cropmind-zone-simulation" in disposition
    body_text = export.text
    assert "precision intervention zone simulation" in body_text
    assert zone_id in body_text and "APPROVED" in body_text

    # ── 11. report generation (zones+review ledger first — by design) ──
    report = client.post(f"/analyses/{analysis_id}/report")
    assert report.status_code == 201, report.text
    report_id = report.json()["report"]["id"]
    human_id = report.json()["report"]["report_id"]
    assert REPORT_ID_RE.match(human_id), human_id

    # ── 12. download: owner gets real bytes with the honest filename ──
    dl = client.get(f"/reports/{report_id}/download")
    assert dl.status_code == 200, dl.text
    assert dl.content[:5] == b"%PDF-"
    assert f"cropmind-field-report-{human_id}" in dl.headers.get("content-disposition", "")

    # ── 13. regression pins — existence stays unconfirmed to non-owners ──
    client.headers["Authorization"] = f"Bearer {other_token}"
    assert client.get(f"/reports/{report_id}/download").status_code == 404
    assert client.get(f"/reports/{report_id}").status_code == 404
    del client.headers["Authorization"]
    assert client.get(f"/reports/{report_id}/download").status_code == 404  # anonymous
    client.headers["Authorization"] = f"Bearer {token}"

    # ── 14. feedback (per-account, audited, no-auto-retraining stated in UI) ──
    fb = client.post(
        f"/analyses/{analysis_id}/feedback",
        json={"correctness": "YES", "actual_condition": "Northern Leaf Blight", "image_quality": "GOOD"},
    )
    assert fb.status_code == 201, fb.text

    # ── 15. logout → token really dead (denylist, not TTL hope) ──
    out = client.post("/auth/logout")
    assert out.status_code == 200, out.text
    assert client.get("/auth/me").status_code == 401

    # ── 16. audit trail recorded the write events (ADMIN reads it back) ──
    # re-login because the token above is revoked — the account is still ADMIN
    again = client.post("/auth/login", json={"email": "grower@e2e.test", "password": "S3cure-pass1"})
    assert again.status_code == 200
    client.headers["Authorization"] = f"Bearer {again.json()['access_token']}"
    logs = client.get("/admin/audit-logs", params={"limit": 50})
    assert logs.status_code == 200, logs.text
    actions = {row["action"] for row in logs.json()["audit_logs"]}
    assert {"REPORT_GENERATED", "AUTH_LOGOUT"} <= actions
