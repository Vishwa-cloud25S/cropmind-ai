/**
 * Pure geometry helpers for the map (Phase 7). No DOM, no Leaflet — everything
 * here is unit-tested. Two coordinate worlds exist and never mix:
 *   - WGS84 bounds/polygon for field boundaries (real geography the user drew)
 *   - image-normalized-xyxy for zone/region evidence (NOT geography)
 */

export type LonLat = [number, number];

/** Validate + describe a drawn boundary before it is sent to the API. */
export function describeRing(points: LonLat[]): { valid: boolean; reason: string | null; closed: LonLat[] } {
  const closed = closeRing(points);
  if (points.length < 3) return { valid: false, reason: "at least 3 corners are needed", closed };
  const unique = new Set(points.map(([lon, lat]) => `${lon},${lat}`));
  if (unique.size < 3) return { valid: false, reason: "corners must be distinct", closed };
  for (const [lon, lat] of points) {
    if (!Number.isFinite(lon) || !Number.isFinite(lat) || lon < -180 || lon > 180 || lat < -90 || lat > 90) {
      return { valid: false, reason: `position [${lon}, ${lat}] is outside valid lon/lat ranges`, closed };
    }
  }
  return { valid: true, reason: null, closed };
}

/** Close a ring for preview/submission (first == last; the API requires closure). */
export function closeRing(points: LonLat[]): LonLat[] {
  if (points.length === 0) return [];
  const first = points[0];
  const last = points[points.length - 1];
  return first[0] === last[0] && first[1] === last[1] ? points : [...points, first];
}

/** Draft points → GeoJSON Polygon (single closed outer ring). */
export function toGeoJsonPolygon(points: LonLat[]): { type: "Polygon"; coordinates: number[][][] } {
  return { type: "Polygon", coordinates: [closeRing(points)] };
}

export interface BBox {
  minLon: number;
  minLat: number;
  maxLon: number;
  maxLat: number;
}

export function bboxOfRing(points: LonLat[]): BBox | null {
  if (points.length === 0) return null;
  let minLon = Infinity;
  let minLat = Infinity;
  let maxLon = -Infinity;
  let maxLat = -Infinity;
  for (const [lon, lat] of points) {
    minLon = Math.min(minLon, lon);
    minLat = Math.min(minLat, lat);
    maxLon = Math.max(maxLon, lon);
    maxLat = Math.max(maxLat, lat);
  }
  return { minLon, minLat, maxLon, maxLat };
}

export function bboxOfPolygon(polygon: { coordinates: number[][][] }): BBox | null {
  const outer = polygon.coordinates[0] ?? [];
  return bboxOfRing(outer.map((p) => [p[0], p[1]] as LonLat));
}

/**
 * Normalized xyxy polygon → SVG points in a 0..1 viewBox (y down, like screens).
 * Returns the "x,y x,y …" string for <polygon points>. Kept at viewBox scale so
 * the consumer controls sizing/responsiveness.
 */
export function normalizedRingToSvgPoints(ring: number[][]): string {
  return ring.map((p) => `${p[0]},${p[1]}`).join(" ");
}

/** Centroid of a normalized ring — for label placement on the SVG overlay. */
export function normalizedRingCentroid(ring: number[][]): [number, number] {
  if (ring.length === 0) return [0.5, 0.5];
  let x = 0;
  let y = 0;
  for (const p of ring) {
    x += p[0] ?? 0;
    y += p[1] ?? 0;
  }
  return [x / ring.length, y / ring.length];
}
