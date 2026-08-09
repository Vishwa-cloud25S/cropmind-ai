"""Intervention zones + field map data (Phase 7).

Pins the geo-honesty rules end to end: zones stay in evidence space with
georeference "none", INCONCLUSIVE analyses make no zones, risk/priority come only
from the documented rule, reviews are audited with transitions, and every export
carries the simulation label in filename and body.
"""

from __future__ import annotations

from sqlalchemy import select

from app.db import models
from app.services.mapping import derive_risk_level, review_priority, validate_wgs84_polygon
from app.workers.analysis_worker import tick
from tests.test_analysis_flow import StubPredictor, _contract, _handle, _upload


def _completed_analysis(client, tmp_path, contract_overrides: dict | None = None, field_id: str | None = None) -> str:
    query = f"?field_id={field_id}" if field_id else ""
    resp = client.post(f"/images{query}" if query else "/images", files={"file": ("leaf.jpg", _jpeg(), "image/jpeg")})
    if resp.status_code != 201:  # fallback: field-aware upload helper
        image_id = _upload(client)
    else:
        image_id = resp.json()["image"]["id"]
    client.post("/analyses", json={"image_id": image_id})
    stub = StubPredictor(_contract(**(contract_overrides or {})))
    assert tick("zone-worker", handle=_handle(stub, tmp_path)) == 1
    analysis_id = client.get("/analyses", params={"status": "COMPLETED"}).json()["analyses"][0]["analysis_id"]
    return analysis_id


def _jpeg() -> bytes:
    import io

    from PIL import Image as PILImage

    buf = io.BytesIO()
    PILImage.new("RGB", (64, 48), (18, 140, 60)).save(buf, "JPEG")
    return buf.getvalue()


def _make_field(client) -> str:
    farm = client.post("/farms", json={"name": "Map Farm"}).json()["farm"]
    field = client.post(f"/farms/{farm['id']}/fields", json={"name": "North paddock", "crop_id": "tomato"})
    return field.json()["field"]["id"]


def _generate(client, analysis_id: str) -> dict:
    resp = client.post(f"/analyses/{analysis_id}/intervention-zones")
    assert resp.status_code == 201, resp.text
    return resp.json()


# ── generation + geo honesty ───────────────────────────────────────────────────


def test_generated_zones_stay_in_evidence_space(client, tmp_path) -> None:
    analysis_id = _completed_analysis(client, tmp_path)
    body = _generate(client, analysis_id)

    assert body["count"] == 1
    assert body["simulation_label"] == "precision intervention zone simulation"
    zone = body["zones"][0]
    assert zone["geometry"]["coordinate_space"] == "image-normalized-xyxy"  # never pretends to be geo
    assert zone["georeference_source"] == "none"
    assert zone["est_area_ha"] is None
    assert "not georeferenced" in zone["area_note"]  # honest null + reason
    assert zone["review_status"] == "PENDING"
    # band HIGH + severity 0.18 (< 0.5) → score 3 → HIGH → priority 2
    assert zone["risk_level"] == "HIGH"
    assert zone["review_priority"] == 2
    assert "band HIGH" in zone["risk_basis"]
    assert zone["condition"] == "Northern Leaf Blight"


def test_inconclusive_analysis_generates_no_zones(client, tmp_path) -> None:
    analysis_id = _completed_analysis(
        client,
        tmp_path,
        contract_overrides={
            "status": "INCONCLUSIVE",
            "confidence": 0.0924,
            "confidence_band": None,
            "phrasing": "Inconclusive (corn - Northern Leaf Blight at 9% is below the LOW band) - retake photo",
        },
    )
    body = _generate(client, analysis_id)
    assert body["count"] == 0 and body["zones"] == []
    assert "abstained" in body["note"]  # we do not intervene on abstentions


def test_generate_requires_completed_analysis(client, tmp_path) -> None:
    image_id = _upload(client)
    analysis_id = client.post("/analyses", json={"image_id": image_id}).json()["analysis_id"]
    resp = client.post(f"/analyses/{analysis_id}/intervention-zones")
    assert resp.status_code == 409
    detail = resp.json()["detail"]
    assert detail["analysis_status"] == "QUEUED" and detail["poll"].endswith(analysis_id)
    assert client.post("/analyses/does-not-exist/intervention-zones").status_code == 404


def test_regenerate_replaces_pending_but_keeps_reviewed(client, tmp_path) -> None:
    analysis_id = _completed_analysis(client, tmp_path)
    first_id = _generate(client, analysis_id)["zones"][0]["id"]

    regenerated = _generate(client, analysis_id)["zones"][0]
    assert regenerated["id"] != first_id  # pending zone replaced

    review = client.patch(f"/intervention-zones/{regenerated['id']}", json={"review_status": "APPROVED"})
    assert review.status_code == 200

    body = _generate(client, analysis_id)
    assert "1 previously-reviewed zone(s) kept untouched" in body["note"]
    ids = {z["id"] for z in body["zones"]}
    assert regenerated["id"] not in ids  # human decision was not silently overwritten
    all_zones = client.get("/intervention-zones").json()["zones"]
    assert {z["id"] for z in all_zones} == ids | {regenerated["id"]}


# ── review ─────────────────────────────────────────────────────────────────────


def test_review_transitions_are_audited(db_session_factory, client, tmp_path) -> None:
    analysis_id = _completed_analysis(client, tmp_path)
    zone_id = _generate(client, analysis_id)["zones"][0]["id"]

    ok = client.patch(f"/intervention-zones/{zone_id}", json={"review_status": "APPROVED", "review_note": "agronomist agrees"})
    assert ok.status_code == 200
    zone = ok.json()["zone"]
    assert zone["review_status"] == "APPROVED"
    assert zone["review_note"] == "agronomist agrees"
    assert zone["reviewed_at"] is not None
    assert zone["review_transition"] == "PENDING → APPROVED"

    re_review = client.patch(f"/intervention-zones/{zone_id}", json={"review_status": "REJECTED"})
    assert re_review.json()["zone"]["review_transition"] == "APPROVED → REJECTED"  # re-review allowed + recorded

    assert client.patch(f"/intervention-zones/{zone_id}", json={"review_status": "PENDING"}).status_code == 422
    assert client.patch("/intervention-zones/nope", json={"review_status": "APPROVED"}).status_code == 404

    with db_session_factory() as db:
        actions = db.execute(
            select(models.AuditLog.action).where(
                models.AuditLog.entity == "intervention_zone", models.AuditLog.entity_id == zone_id
            )
        ).scalars().all()
    assert actions.count("ZONE_REVIEWED") == 2


# ── list, filters, exports ─────────────────────────────────────────────────────


def test_list_filters_and_whitelists(client, tmp_path) -> None:
    field_id = _make_field(client)
    analysis_id = _completed_analysis(client, tmp_path, field_id=field_id)
    _generate(client, analysis_id)

    by_field = client.get("/intervention-zones", params={"field_id": field_id}).json()
    assert by_field["count"] == 1 and by_field["zones"][0]["field_id"] == field_id

    bogus = client.get("/intervention-zones", params={"review_status": "BOGUS"})
    assert bogus.status_code == 400
    assert set(bogus.json()["detail"]["allowed"]) == {"APPROVED", "PENDING", "REJECTED"}

    assert client.get("/intervention-zones", params={"review_status": "PENDING"}).json()["count"] == 1
    assert client.get(f"/intervention-zones/{by_field['zones'][0]['id']}").status_code == 200
    assert client.get("/intervention-zones/nope").status_code == 404


def test_exports_carry_simulation_label_everywhere(client, tmp_path) -> None:
    field_id = _make_field(client)
    analysis_id = _completed_analysis(client, tmp_path, field_id=field_id)
    zone_id = _generate(client, analysis_id)["zones"][0]["id"]

    geojson = client.get("/intervention-zones/export", params={"field_id": field_id, "format": "geojson"})
    assert geojson.status_code == 200
    assert "simulation" in geojson.headers["content-disposition"]
    body = geojson.json()
    assert body["type"] == "FeatureCollection"
    assert "precision intervention zone simulation" in body["simulation"]
    feature = body["features"][0]
    assert feature["id"] == zone_id
    props = feature["properties"]
    assert props["georeference_source"] == "none"
    assert props["coordinate_space"] == "image-normalized-xyxy"
    assert props["simulation"] == "precision intervention zone simulation"

    csv_resp = client.get("/intervention-zones/export", params={"field_id": field_id, "format": "csv"})
    assert csv_resp.status_code == 200
    assert "simulation" in csv_resp.headers["content-disposition"]
    assert csv_resp.text.startswith("# precision intervention zone simulation")
    assert "simulation_label" in csv_resp.text and zone_id in csv_resp.text

    assert client.get("/intervention-zones/export", params={"format": "yaml"}).status_code == 400


# ── field boundary (real geographic data validation) ───────────────────────────

VALID_BOUNDARY = {
    "type": "Polygon",
    "coordinates": [[[ -0.70, 51.10], [-0.69, 51.10], [-0.69, 51.11], [-0.70, 51.11], [-0.70, 51.10]]],
}


def test_boundary_patch_validates_honestly(client) -> None:
    field_id = _make_field(client)

    ok = client.patch(f"/fields/{field_id}", json={"boundary_geojson": VALID_BOUNDARY})
    assert ok.status_code == 200
    assert ok.json()["field"]["boundary_geojson"]["type"] == "Polygon"
    assert client.get(f"/fields/{field_id}").json()["field"]["boundary_geojson"] == VALID_BOUNDARY

    unclosed = {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1]]]}
    resp = client.patch(f"/fields/{field_id}", json={"boundary_geojson": unclosed})
    assert resp.status_code == 400 and "not closed" in resp.json()["detail"]["detail"]

    out_of_range = {"type": "Polygon", "coordinates": [[[0, 0], [190, 0], [190, 1], [0, 0]]]}
    resp = client.patch(f"/fields/{field_id}", json={"boundary_geojson": out_of_range})
    assert resp.status_code == 400 and "outside valid lon/lat" in resp.json()["detail"]["detail"]

    too_few = {"type": "Polygon", "coordinates": [[[0, 0], [1, 1], [0, 0]]]}
    resp = client.patch(f"/fields/{field_id}", json={"boundary_geojson": too_few})
    assert resp.status_code == 400 and "at least 4 positions" in resp.json()["detail"]["detail"]

    assert client.patch(f"/fields/{field_id}", json={"boundary_geojson": {"type": "Point", "coordinates": [0, 0]}}).status_code == 400

    # stored boundary unchanged after the failed patches (no partial writes)
    assert client.get(f"/fields/{field_id}").json()["field"]["boundary_geojson"] == VALID_BOUNDARY
    # the pure validator round-trips a valid polygon unchanged
    assert validate_wgs84_polygon(VALID_BOUNDARY) == VALID_BOUNDARY


# ── risk rules (pure, documented) ──────────────────────────────────────────────


def test_risk_rules_are_deterministic() -> None:
    assert derive_risk_level("LOW", 0.0)[0] == "LOW"
    assert derive_risk_level("MEDIUM", 0.10)[0] == "MEDIUM"
    assert derive_risk_level("MEDIUM", 0.60)[0] == "HIGH"  # severity proxy escalates once
    assert derive_risk_level("HIGH", 0.10)[0] == "HIGH"
    assert derive_risk_level("HIGH", 0.51)[0] == "CRITICAL"
    assert derive_risk_level("HIGH", None)[0] == "HIGH"  # missing severity never fabricates a bonus
    assert review_priority("CRITICAL") == (1, "review first")
    assert review_priority("LOW") == (4, "low priority")


# ── map-data aggregate ─────────────────────────────────────────────────────────


def test_map_data_aggregates_only_stored_rows(client, tmp_path) -> None:
    field_id = _make_field(client)
    client.patch(f"/fields/{field_id}", json={"boundary_geojson": VALID_BOUNDARY})
    analysis_id = _completed_analysis(client, tmp_path, field_id=field_id)
    _generate(client, analysis_id)

    resp = client.get(f"/fields/{field_id}/map-data")
    assert resp.status_code == 200
    body = resp.json()
    assert body["field"]["boundary_geojson"] == VALID_BOUNDARY
    assert body["field"]["farm_name"] == "Map Farm"
    assert len(body["analyses"]) == 1
    assert body["analyses"][0]["prediction"]["band"] == "HIGH"
    assert len(body["zones"]) == 1

    support = body["decision_support"]
    assert support["risk_counts"] == {"LOW": 0, "MEDIUM": 0, "HIGH": 1, "CRITICAL": 0}
    assert support["review_counts"]["PENDING"] == 1
    assert support["pending_zone_count"] == 1
    assert support["first_priority_zone_ids"] == [body["zones"][0]["id"]]
    assert "not an agronomic risk score" in support["note"]
    assert support["simulation_label"] == "precision intervention zone simulation"

    assert client.get("/fields/nope/map-data").status_code == 404
