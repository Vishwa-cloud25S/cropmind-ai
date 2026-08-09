"""Precision input-application simulator (Phase 8) — the SprayingMachineProvider.

Honesty contract (echoed into every result, enforced in tests):
  * SIMULATION-labelled arithmetic only: areas the user marked × a rate the user
    declared. No product, brand, chemical or dosage content exists here.
  * Areas are exact polygon math in the documented planar projection (see
    simulation/geo.py). Spray-on *route length* is sampled at swath centrelines —
    stated as an approximation next to the exact areas.
  * The route is a boustrophedon (lawnmower) sweep of the real drawn boundary;
    turns are modelled as straight joins plus an optional per-swath overhead.
  * Treatment polygons must each lie inside the boundary and must not overlap
    each other — the API rejects violations with the precise reason instead of
    silently clipping geometry the user did not approve.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import pairwise
from typing import Any, Protocol

from simulation.geo import (
    GeoError,
    anchor_of,
    polygon_area_m2,
    project,
    ring_within_ring,
    ring_y_range,
    rings_overlap,
    scanline_intervals,
    subtract_gaps_keep_overlap,
    unproject,
)

SIMULATION_LABEL = "precision input-application simulation"

ASSUMPTIONS = [
    "Planar equirectangular projection anchored at the field centroid (area error << 1% for fields up to a few km)",
    "Areas are exact polygon math; spray-on route length is sampled at swath centrelines",
    "Boustrophedon route; turns are straight joins plus the declared per-swath turn overhead",
    "The rate is whatever you declared — the simulator never suggests products, chemicals or doses",
    "No tank-mixing, drift, overlap compensation or terrain effects are modelled",
]

DEFAULT_SWATH_CAP = 2000  # refuses absurd fields/widths instead of melting silently


class SprayError(GeoError):
    """Stated planning constraint violated; the message is user-facing verbatim."""


@dataclass(frozen=True)
class SprayParams:
    boundary_lonlat: list[list[float]]  # closed WGS84 outer ring
    treatments_lonlat: list[list[list[float]]]  # closed WGS84 rings (the user-marked zone copies)
    spray_width_m: float
    speed_mps: float
    declared_rate_l_per_ha: float
    turn_overhead_s: float = 0.0


@dataclass
class Segment:
    path: list[tuple[float, float]]
    spray_on: bool

    @property
    def length_m(self) -> float:
        total = 0.0
        for (x1, y1), (x2, y2) in pairwise(self.path):
            total += ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
        return total


@dataclass
class RoutePlan:
    anchor: tuple[float, float]
    boundary_m: list[tuple[float, float]]
    treatments_m: list[list[tuple[float, float]]]
    segments: list[Segment] = field(default_factory=list)
    swath_count: int = 0
    spray_on_length_m: float = 0.0
    route_length_m: float = 0.0


class SprayingMachineProvider(Protocol):
    """The hardware seam from docs/02 §8 — a real vendor adapter implements this
    same Protocol and the API layer never changes."""

    def plan_route(self, params: SprayParams) -> RoutePlan: ...
    def simulate_run(self, params: SprayParams, plan: RoutePlan) -> dict[str, Any]: ...


def _validate(params: SprayParams) -> tuple[tuple[float, float], list[tuple[float, float]], list[list[tuple[float, float]]]]:
    if params.spray_width_m <= 0:
        raise SprayError("spray width must be positive")
    if params.speed_mps <= 0:
        raise SprayError("speed must be positive")
    if params.declared_rate_l_per_ha <= 0:
        raise SprayError("declared rate must be positive — the simulator only multiplies YOUR number")
    if len(params.treatments_lonlat) == 0:
        raise SprayError("mark at least one treatment polygon on the map")
    anchor = anchor_of(params.boundary_lonlat)
    boundary_m = project(params.boundary_lonlat, anchor)
    treatments_m = [project(t, anchor) for t in params.treatments_lonlat]
    for i, treatment in enumerate(treatments_m, start=1):
        if not ring_within_ring(treatment, boundary_m):
            raise SprayError(f"treatment polygon {i} is not fully inside the field boundary")
    for i in range(len(treatments_m)):
        for j in range(i + 1, len(treatments_m)):
            if rings_overlap(treatments_m[i], treatments_m[j]):
                raise SprayError(
                    f"treatment polygons {i + 1} and {j + 1} overlap — mark each distinct patch once"
                )
    return anchor, boundary_m, treatments_m


class SimulatedSprayingMachine:
    """Boustrophedon planner behind the provider Protocol (no hardware involved)."""

    def __init__(self, swath_cap: int = DEFAULT_SWATH_CAP):
        self.swath_cap = swath_cap

    def plan_route(self, params: SprayParams) -> RoutePlan:
        anchor, boundary_m, treatments_m = _validate(params)
        y_min, y_max = ring_y_range(boundary_m)
        width = params.spray_width_m
        half = width / 2.0
        # count sweep lines first so the cap error can quote a MEASURED number
        ys: list[float] = []
        y = y_min + half
        while y < y_max:
            ys.append(y)
            y += width
        if not ys:
            ys = [(y_min + y_max) / 2.0]
        if len(ys) > self.swath_cap:
            raise SprayError(
                f"route would need {len(ys)} swaths (cap {self.swath_cap}) — increase the spray width for this field size"
            )

        plan = RoutePlan(anchor=anchor, boundary_m=boundary_m, treatments_m=treatments_m)
        cursor: tuple[float, float] | None = None
        for index, yy in enumerate(ys):
            base = sorted(scanline_intervals(boundary_m, yy))
            if not base:
                continue
            spray_intervals: list[tuple[float, float]] = []
            for treatment in treatments_m:
                spray_intervals.extend(scanline_intervals(treatment, yy))
            spray_on = subtract_gaps_keep_overlap(base, spray_intervals)
            plan.swath_count += 1
            forward = index % 2 == 0  # boustrophedon: alternate travel direction

            intervals = base if forward else base[::-1]
            for x0, x1 in intervals:
                enter, exit_ = (x0, x1) if forward else (x1, x0)
                if cursor is not None:
                    gap = Segment(path=[cursor, (enter, yy)], spray_on=False)
                    plan.segments.append(gap)
                    plan.route_length_m += gap.length_m
                on_here = subtract_gaps_keep_overlap([(x0, x1)], spray_on)
                cuts = sorted({v for iv in on_here for v in iv} | {x0, x1})
                sub_segments: list[tuple[float, float, bool]] = []
                for c0, c1 in pairwise(cuts):
                    if c1 - c0 <= 1e-9:
                        continue
                    mid = (c0 + c1) / 2.0
                    sub_segments.append((c0, c1, any(a <= mid <= b for a, b in on_here)))
                if not sub_segments:
                    sub_segments = [(x0, x1, False)]
                if not forward:
                    sub_segments = sub_segments[::-1]
                for c0, c1, on in sub_segments:
                    # path order traces actual travel direction (zig-zag), not just geometry
                    path = [(c0, yy), (c1, yy)] if forward else [(c1, yy), (c0, yy)]
                    seg = Segment(path=path, spray_on=on)
                    plan.segments.append(seg)
                    plan.route_length_m += seg.length_m
                    if on:
                        plan.spray_on_length_m += seg.length_m
                cursor = (exit_, yy)
        return plan

    def simulate_run(self, params: SprayParams, plan: RoutePlan | None = None) -> dict[str, Any]:
        plan = plan or self.plan_route(params)
        field_area_ha = polygon_area_m2(plan.boundary_m) / 10_000.0
        treated_area_ha = sum(polygon_area_m2(t) for t in plan.treatments_m) / 10_000.0
        untreated_ha = max(0.0, field_area_ha - treated_area_ha)
        est_time_s = plan.route_length_m / params.speed_mps + plan.swath_count * params.turn_overhead_s
        blanket_l = field_area_ha * params.declared_rate_l_per_ha
        precision_l = treated_area_ha * params.declared_rate_l_per_ha
        savings_l = blanket_l - precision_l
        savings_pct = (savings_l / blanket_l * 100.0) if blanket_l > 0 else 0.0

        route_geojson = {
            "type": "FeatureCollection",
            "simulation": SIMULATION_LABEL,
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "LineString", "coordinates": unproject(seg.path, plan.anchor)},
                    "properties": {"spray_on": seg.spray_on, "length_m": round(seg.length_m, 2)},
                }
                for seg in plan.segments
            ],
        }
        return {
            "field_area_ha": round(field_area_ha, 4),
            "treated_area_ha": round(treated_area_ha, 4),
            "untreated_area_ha": round(untreated_ha, 4),
            "treated_fraction": round(treated_area_ha / field_area_ha, 4) if field_area_ha else 0.0,
            "swath_count": plan.swath_count,
            "spray_on_length_m": round(plan.spray_on_length_m, 1),
            "route_length_m": round(plan.route_length_m, 1),
            "est_time_s": round(est_time_s, 1),
            "blanket_volume_l": round(blanket_l, 1),
            "precision_volume_l": round(precision_l, 1),
            "savings_volume_l": round(savings_l, 1),
            "savings_pct": round(savings_pct, 1),
            "route_geojson": route_geojson,
        }


def run(params: SprayParams, swath_cap: int = DEFAULT_SWATH_CAP) -> dict[str, Any]:
    """One call → plan + simulation result with assumptions + label embedded."""
    machine = SimulatedSprayingMachine(swath_cap=swath_cap)
    plan = machine.plan_route(params)
    result = machine.simulate_run(params, plan)
    result["simulation_label"] = SIMULATION_LABEL
    result["assumptions"] = ASSUMPTIONS
    return result
