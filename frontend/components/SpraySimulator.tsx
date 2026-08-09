"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";

import {
  errorMessage,
  getFarm,
  getSimulation,
  listFarms,
  listSimulations,
  runSprayPlan,
} from "@/lib/api";
import { toGeoJsonPolygon } from "@/lib/geo";
import type { Farm, FieldRecord, SimulationRunDetail, SimulationSummary } from "@/lib/types";
import type { LonLat } from "@/lib/geo";
import RouteMapView from "@/components/RouteMapView";
import SprayResultCard from "@/components/SprayResultCard";
import TreatmentDrawer from "@/components/TreatmentDrawer";

/**
 * /simulate orchestration. The two honest input sources: a real drawn boundary
 * (from Phase 7) + treatment polygons the operator marks themselves. Every number
 * comes from the stored run — this component renders, never recomputes.
 */
export default function SpraySimulator() {
  const [farms, setFarms] = useState<Farm[] | null>(null);
  const [fieldsByFarm, setFieldsByFarm] = useState<Record<string, FieldRecord[]>>({});
  const [fieldId, setFieldId] = useState("");
  const [treatments, setTreatments] = useState<LonLat[][]>([]);
  const [sprayWidth, setSprayWidth] = useState("5");
  const [speed, setSpeed] = useState("5");
  const [rate, setRate] = useState("");
  const [turnOverhead, setTurnOverhead] = useState("0");
  const [current, setCurrent] = useState<SimulationRunDetail | null>(null);
  const [history, setHistory] = useState<SimulationSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

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

  const boundedFields = useMemo(
    () =>
      (farms ?? []).flatMap((farm) =>
        (fieldsByFarm[farm.id] ?? [])
          .filter((field) => field.boundary_geojson !== null)
          .map((field) => ({ ...field, farmName: farm.name })),
      ),
    [farms, fieldsByFarm],
  );
  const unboundedCount = useMemo(
    () =>
      (farms ?? []).reduce(
        (total, farm) => total + (fieldsByFarm[farm.id] ?? []).filter((f) => f.boundary_geojson === null).length,
        0,
      ),
    [farms, fieldsByFarm],
  );

  const selectedField = boundedFields.find((f) => f.id === fieldId) ?? null;

  const refreshHistory = useCallback(async () => {
    if (!fieldId) {
      setHistory(null);
      return;
    }
    try {
      setHistory((await listSimulations({ fieldId, limit: 10 })).simulations);
    } catch {
      setHistory([]); // history is secondary; the error banner shows the primary failure
    }
  }, [fieldId]);

  useEffect(() => {
    void refreshHistory();
  }, [refreshHistory]);

  function pickField(id: string) {
    setFieldId(id);
    setTreatments([]);
    setCurrent(null);
    setError(null);
  }

  const rateNum = Number(rate);
  const canRun =
    selectedField !== null &&
    treatments.length > 0 &&
    rate.trim() !== "" &&
    Number.isFinite(rateNum) &&
    rateNum > 0 &&
    Number(sprayWidth) > 0 &&
    Number(speed) > 0;

  async function run() {
    if (!selectedField || !selectedField.boundary_geojson) return;
    setBusy(true);
    setError(null);
    try {
      const response = await runSprayPlan({
        field_id: selectedField.id,
        treatment_polygons: treatments.map((ring) => toGeoJsonPolygon(ring)),
        spray_width_m: Number(sprayWidth),
        speed_mps: Number(speed),
        declared_rate_l_per_ha: rateNum,
        turn_overhead_s: Number(turnOverhead) || 0,
      });
      setCurrent(response.simulation);
      await refreshHistory();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function openStoredRun(id: string) {
    setError(null);
    try {
      setCurrent((await getSimulation(id)).simulation);
    } catch (err) {
      setError(errorMessage(err));
    }
  }

  return (
    <div className="space-y-6" data-testid="spray-simulator">
      <div className="card">
        <label htmlFor="sim-field" className="field-label">
          Field with a drawn boundary
        </label>
        <select id="sim-field" className="input mt-1" value={fieldId} onChange={(e) => pickField(e.target.value)}>
          <option value="">choose a field…</option>
          {boundedFields.map((field) => (
            <option key={field.id} value={field.id}>
              {field.farmName} · {field.name}
              {field.area_ha !== null ? ` (${field.area_ha} ha declared)` : ""}
            </option>
          ))}
        </select>
        {farms !== null && boundedFields.length === 0 && !error ? (
          <p className="alert-info mt-3" role="note">
            No field has a boundary yet — the simulator plans routes on real drawn geography only.{" "}
            <Link href="/map" className="link-cta">
              Draw a boundary on the Map page first
            </Link>
            .
          </p>
        ) : null}
        {unboundedCount > 0 && fieldId === "" ? (
          <p className="mt-2 text-xs text-stone-500">
            {unboundedCount} field(s) hidden because they have no boundary yet.
          </p>
        ) : null}
      </div>

      {error ? (
        <p className="alert-error" role="alert">
          {error}
        </p>
      ) : null}

      {selectedField?.boundary_geojson ? (
        <>
          <TreatmentDrawer boundary={selectedField.boundary_geojson} treatments={treatments} onChange={setTreatments} />

          <form
            className="card"
            aria-label="Simulation parameters"
            onSubmit={(e) => {
              e.preventDefault();
              void run();
            }}
          >
            <h2 className="text-lg font-bold text-stone-900">Parameters</h2>
            <p className="mt-1 text-sm leading-6 text-stone-600">
              The rate is <strong>your declared number</strong> — CropMind never suggests products or doses.
              Constants here are generic machine parameters, not agronomic advice.
            </p>
            <div className="mt-4 grid gap-3 sm:grid-cols-4">
              <div>
                <label htmlFor="spray-width" className="field-label">
                  Spray width (m)
                </label>
                <input id="spray-width" className="input" inputMode="decimal" value={sprayWidth} onChange={(e) => setSprayWidth(e.target.value)} />
              </div>
              <div>
                <label htmlFor="speed" className="field-label">
                  Speed (m/s)
                </label>
                <input id="speed" className="input" inputMode="decimal" value={speed} onChange={(e) => setSpeed(e.target.value)} />
              </div>
              <div>
                <label htmlFor="rate" className="field-label">
                  Declared rate (L/ha)
                </label>
                <input id="rate" className="input" inputMode="decimal" value={rate} onChange={(e) => setRate(e.target.value)} placeholder="type your own rate" required />
              </div>
              <div>
                <label htmlFor="turn-overhead" className="field-label">
                  Turn overhead (s/swath)
                </label>
                <input id="turn-overhead" className="input" inputMode="decimal" value={turnOverhead} onChange={(e) => setTurnOverhead(e.target.value)} />
              </div>
            </div>
            <div className="mt-4 flex items-center gap-3">
              <button type="submit" className="btn-primary" disabled={!canRun || busy}>
                {busy ? "Simulating…" : "Run simulation"}
              </button>
              {!canRun ? (
                <p className="text-xs text-stone-500">
                  needs: field + at least one finished polygon + your declared rate
                </p>
              ) : null}
            </div>
          </form>
        </>
      ) : null}

      {current ? (
        <>
          <SprayResultCard results={current.results} simulationId={current.simulation_id} />
          <RouteMapView
            boundary={current.params.boundary_geojson}
            treatments={current.params.treatment_polygons}
            features={current.results.route_geojson.features}
          />
        </>
      ) : null}

      {history && history.length > 0 ? (
        <section className="card" aria-label="Stored simulation runs">
          <h2 className="text-lg font-bold text-stone-900">Stored runs for this field ({history.length})</h2>
          <p className="mt-1 text-xs text-stone-500">
            Every figure is reproducible from the stored params + versioned engine — click a row to re-open it.
          </p>
          <div className="mt-3 overflow-x-auto">
            <table className="table-basic">
              <thead>
                <tr>
                  <th scope="col">Created</th>
                  <th scope="col">Swaths</th>
                  <th scope="col">Treated</th>
                  <th scope="col">Saving (SIM)</th>
                  <th scope="col" className="text-right">
                    Open
                  </th>
                </tr>
              </thead>
              <tbody>
                {history.map((run) => (
                  <tr key={run.simulation_id}>
                    <td>{run.created_at ? new Date(run.created_at).toLocaleString() : "—"}</td>
                    <td>{run.key_results.swath_count}</td>
                    <td>{(run.key_results.treated_fraction * 100).toFixed(1)}%</td>
                    <td>
                      {run.key_results.savings_volume_l.toFixed(0)} L ({run.key_results.savings_pct.toFixed(1)}%)
                    </td>
                    <td className="text-right">
                      <button type="button" className="link-cta" onClick={() => openStoredRun(run.simulation_id)}>
                        Re-open →
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}
    </div>
  );
}
