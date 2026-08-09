"use client";

import { MapContainer, Polygon, Polyline, TileLayer } from "react-leaflet";

import "leaflet/dist/leaflet.css";

import { bboxOfPolygon } from "@/lib/geo";
import type { RouteFeature } from "@/lib/types";

const SPRAY_ON = "#15803d"; // green 700 — input applied
const TRANSIT = "#a8a29e"; // stone 400 — moving with spray off

/**
 * The simulated route drawn over the real boundary: green segments = spray on,
 * grey = transit. Geometry comes straight from the stored result payload.
 */
export default function RouteMapView({
  boundary,
  treatments,
  features,
}: {
  boundary: { type: "Polygon"; coordinates: number[][][] };
  treatments: { type: "Polygon"; coordinates: number[][][] }[];
  features: RouteFeature[];
}) {
  const box = bboxOfPolygon(boundary);
  const center: [number, number] = box ? [(box.minLat + box.maxLat) / 2, (box.minLon + box.maxLon) / 2] : [20, 0];

  return (
    <div className="card overflow-hidden p-0" data-testid="route-map">
      <div className="border-b border-stone-200 px-4 py-3">
        <h2 className="text-lg font-bold text-stone-900">Simulated route (boustrophedon)</h2>
        <p className="text-xs text-stone-500">
          <span className="font-semibold" style={{ color: SPRAY_ON }}>
            green
          </span>{" "}
          = spray on ·{" "}
          <span className="font-semibold" style={{ color: "#78716c" }}>
            grey
          </span>{" "}
          = transit (spray off) — from the stored run, not recomputed here
        </p>
      </div>
      <MapContainer center={center} zoom={15} style={{ height: 460, width: "100%" }} scrollWheelZoom>
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <Polygon
          positions={boundary.coordinates[0].map((p) => [p[1], p[0]] as [number, number])}
          pathOptions={{ color: "#1d6f4c", fillOpacity: 0.03, weight: 2 }}
        />
        {treatments.map((polygon, i) => (
          <Polygon
            key={i}
            positions={polygon.coordinates[0].map((p) => [p[1], p[0]] as [number, number])}
            pathOptions={{ color: "#b45309", fillColor: "#b45309", fillOpacity: 0.15, weight: 1.5 }}
          />
        ))}
        {features.map((feature, i) => (
          <Polyline
            key={i}
            positions={feature.geometry.coordinates.map((p) => [p[1], p[0]] as [number, number])}
            pathOptions={{
              color: feature.properties.spray_on ? SPRAY_ON : TRANSIT,
              weight: feature.properties.spray_on ? 3 : 1.5,
              opacity: feature.properties.spray_on ? 0.85 : 0.6,
            }}
          />
        ))}
      </MapContainer>
    </div>
  );
}
