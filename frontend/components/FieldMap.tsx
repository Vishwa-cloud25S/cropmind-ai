"use client";

import { useCallback, useMemo, useState } from "react";
import { CircleMarker, MapContainer, Polygon, Polyline, TileLayer, useMapEvents } from "react-leaflet";

import "leaflet/dist/leaflet.css";

import { bboxOfRing, describeRing, toGeoJsonPolygon } from "@/lib/geo";
import type { LonLat } from "@/lib/geo";

const BOUNDARY_COLOR = "#1d6f4c"; // emerald 800

function ClickCollector({ onAdd }: { onAdd: (point: LonLat) => void }) {
  useMapEvents({
    click(event) {
      onAdd([Number(event.latlng.lng.toFixed(6)), Number(event.latlng.lat.toFixed(6))]);
    },
  });
  return null;
}

/**
 * The geographic half of Phase 7: the ONLY geography this system stores, because
 * the user provides it directly — a WGS84 field boundary drawn on OpenStreetMap
 * tiles. Zone/region evidence never appears here (it is image-space; pretending
 * otherwise would fabricate locations). Validation previews before PATCHing.
 */
export default function FieldMap({
  boundary,
  onSaveBoundary,
  saving,
}: {
  boundary: { type: "Polygon"; coordinates: number[][][] } | null;
  onSaveBoundary: (poly: { type: "Polygon"; coordinates: number[][][] }) => Promise<void> | void;
  saving?: boolean;
}) {
  const [drawing, setDrawing] = useState(false);
  const [draft, setDraft] = useState<LonLat[]>([]);
  const [error, setError] = useState<string | null>(null);

  const hasBoundary = boundary !== null && boundary.coordinates?.[0]?.length >= 4;
  const center = useMemo<[number, number]>(() => {
    if (hasBoundary) {
      const ring = boundary.coordinates[0].map((p) => [p[0], p[1]] as LonLat);
      const box = bboxOfRing(ring);
      if (box) return [(box.minLat + box.maxLat) / 2, (box.minLon + box.maxLon) / 2];
    }
    return [20, 0]; // whole-world neutral view until a boundary exists
  }, [boundary, hasBoundary]);

  const draftRing = useMemo(() => describeRing(draft), [draft]);

  const addPoint = useCallback(
    (point: LonLat) => {
      if (!drawing) return;
      setError(null);
      setDraft((current) => [...current, point]);
    },
    [drawing],
  );

  function startDrawing() {
    setDrawing(true);
    setDraft([]);
    setError(null);
  }

  async function save() {
    if (!draftRing.valid) {
      setError(draftRing.reason ?? "boundary is not valid yet");
      return;
    }
    try {
      await onSaveBoundary(toGeoJsonPolygon(draftRing.closed));
      setDrawing(false);
      setDraft([]);
    } catch {
      /* the parent surfaces the API's reason; keep the draft editable */
    }
  }

  return (
    <div className="card overflow-hidden p-0" data-testid="field-map">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-stone-200 px-4 py-3">
        <div>
          <h2 className="text-lg font-bold text-stone-900">Field boundary</h2>
          <p className="text-xs text-stone-500">
            Real WGS84 geography — drawn by you, validated client- and server-side (lon/lat ranges, closed ring).
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {!drawing ? (
            <button type="button" className="btn-secondary" onClick={startDrawing}>
              {hasBoundary ? "Redraw boundary" : "Draw boundary"}
            </button>
          ) : (
            <>
              <button type="button" className="btn-ghost" onClick={() => setDraft((d) => d.slice(0, -1))} disabled={draft.length === 0}>
                Undo point
              </button>
              <button
                type="button"
                className="btn-ghost"
                onClick={() => {
                  setDrawing(false);
                  setDraft([]);
                  setError(null);
                }}
              >
                Cancel
              </button>
              <button type="button" className="btn-primary" onClick={save} disabled={!draftRing.valid || saving}>
                {saving ? "Saving…" : `Save boundary (${draft.length} points)`}
              </button>
            </>
          )}
        </div>
      </div>

      {drawing ? (
        <p className="border-b border-stone-200 bg-sky-50 px-4 py-2 text-sm text-sky-900" role="note">
          Click the map to add boundary corners ({draft.length} placed
          {draftRing.valid ? "" : ` — ${draftRing.reason ?? "at least 3 corners are needed"}`}).
        </p>
      ) : null}
      {error ? (
        <p className="alert-error m-3" role="alert">
          {error}
        </p>
      ) : null}

      <MapContainer center={center} zoom={hasBoundary ? 14 : 2} style={{ height: 420, width: "100%" }} scrollWheelZoom>
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <ClickCollector onAdd={addPoint} />

        {hasBoundary ? (
          <Polygon
            positions={boundary.coordinates[0].map((p) => [p[1], p[0]] as [number, number])}
            pathOptions={{ color: BOUNDARY_COLOR, fillColor: BOUNDARY_COLOR, fillOpacity: 0.15, weight: 2.5 }}
          />
        ) : (
          drawing ? null : null
        )}

        {draft.length >= 2 ? <Polyline positions={draft.map(([lon, lat]) => [lat, lon] as [number, number])} pathOptions={{ color: "#0369a1", dashArray: "6 6" }} /> : null}
        {draft.length >= 3 ? (
          <Polygon positions={draft.map(([lon, lat]) => [lat, lon] as [number, number])} pathOptions={{ color: "#0369a1", fillOpacity: 0.08 }} />
        ) : null}
        {draft.map(([lon, lat], i) => (
          <CircleMarker key={`${lon}-${lat}-${i}`} center={[lat, lon]} radius={4} pathOptions={{ color: "#0369a1", fillColor: "#0369a1", fillOpacity: 1 }} />
        ))}
      </MapContainer>

      <p className="px-4 py-2 text-xs leading-5 text-stone-500">
        Tiles © OpenStreetMap contributors. Only this boundary is geographic data; zone overlays stay on their
        source imagery in evidence space, by design.
      </p>
    </div>
  );
}
