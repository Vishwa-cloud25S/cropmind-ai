"""Spray-plan simulation API (Phase 8).

Pins: every run is stored verbatim (numbers re-served identical), labels travel
in payload + download filename, engine constraint errors surface verbatim with
their reason, and no route exists without a user-drawn boundary (409).
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.db import models

SQUARE = {"type": "Polygon", "coordinates": [[[0.0, 0.0], [0.0009, 0.0], [0.0009, 0.0009], [0.0, 0.0009], [0.0, 0.0]]]}
WEST_HALF = {"type": "Polygon", "coordinates": [[[0.0, 0.0], [0.00045, 0.0], [0.00045, 0.0009], [0.0, 0.0009], [0.0, 0.0]]]}


def _field_with_boundary(client) -> str:
    farm_id = client.post("/farms", json={"name": "Sim Farm"}).json()["farm"]["id"]
    field_id = client.post(f"/farms/{farm_id}/fields", json={"name": "Sim Field"}).json()["field"]["id"]
    resp = client.patch(f"/fields/{field_id}", json={"boundary_geojson": SQUARE})
    assert resp.status_code == 200, resp.text
    return field_id


def _run(client, field_id: str, **overrides) -> dict:
    payload = {
        "field_id": field_id,
        "treatment_polygons": [WEST_HALF],
        "spray_width_m": 25.0,
        "speed_mps": 5.0,
        "declared_rate_l_per_ha": 200.0,
        "turn_overhead_s": 3.0,
    }
    payload.update(overrides)
    resp = client.post("/simulations/spray-plan", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()["simulation"]


def test_run_persists_verbatim_and_carries_labels(client) -> None:
    field_id = _field_with_boundary(client)
    sim = _run(client, field_id)

    results = sim["results"]
    assert results["savings_pct"] == pytest.approx(50.0, abs=0.2)
    assert results["swath_count"] == 4
    assert results["simulation_label"] == "precision input-application simulation"
    assert "no product, chemical or dosage guidance" in results["honesty_notice"]
    assert any("never suggests products" in a for a in results["assumptions"])
    assert "no aircraft exists" in results["provider_receipt"]["note"]  # seam proven, nothing flown
    assert sim["mission_id"].startswith("SIM-")
    assert sim["params"]["declared_rate_l_per_ha"] == 200.0
    assert sim["params"]["treatment_polygons"] == [WEST_HALF]

    # files win: the stored run re-serves the SAME numbers
    fetched = client.get(f"/simulations/{sim['simulation_id']}").json()["simulation"]
    assert fetched["results"] == results
    assert fetched["params"] == sim["params"]

    listing = client.get("/simulations", params={"field_id": field_id}).json()
    assert listing["count"] == 1
    summary = listing["simulations"][0]["key_results"]
    assert summary["savings_pct"] == results["savings_pct"]
    assert "reproducible" in listing["note"]


def test_route_download_is_simulation_labelled(client) -> None:
    field_id = _field_with_boundary(client)
    sim = _run(client, field_id)
    resp = client.get(f"/simulations/{sim['simulation_id']}/route.geojson")
    assert resp.status_code == 200
    assert "spray-simulation-route" in resp.headers["content-disposition"]
    body = resp.json()
    assert body["simulation"] == "precision input-application simulation"
    spray_flags = {f["properties"]["spray_on"] for f in body["features"]}
    assert spray_flags == {True, False}  # both spraying and transit segments


def test_determinism_across_runs(client) -> None:
    field_id = _field_with_boundary(client)
    first, second = _run(client, field_id), _run(client, field_id)
    for key in ("field_area_ha", "treated_area_ha", "route_length_m", "savings_pct"):
        assert first["results"][key] == second["results"][key]
    assert first["simulation_id"] != second["simulation_id"]  # separate audited runs


def test_no_boundary_means_409_not_a_fake_plan(client) -> None:
    farm_id = client.post("/farms", json={"name": "No Boundary Farm"}).json()["farm"]["id"]
    field_id = client.post(f"/farms/{farm_id}/fields", json={"name": "Bare"}).json()["field"]["id"]
    resp = client.post(
        "/simulations/spray-plan",
        json={
            "field_id": field_id,
            "treatment_polygons": [WEST_HALF],
            "spray_width_m": 25.0,
            "speed_mps": 5.0,
            "declared_rate_l_per_ha": 200.0,
        },
    )
    assert resp.status_code == 409
    assert "no boundary" in resp.json()["detail"]["detail"]
    assert client.post("/simulations/spray-plan", json={"field_id": "nope", "treatment_polygons": [WEST_HALF], "spray_width_m": 25, "speed_mps": 5, "declared_rate_l_per_ha": 200}).status_code == 404


def test_engine_constraints_surface_verbatim(client) -> None:
    field_id = _field_with_boundary(client)
    unclosed = {"type": "Polygon", "coordinates": [[[0, 0], [0.0004, 0], [0.0004, 0.0009], [0, 0.0009]]]}
    resp = client.post(
        "/simulations/spray-plan",
        json={"field_id": field_id, "treatment_polygons": [unclosed], "spray_width_m": 25, "speed_mps": 5, "declared_rate_l_per_ha": 200},
    )
    assert resp.status_code == 400 and "not closed" in resp.json()["detail"]["detail"]

    overlapping = {"type": "Polygon", "coordinates": [[[0.0002, 0.0], [0.0007, 0.0], [0.0007, 0.0009], [0.0002, 0.0009], [0.0002, 0.0]]]}
    resp = client.post(
        "/simulations/spray-plan",
        json={"field_id": field_id, "treatment_polygons": [WEST_HALF, overlapping], "spray_width_m": 25, "speed_mps": 5, "declared_rate_l_per_ha": 200},
    )
    assert resp.status_code == 400 and "overlap" in resp.json()["detail"]["detail"]

    assert client.post(
        "/simulations/spray-plan",
        json={"field_id": field_id, "treatment_polygons": [WEST_HALF], "spray_width_m": 25, "speed_mps": 5, "declared_rate_l_per_ha": 0},
    ).status_code == 422  # non-positive rate never multiplies


def test_run_is_audited(client, db_session_factory) -> None:
    field_id = _field_with_boundary(client)
    sim = _run(client, field_id)
    with db_session_factory() as db:
        actions = db.execute(
            select(models.AuditLog.action).where(
                models.AuditLog.entity == "simulation_run", models.AuditLog.entity_id == sim["simulation_id"]
            )
        ).scalars().all()
    assert actions == ["SIMULATION_RUN_CREATED"]


def test_simulation_not_found(client) -> None:
    assert client.get("/simulations/nope").status_code == 404
    assert client.get("/simulations/nope/route.geojson").status_code == 404
