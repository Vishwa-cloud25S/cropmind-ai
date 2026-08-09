import { simulationRouteUrl } from "@/lib/api";
import type { SprayResults } from "@/lib/types";

/**
 * Presentational card for one stored spray-plan SIMULATION. Labels and the full
 * assumption set come from the engine payload verbatim — the UI never recomputes
 * a savings figure (files win).
 */
export default function SprayResultCard({
  results,
  simulationId,
}: {
  results: SprayResults;
  simulationId: string;
}) {
  const r = results;
  return (
    <article className="card space-y-5" aria-label="Simulation results" data-testid="spray-result">
      <header className="flex flex-wrap items-center gap-2">
        <span className="chip-medium">SIMULATION</span>
        <span className="chip-muted">{r.simulation_label}</span>
        <span className="chip-info" title={`${r.engine.package} v${r.engine.version}`}>
          engine v{r.engine.version}
        </span>
      </header>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="stat-card">
          <p className="field-label">Field / treated</p>
          <p className="mt-1 text-xl font-bold text-stone-900">
            {r.field_area_ha.toFixed(2)} ha → {r.treated_area_ha.toFixed(2)} ha
          </p>
          <p className="mt-1 text-xs text-stone-500">{(r.treated_fraction * 100).toFixed(1)}% of the drawn boundary</p>
        </div>
        <div className="stat-card">
          <p className="field-label">Blanket vs precision input</p>
          <p className="mt-1 text-xl font-bold text-stone-900">
            {r.blanket_volume_l.toFixed(0)} L → {r.precision_volume_l.toFixed(0)} L
          </p>
          <p className="mt-1 text-xs text-stone-500">area × your declared rate, both directions</p>
        </div>
        <div className="stat-card">
          <p className="field-label">Simulated saving</p>
          <p className="mt-1 text-2xl font-bold text-emerald-800">
            {r.savings_volume_l.toFixed(0)} L ({r.savings_pct.toFixed(1)}%)
          </p>
          <p className="mt-1 text-xs text-stone-500">SIMULATION — planning illustration, not a field guarantee</p>
        </div>
        <div className="stat-card">
          <p className="field-label">Route / time</p>
          <p className="mt-1 text-xl font-bold text-stone-900">
            {(r.route_length_m / 1000).toFixed(2)} km · {(r.est_time_s / 60).toFixed(1)} min
          </p>
          <p className="mt-1 text-xs text-stone-500">
            {r.swath_count} swaths · spray-on {(r.spray_on_length_m / 1000).toFixed(2)} km
          </p>
        </div>
      </div>

      <div>
        <h3 className="text-sm font-semibold text-stone-900">Assumptions (verbatim from the engine)</h3>
        <ul className="mt-2 space-y-1 text-sm leading-6 text-stone-600">
          {r.assumptions.map((assumption) => (
            <li key={assumption} className="flex gap-2">
              <span aria-hidden="true" className="text-emerald-800">
                ▸
              </span>
              {assumption}
            </li>
          ))}
        </ul>
      </div>

      <p className="text-xs leading-5 text-stone-500">
        Provider receipt: {r.provider_receipt.provider} · mission {r.provider_receipt.mission_id} —{" "}
        {r.provider_receipt.note}
      </p>
      <p className="alert-info" role="note">
        {r.honesty_notice}
      </p>
      <div>
        <a className="btn-secondary" href={simulationRouteUrl(simulationId)} download>
          Download route (GeoJSON, simulation-labelled)
        </a>
      </div>
    </article>
  );
}
