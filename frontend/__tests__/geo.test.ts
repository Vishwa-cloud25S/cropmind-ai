import { describe, expect, it } from "vitest";

import { bboxOfRing, closeRing, describeRing, normalizedRingCentroid, normalizedRingToSvgPoints, toGeoJsonPolygon } from "@/lib/geo";
import type { LonLat } from "@/lib/geo";

const SQUARE: LonLat[] = [
  [-0.7, 51.1],
  [-0.69, 51.1],
  [-0.69, 51.11],
  [-0.7, 51.11],
];

describe("ring validation (client-side honesty preview)", () => {
  it("accepts a valid WGS84 square", () => {
    const result = describeRing(SQUARE);
    expect(result.valid).toBe(true);
    expect(result.reason).toBeNull();
    expect(result.closed).toHaveLength(5); // first point repeated
    expect(result.closed[0]).toEqual(result.closed[4]);
  });

  it("rejects fewer than 3 corners", () => {
    expect(describeRing([[-0.7, 51.1], [-0.69, 51.1]]).reason).toContain("at least 3 corners");
  });

  it("rejects duplicate-only corners", () => {
    expect(
      describeRing([
        [-0.7, 51.1],
        [-0.7, 51.1],
        [-0.69, 51.1],
      ]).reason,
    ).toContain("distinct");
  });

  it("rejects out-of-range coordinates with the position named", () => {
    const result = describeRing([[0, 0], [190, 0], [0, 1]]);
    expect(result.valid).toBe(false);
    expect(result.reason).toContain("190");
  });
});

describe("closeRing / toGeoJsonPolygon", () => {
  it("closes an open ring", () => {
    const closed = closeRing(SQUARE);
    expect(closed[0]).toEqual(closed[closed.length - 1]);
  });

  it("leaves an already-closed ring untouched", () => {
    const closed = closeRing([...SQUARE, SQUARE[0]]);
    expect(closed).toHaveLength(5);
  });

  it("produces a single-ring GeoJSON Polygon", () => {
    const poly = toGeoJsonPolygon(SQUARE);
    expect(poly.type).toBe("Polygon");
    expect(poly.coordinates[0][0]).toEqual(poly.coordinates[0][4]);
  });
});

describe("bbox + normalized-space helpers", () => {
  it("computes the bounding box of a ring", () => {
    expect(bboxOfRing(SQUARE)).toEqual({ minLon: -0.7, minLat: 51.1, maxLon: -0.69, maxLat: 51.11 });
    expect(bboxOfRing([])).toBeNull();
  });

  it("keeps normalized coordinates exact for the SVG overlay (no resampling)", () => {
    const ring = [
      [0.25, 0.25],
      [0.8125, 0.25],
      [0.8125, 1],
      [0.25, 1],
      [0.25, 0.25],
    ];
    expect(normalizedRingToSvgPoints(ring)).toBe("0.25,0.25 0.8125,0.25 0.8125,1 0.25,1 0.25,0.25");
  });

  it("finds the centroid of the room for labels", () => {
    const [x, y] = normalizedRingCentroid([
      [0, 0],
      [1, 0],
      [1, 1],
      [0, 1],
    ]);
    expect(x).toBe(0.5);
    expect(y).toBe(0.5);
  });
});
