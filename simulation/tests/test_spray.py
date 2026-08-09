"""Spray simulator tests — the numbers here are hand-computed, so any engine
regression breaks arithmetic we can recite. SIMULATION labelling is pinned."""

from __future__ import annotations

import pytest

from simulation import geo
from simulation.drone_simulator import SimulatedDroneProvider
from simulation.spray_simulator import SprayError, SprayParams, run

# 0.0009° ≈ 100.188 m at the equator anchor → field ≈ 1.0038 ha
SQUARE = [[0.0, 0.0], [0.0009, 0.0], [0.0009, 0.0009], [0.0, 0.0009], [0.0, 0.0]]
WEST_HALF = [[0.0, 0.0], [0.00045, 0.0], [0.00045, 0.0009], [0.0, 0.0009], [0.0, 0.0]]
EAST_HALF = [[0.00045, 0.0], [0.0009, 0.0], [0.0009, 0.0009], [0.00045, 0.0009], [0.00045, 0.0]]
SIDE_M = geo.M_PER_DEG * 0.0009  # 100.188


def _params(**overrides) -> SprayParams:
    base = {
        "boundary_lonlat": SQUARE,
        "treatments_lonlat": [WEST_HALF],
        "spray_width_m": 25.0,
        "speed_mps": 5.0,
        "declared_rate_l_per_ha": 200.0,
        "turn_overhead_s": 3.0,
    }
    base.update(overrides)
    return SprayParams(**base)


# ── honesty labels + core arithmetic ───────────────────────────────────────────


def test_half_field_treatment_gives_half_savings() -> None:
    result = run(_params())
    field_ha = (SIDE_M * SIDE_M) / 10_000
    # results are documented as rounded (areas 4dp, volumes 1dp) — tolerances match
    assert result["field_area_ha"] == pytest.approx(field_ha, abs=5e-4)
    assert result["treated_area_ha"] == pytest.approx(field_ha / 2, abs=5e-4)
    assert result["untreated_area_ha"] == pytest.approx(field_ha / 2, abs=5e-4)
    assert result["treated_fraction"] == pytest.approx(0.5, abs=1e-4)
    assert result["savings_pct"] == pytest.approx(50.0, abs=0.1)
    assert result["blanket_volume_l"] == pytest.approx(field_ha * 200.0, abs=0.1)
    assert result["precision_volume_l"] == pytest.approx(field_ha / 2 * 200.0, abs=0.1)
    assert result["savings_volume_l"] == pytest.approx(field_ha / 2 * 200.0, abs=0.1)


def test_route_is_boustrophedon_with_exact_swath_count() -> None:
    result = run(_params())
    assert result["swath_count"] == 4  # ys = 12.5, 37.5, 62.5, 87.5 (next 112.5 > 100.19)
    # spray-on covers the western 50.094 m on each of 4 swaths
    assert result["spray_on_length_m"] == pytest.approx((SIDE_M / 2) * 4, rel=1e-3)
    assert result["route_length_m"] >= result["spray_on_length_m"]
    est = result["route_length_m"] / 5.0 + 4 * 3.0
    assert result["est_time_s"] == pytest.approx(est, abs=0.15)  # results documented as 1dp-rounded
    directions = [
        (f["properties"]["spray_on"], f["geometry"]["coordinates"][0][0] > f["geometry"]["coordinates"][-1][0])
        for f in result["route_geojson"]["features"]
        if f["properties"]["spray_on"]
    ]
    assert any(reversed_ for _, reversed_ in directions) and any(not r for _, r in directions)  # zig-zag


def test_full_field_treatment_means_zero_savings_honestly() -> None:
    result = run(_params(treatments_lonlat=[SQUARE]))
    assert result["savings_pct"] == pytest.approx(0.0, abs=0.01)
    assert result["untreated_area_ha"] == pytest.approx(0.0, abs=1e-6)


def test_edge_adjacent_treatments_are_allowed_and_sum_exactly() -> None:
    result = run(_params(treatments_lonlat=[WEST_HALF, EAST_HALF]))  # shared edge is not overlap
    assert result["treated_fraction"] == pytest.approx(1.0, abs=1e-3)
    assert result["savings_pct"] == pytest.approx(0.0, abs=0.01)


def test_every_result_carries_the_label_and_assumptions() -> None:
    result = run(_params())
    assert result["simulation_label"] == "precision input-application simulation"
    assert any("never suggests products" in a for a in result["assumptions"])
    assert result["route_geojson"]["simulation"] == "precision input-application simulation"


def test_deterministic_same_inputs_same_numbers() -> None:
    first, second = run(_params()), run(_params())
    for key in ("field_area_ha", "treated_area_ha", "route_length_m", "savings_pct", "est_time_s"):
        assert first[key] == second[key]


# ── stated constraints (rejected loudly, never silently clipped) ───────────────


def test_overlap_and_containment_and_bad_inputs_are_rejected() -> None:
    overlapping = [[0.0002, 0.0], [0.0006, 0.0], [0.0006, 0.0009], [0.0002, 0.0009], [0.0002, 0.0]]
    with pytest.raises(SprayError, match="overlap"):
        run(_params(treatments_lonlat=[WEST_HALF, overlapping]))
    outside = [[0.0010, 0.0], [0.0011, 0.0], [0.0011, 0.0009], [0.0010, 0.0009], [0.0010, 0.0]]
    with pytest.raises(SprayError, match="not fully inside"):
        run(_params(treatments_lonlat=[outside]))
    with pytest.raises(SprayError, match="mark at least one"):
        run(_params(treatments_lonlat=[]))
    with pytest.raises(SprayError, match="rate must be positive"):
        run(_params(declared_rate_l_per_ha=0.0))
    with pytest.raises(SprayError, match="width must be positive"):
        run(_params(spray_width_m=0.0))


def test_swath_cap_quotes_the_measured_count() -> None:
    tall = [[0.0, 0.0], [0.01, 0.0], [0.01, 0.2], [0.0, 0.2], [0.0, 0.0]]
    treat = [[0.0, 0.0], [0.005, 0.0], [0.005, 0.2], [0.0, 0.2], [0.0, 0.0]]
    with pytest.raises(SprayError, match="swaths"):
        run(_params(boundary_lonlat=tall, treatments_lonlat=[treat], spray_width_m=1.0))


# ── pure geometry micro-pins ───────────────────────────────────────────────────


def test_geo_primitives() -> None:
    ring = [(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)]
    assert geo.polygon_area_m2(ring) == pytest.approx(100.0)
    assert geo.point_in_ring((5, 5), ring) and not geo.point_in_ring((15, 5), ring)
    assert geo.point_in_ring((0, 5), ring)  # boundary counts as inside

    tri = [(0, 0), (10, 0), (5, 10), (0, 0)]
    assert geo.scanline_intervals(tri, 5.0) == [pytest.approx((2.5, 7.5), rel=1e-9)]

    inner_touching = [(0, 0), (5, 0), (5, 10), (0, 10), (0, 0)]
    crossing = [(-5, 5), (15, 5), (5, 20), (-5, 5)]
    assert geo.ring_within_ring(inner_touching, ring)  # edge-touching is fine
    assert not geo.ring_within_ring(crossing, ring)
    assert not geo.rings_overlap(inner_touching, ring) or geo.ring_within_ring(inner_touching, ring)
    box_a = [(0, 0), (4, 0), (4, 4), (0, 4), (0, 0)]
    box_b_touch = [(4, 0), (8, 0), (8, 4), (4, 4), (4, 0)]
    box_c_overlap = [(2, 0), (6, 0), (6, 4), (2, 4), (2, 0)]
    assert not geo.rings_overlap(box_a, box_b_touch)  # shared edge allowed
    assert geo.rings_overlap(box_a, box_c_overlap)


# ── drone provider seam ────────────────────────────────────────────────────────


def test_simulated_drone_records_intent_only() -> None:
    provider = SimulatedDroneProvider()
    mission_id = provider.upload_mission({"kind": "SPRAY_PLAN", "swaths": 5})
    assert mission_id.startswith("SIM-")
    receipt = provider.receipt(mission_id)
    assert receipt["provider"] == "simulated-drone-v1"
    assert "no aircraft exists" in receipt["note"]
    with pytest.raises(KeyError):
        provider.get_telemetry("SIM-nope")
