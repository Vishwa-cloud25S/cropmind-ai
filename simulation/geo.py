"""Planar field-scale geography for the simulators — the documented approximation.

Coordinates the user draws on the Leaflet map are WGS84 lon/lat. The spray engine
works in metres, so we project with an *equirectangular anchor* centred on the
field centroid:

    x = (lon - lon0) * cos(lat0) * M_PER_DEG
    y = (lat - lat0) * M_PER_DEG

with M_PER_DEG = 111_320 m (mean meridional degree). Distortion grows with
distance from the anchor and with |latitude|; for realistic field sizes (≪ 5 km
across) the area error is well below 1%, and every result payload echoes this
assumption verbatim (simulation/spray_simulator.ASSUMPTIONS). Bigger fields are
honestly rejected by the swath cap before precision becomes a question.

All functions are pure and operate on =~(x, y) metre rings unless stated.
Rings are closed lists of (x, y) pairs (first == last).
"""

from __future__ import annotations

import math
from itertools import pairwise

M_PER_DEG = 111_320.0
_EPS = 1e-9

Point = tuple[float, float]
Ring = list[Point]


class GeoError(ValueError):
    """A stated geometric constraint was violated; message is shown to the user."""


# ── projection ─────────────────────────────────────────────────────────────────


def anchor_of(outer_lonlat: list[list[float]]) -> tuple[float, float]:
    """(lat0, lon0) projection anchor: mean of the boundary's outer-ring corners."""
    lats = [p[1] for p in outer_lonlat[:-1]] or [p[1] for p in outer_lonlat]
    lons = [p[0] for p in outer_lonlat[:-1]] or [p[0] for p in outer_lonlat]
    lat0 = sum(lats) / len(lats)
    if not -80.0 <= lat0 <= 80.0:
        raise GeoError(f"field is too close to the poles for the planar approximation (anchor latitude {lat0:.2f})")
    return lat0, sum(lons) / len(lons)


def project(ring_lonlat: list[list[float]], anchor: tuple[float, float]) -> Ring:
    lat0, lon0 = anchor
    factor = math.cos(math.radians(lat0)) * M_PER_DEG
    return [((lon - lon0) * factor, (lat - lat0) * M_PER_DEG) for lon, lat in ring_lonlat]


def unproject(ring: Ring, anchor: tuple[float, float]) -> list[list[float]]:
    lat0, lon0 = anchor
    factor = math.cos(math.radians(lat0)) * M_PER_DEG
    return [[x / factor + lon0, y / M_PER_DEG + lat0] for x, y in ring]


# ── polygon measures ───────────────────────────────────────────────────────────


def polygon_area_m2(ring: Ring) -> float:
    """Shoelace area of a closed ring (metres²)."""
    area = 0.0
    for (x1, y1), (x2, y2) in pairwise(ring):
        area += x1 * y2 - x2 * y1
    return abs(area) / 2.0


def _on_segment(p: Point, a: Point, b: Point) -> bool:
    cross = (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])
    if abs(cross) > _EPS:
        return False
    return (
        min(a[0], b[0]) - _EPS <= p[0] <= max(a[0], b[0]) + _EPS
        and min(a[1], b[1]) - _EPS <= p[1] <= max(a[1], b[1]) + _EPS
    )


def point_in_ring(p: Point, ring: Ring, *, include_boundary: bool = True) -> bool:
    """Even-odd containment; boundary counts as inside when include_boundary.

    The on-segment check runs FIRST either way: a point on an edge/vertex is
    boundary (True / False per the flag), never left to the ray cast — even-odd
    is degenerate exactly on edges and would silently misclassify them."""
    pairs = list(pairwise(ring))
    on_boundary = any(_on_segment(p, a, b) for a, b in pairs)
    if on_boundary:
        return include_boundary
    inside = False
    for a, b in pairs:
        if (a[1] <= p[1] < b[1]) or (b[1] <= p[1] < a[1]):
            x = a[0] + (p[1] - a[1]) * (b[0] - a[0]) / (b[1] - a[1])
            if x > p[0]:
                inside = not inside
    return inside


def _proper_crossing(a1: Point, a2: Point, b1: Point, b2: Point) -> bool:
    """True only for interior crossings — shared endpoints / collinear touch do NOT count."""

    def orient(p: Point, q: Point, r: Point) -> float:
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])

    d1 = orient(b1, b2, a1)
    d2 = orient(b1, b2, a2)
    d3 = orient(a1, a2, b1)
    d4 = orient(a1, a2, b2)
    if min(abs(d1), abs(d2), abs(d3), abs(d4)) <= _EPS:
        return False  # touching or collinear at a vertex/edge — no area overlap
    return (d1 > 0) != (d2 > 0) and (d3 > 0) != (d4 > 0)


def ring_within_ring(inner: Ring, outer: Ring) -> bool:
    """inner lies (boundary-inclusively) inside outer with no edge crossings."""
    if not all(point_in_ring(p, outer, include_boundary=True) for p in inner[:-1]):
        return False
    for a1, a2 in pairwise(inner):
        for b1, b2 in pairwise(outer):
            if _proper_crossing(a1, a2, b1, b2):
                return False
    return True


def _strict_witness_in(witness_ring: Ring, target: Ring) -> bool:
    """Any vertex, edge midpoint or ring centroid of witness_ring strictly inside target.

    Between strict-vertex, midpoint and centroid samples we catch containment,
    identical rings, and collinear-edge-attached overlaps that a vertex-only
    test would miss (map-drawn shapes are non-degenerate)."""
    vertices = witness_ring[:-1] if len(witness_ring) > 1 else witness_ring
    if any(point_in_ring(p, target, include_boundary=False) for p in vertices):
        return True
    midpoints = [
        ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)
        for a, b in pairwise(witness_ring)
    ]
    if any(point_in_ring(m, target, include_boundary=False) for m in midpoints):
        return True
    if vertices:
        centroid = (
            sum(p[0] for p in vertices) / len(vertices),
            sum(p[1] for p in vertices) / len(vertices),
        )
        return point_in_ring(centroid, target, include_boundary=False)
    return False


def rings_overlap(a: Ring, b: Ring) -> bool:
    """True area overlap (touching edges/vertices alone is allowed)."""
    for a1, a2 in pairwise(a):
        for b1, b2 in pairwise(b):
            if _proper_crossing(a1, a2, b1, b2):
                return True
    return _strict_witness_in(a, b) or _strict_witness_in(b, a)


# ── boustrophedon scanlines ────────────────────────────────────────────────────


def scanline_intervals(ring: Ring, y: float) -> list[tuple[float, float]]:
    """Sorted x-intervals where the horizontal line y passes inside the ring (even-odd)."""
    xs: list[float] = []
    for a, b in pairwise(ring):
        if (a[1] <= y < b[1]) or (b[1] <= y < a[1]):
            xs.append(a[0] + (y - a[1]) * (b[0] - a[0]) / (b[1] - a[1]))
    xs.sort()
    return [(xs[i], xs[i + 1]) for i in range(0, len(xs) - 1, 2)]


def subtract_gaps_keep_overlap(
    base: list[tuple[float, float]], masks: list[tuple[float, float]]
) -> list[tuple[float, float]]:
    """base ∩ (union of masks): the spray-on sub-intervals of a swath."""
    out: list[tuple[float, float]] = []
    for b0, b1 in base:
        for m0, m1 in masks:
            lo, hi = max(b0, m0), min(b1, m1)
            if hi - lo > _EPS:
                out.append((lo, hi))
    out.sort()
    return out


def ring_y_range(ring: Ring) -> tuple[float, float]:
    ys = [p[1] for p in ring]
    return min(ys), max(ys)
