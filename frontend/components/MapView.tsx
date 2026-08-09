"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";

import { errorMessage, generateZones, getFarm, getFieldMapData, listFarms, updateField } from "@/lib/api";
import type { Farm, FieldMapData, FieldRecord } from "@/lib/types";
import FieldMap from "@/components/FieldMap";
import ImageSpaceOverlay from "@/components/ImageSpaceOverlay";
import { AnalysisStatusChip, BandChip } from "@/components/StatusBadge";
import ZonesPanel from "@/components/ZonesPanel";
import { imageDownloadUrl } from "@/lib/api";

const RISK_COLOR: Record<string, string> = {
  LOW: "#78716c",
  MEDIUM: "#0369a1",
  HIGH: "#b45309",
  CRITICAL: "#b91c1c",
};

/**
 * /map orchestration: field picker → boundary drawing (real geography) + zones
 * (evidence space, reviewed here) + per-analysis zone generation. Geographic map
 * and image-space overlay are deliberately separate honest surfaces.
 */
export default function MapView({ initialFieldId }: { initialFieldId?: string }) {
  const [farms, setFarms] = useState<Farm[] | null>(null);
  const [fieldsByFarm, setFieldsByFarm] = useState<Record<string, FieldRecord[]>>({});
  const [fieldId, setFieldId] = useState<string>(initialFieldId ?? "");
  const [data, setData] = useState<FieldMapData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [savingBoundary, setSavingBoundary] = useState(false);
  const [generatingFor, setGeneratingFor] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const farmList = await listFarms();
        if (cancelled) return;
        setFarms(farmList.farms);
        const entries: Record<string, FieldRecord[]> = {};
        await Promise.all(
          farmList.farms.map(async (farm) => {
            try {
              entries[farm.id] = (await getFarm(farm.id)).fields;
            } catch {
              entries[farm.id] = [];
            }
          }),
        );
        if (!cancelled) setFieldsByFarm(entries);
      } catch (err) {
        if (!cancelled) setError(errorMessage(err));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const allFields = useMemo(
    () =>
      (farms ?? []).flatMap((farm) =>
        (fieldsByFarm[farm.id] ?? []).map((field) => ({ ...field, farmName: farm.name })),
      ),
    [farms, fieldsByFarm],
  );

  const refresh = useCallback(async () => {
    if (!fieldId) {
      setData(null);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      setData(await getFieldMapData(fieldId));
    } catch (err) {
      setError(errorMessage(err));
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [fieldId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function saveBoundary(poly: { type: "Polygon"; coordinates: number[][][] }) {
    setSavingBoundary(true);
    setError(null);
    try {
      await updateField(fieldId, { boundary_geojson: poly });
      setNotice("Boundary saved (validated server-side as WGS84).");
      await refresh();
    } catch (err) {
      setError(errorMessage(err));
      throw err; // keeps the draft on the map for correction
    } finally {
      setSavingBoundary(false);
    }
  }

  async function generateFor(analysisId: string) {
    setGeneratingFor(analysisId);
    setError(null);
    setNotice(null);
    try {
      const result = await generateZones(analysisId);
      setNotice(result.note);
      await refresh();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setGeneratingFor(null);
    }
  }

  const zonesWithImages = (data?.zones ?? []).filter((zone) => zone.image_id);

  return (
    <div className="space-y-6" data-testid="map-view">
      <div className="card">
        <label htmlFor="map-field" className="field-label">
          Field
        </label>
        <select id="map-field" className="input mt-1" value={fieldId} onChange={(e) => setFieldId(e.target.value)}>
          <option value="">choose a field…</option>
          {allFields.map((field) => (
            <option key={field.id} value={field.id}>
              {field.farmName} · {field.name}
              {field.crop_id ? ` (${field.crop_id})` : ""}
            </option>
          ))}
        </select>
        {farms !== null && allFields.length === 0 && !error ? (
          <p className="alert-info mt-3" role="note">
            No fields yet —{" "}
            <Link href="/farms" className="link-cta">
              create a farm and a field first
            </Link>
            .
          </p>
        ) : null}
      </div>

      {error ? (
        <p className="alert-error" role="alert">
          {error}
        </p>
      ) : null}
      {notice ? (
        <p className="alert-info" role="note">
          {notice}
        </p>
      ) : null}

      {fieldId && loading ? <p className="text-sm text-stone-500">Loading field map data…</p> : null}

      {data ? (
        <>
          <FieldMap boundary={data.field.boundary_geojson} onSaveBoundary={saveBoundary} saving={savingBoundary} />

          <section className="card" aria-label="Analyses on this field">
            <h2 className="text-lg font-bold text-stone-900">Analyses on this field ({data.analyses.length})</h2>
            {data.analyses.length === 0 ? (
              <p className="alert-info mt-3" role="note">
                No analyses attached to this field yet.{" "}
                <Link href="/analyze" className="link-cta">
                  Analyze a photo
                </Link>{" "}
                and pick this field in the wizard.
              </p>
            ) : (
              <ul className="mt-3 divide-y divide-stone-200">
                {data.analyses.map((analysis) => {
                  const hasZones = data.zones.some((zone) => zone.analysis_id === analysis.analysis_id);
                  const suspected = analysis.prediction?.status === "SUSPECTED";
                  return (
                    <li key={analysis.analysis_id} className="flex flex-wrap items-center justify-between gap-3 py-2.5">
                      <div className="flex flex-wrap items-center gap-2">
                        <AnalysisStatusChip status={analysis.status} demo={analysis.demo} />
                        {analysis.prediction ? (
                          <>
                            <BandChip band={analysis.prediction.band} />
                            <span className="text-sm text-stone-700">{analysis.prediction.phrasing}</span>
                          </>
                        ) : (
                          <span className="text-sm text-stone-500">no prediction stored yet</span>
                        )}
                      </div>
                      <div className="flex items-center gap-3">
                        {analysis.status === "COMPLETED" && suspected ? (
                          <button
                            type="button"
                            className="btn-secondary"
                            disabled={generatingFor === analysis.analysis_id}
                            onClick={() => generateFor(analysis.analysis_id)}
                          >
                            {generatingFor === analysis.analysis_id ? "Generating…" : hasZones ? "Regenerate zones" : "Generate zones"}
                          </button>
                        ) : null}
                        {analysis.status === "COMPLETED" && analysis.prediction?.status === "INCONCLUSIVE" ? (
                          <span className="chip-muted" title="The system abstained on this evidence — zones would not be honest">
                            abstained — no zones by design
                          </span>
                        ) : null}
                        <Link href={`/analyses/${analysis.analysis_id}`} className="link-cta">
                          View →
                        </Link>
                      </div>
                    </li>
                  );
                })}
              </ul>
            )}
          </section>

          {zonesWithImages.length > 0 ? (
            <section className="card" aria-label="Zone evidence overlays">
              <h2 className="text-lg font-bold text-stone-900">Zone evidence (image space, true coordinates)</h2>
              <p className="mt-1 text-sm leading-6 text-stone-600">
                The model reasoned in image space, so zones drawn on their source imagery are the honest overlay —
                these are NOT map positions.
              </p>
              <div className="mt-4 grid gap-4 md:grid-cols-2">
                {zonesWithImages.map((zone) => (
                  <ImageSpaceOverlay
                    key={zone.id}
                    imageUrl={imageDownloadUrl(zone.image_id as string)}
                    imageAlt={`Stored upload for analysis ${zone.analysis_id.slice(0, 8)}`}
                    polygons={[
                      {
                        ring: zone.geometry.coordinates[0],
                        color: RISK_COLOR[zone.risk_level] ?? "#78716c",
                        label: `${zone.condition} — ${zone.risk_level}`,
                      },
                    ]}
                    caption="image-normalized-xyxy — evidence space, not geography"
                  />
                ))}
              </div>
            </section>
          ) : null}

          <ZonesPanel zones={data.zones} decisionSupport={data.decision_support} fieldId={data.field.id} onChanged={refresh} />
        </>
      ) : null}
    </div>
  );
}
