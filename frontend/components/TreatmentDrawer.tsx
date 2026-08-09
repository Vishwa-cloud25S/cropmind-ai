"use client";

import { useCallback, useState } from "react";
import { CircleMarker, MapContainer, Polygon, Polyline, TileLayer, useMapEvents } from "react-leaflet";

import "leaflet/dist/leaflet.css";

import { bboxOfPolygon, toGeoJsonPolygon } from "@/lib/geo";
import type { LonLat } from "@/lib/geo";

const BOUNDARY_COLOR = "#1d6f4c";
const TREATMENT_COLOR = "#b45309"; // amber 700 — treatment polygons the operator marks
const DRAFT_COLOR = "#0369a1";

function ClickCollector({ onAdd }: { onAdd: (p: LonLat) => void }) {
  useMapEvents({
    click(event) {
      onAdd([Number(event.latlng.lng.toFixed(6)), Number(event.latlng.lat.toFixed(6))]);
    },
  });
  return null;
}

/**
 * Where simulation geography comes from: the operator MARKS treatment polygons
 * on the real field boundary (image-space zones stay evidence — they inform,
 * never auto-scale). Polygons are previews until the engine validates them
 * server-side (inside boundary, non-overlapping, closed).
 */
export default function TreatmentDrawer({
  boundary,
  treatments,
  onChange,
}: {
  boundary: { type: "Polygon"; coordinates: number[][][] };
  treatments: LonLat[][]; // finished rings (open, not yet closed client-side)
  onChange: (treatments: LonLat[][]) => void;
}) {
  const [draft, setDraft] = useState<LonLat[] | null>(null);
  const drawing = draft !== null;

  const box = bboxOfPolygon(boundary);
  const center: [number, number] = box
    ? [(box.minLat + box.maxLat) / 2, (box.minLon + box.maxLon) / 2]
    : [20, 0];

  const add = useCallback(
    (p: LonLat) => {
      if (drawing) setDraft((d) => [...(d ?? []), p]);
    },
    [drawing],
  );

  function finish() {
    if (draft && draft.length >= 3) onChange([...treatments, draft]);
    setDraft(null);
  }

  return (
    <div className="card overflow-hidden p-0" data-testid="treatment-drawer">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-stone-200 px-4 py-3">
        <div>
          <h2 className="text-lg font-bold text-stone-900">Mark what to treat ({treatments.length})</h2>
          <p className="text-xs text-stone-500">
            You trace the affected patches — the simulator never scales image-space zones into hectares.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {!drawing ? (
            <button type="button" className="btn-secondary" onClick={() => setDraft([])}>
              New polygon
            </button>
          ) : (
            <>
              <button type="button" className="btn-ghost" onClick={() => setDraft((d) => (d ?? []).slice(0, -1))} disabled={!draft?.length}>
                Undo point
              </button>
              <button type="button" className="btn-ghost" onClick={() => setDraft(null)}>
                Cancel
              </button>
              <button type="button" className="btn-primary" onClick={finish} disabled={(draft?.length ?? 0) < 3}>
                Finish polygon ({draft?.length ?? 0})
              </button>
            </>
          )}
        </div>
      </div>
      {drawing ? (
        <p className="border-b border-stone-200 bg-sky-50 px-4 py-2 text-sm text-sky-900" role="note">
          Click inside the boundary to place corners (need 3+). Finish when the patch is traced.
        </p>
      ) : null}

      <MapContainer center={center} zoom={15} style={{ height: 420, width: "100%" }} scrollWheelZoom>
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <ClickCollector onAdd={add} />
        <Polygon
          positions={boundary.coordinates[0].map((p) => [p[1], p[0]] as [number, number])}
          pathOptions={{ color: BOUNDARY_COLOR, fillColor: BOUNDARY_COLOR, fillOpacity: 0.06, weight: 2 }}
        />
        {treatments.map((ring, i) => (
          <Polygon
            key={i}
            positions={ring.map(([lon, lat]) => [lat, lon] as [number, number])}
            pathOptions={{ color: TREATMENT_COLOR, fillColor: TREATMENT_COLOR, fillOpacity: 0.22, weight: 2 }}
          />
        ))}
        {draft && draft.length >= 2 ? (
          <Polyline positions={draft.map(([lon, lat]) => [lat, lon])} pathOptions={{ color: DRAFT_COLOR, dashArray: "5 5" }} />
        ) : null}
        {draft && draft.length >= 3 ? (
          <Polygon positions={draft.map(([lon, lat]) => [lat, lon])} pathOptions={{ color: DRAFT_COLOR, fillOpacity: 0.08 }} />
        ) : null}
        {(draft ?? []).map(([lon, lat], i) => (
          <CircleMarker key={`${lon}-${lat}-${i}`} center={[lat, lon]} radius={4} pathOptions={{ color: DRAFT_COLOR, fillColor: DRAFT_COLOR, fillOpacity: 1 }} />
        ))}
      </MapContainer>

      {treatments.length > 0 ? (
        <ul className="divide-y divide-stone-200 px-4">
          {treatments.map((ring, i) => (
            <li key={i} className="flex items-center justify-between py-2 text-sm">
              <span>
                Polygon {i + 1} — {ring.length} corners · preview as{" "}
                <code className="text-xs">{JSON.stringify(toGeoJsonPolygon(ring).coordinates[0].length)}</code> positions when closed
              </span>
              <button
                type="button"
                className="btn-danger"
                onClick={() => onChange(treatments.filter((_, j) => j !== i))}
              >
                Remove
              </button>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
