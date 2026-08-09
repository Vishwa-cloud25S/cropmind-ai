import type { Prediction } from "@/lib/types";
import { BandChip, DemoBadge, PredictionStatusChip } from "@/components/StatusBadge";

/**
 * The complete honesty presentation of one prediction (docs/04 §2):
 * verbatim phrasing, band with thresholds context, abstention supporting copy,
 * labelled severity proxy, demo flags, model identity, standing client notice.
 * Nothing here recomputes a number from the model module.
 */

function pct(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined) return "—";
  return `${(value * 100).toFixed(digits)}%`;
}

function ConfidenceBar({ value }: { value: number }) {
  const width = Math.max(0, Math.min(100, Math.round(value * 100)));
  return (
    <div
      className="mt-1.5 h-2.5 w-full overflow-hidden rounded-full bg-stone-200"
      role="img"
      aria-label={`Confidence bar: ${width} percent`}
    >
      <div className="h-full rounded-full bg-emerald-700" style={{ width: `${width}%` }} />
    </div>
  );
}

export default function PredictionCard({ prediction }: { prediction: Prediction }) {
  const p = prediction;
  const inconclusive = p.status === "INCONCLUSIVE";
  return (
    <article aria-labelledby="prediction-heading" className="card space-y-6">
      <header>
        <div className="flex flex-wrap items-center gap-2">
          <PredictionStatusChip status={p.status} />
          <BandChip band={p.band} />
          <DemoBadge demo={p.demo} />
        </div>
        {/* The model module's phrasing, verbatim — never reworded UI-side */}
        <h2 id="prediction-heading" className="mt-3 text-xl font-bold leading-8 text-stone-900">
          {p.phrasing}
        </h2>
        {p.analysis_demo_requested ? (
          <p className="mt-1 text-xs text-stone-500">Analysis was run in demo mode by request.</p>
        ) : null}
      </header>

      {inconclusive ? (
        <div className="alert-caution" role="note">
          <strong>Why inconclusive?</strong> The top score ({pct(p.confidence, 1)}) is below the
          low confidence band, so the system abstains instead of guessing a wrong label.
          Take a sharper, closer, well-lit photo of a single affected leaf — or request an
          agronomist review.
        </div>
      ) : null}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="stat-card">
          <p className="field-label">Confidence</p>
          <p className="mt-1 text-2xl font-bold text-stone-900">{pct(p.confidence, 1)}</p>
          <ConfidenceBar value={p.confidence} />
        </div>
        <div className="stat-card">
          <p className="field-label">Uncertainty</p>
          <p className="mt-1 text-2xl font-bold text-stone-900">{pct(p.uncertainty, 1)}</p>
          <p className="mt-1.5 text-xs leading-5 text-stone-500">normalized prediction entropy</p>
        </div>
        <div className="stat-card">
          <p className="field-label">{p.severity_label ?? "Estimated visual severity"}</p>
          <p className="mt-1 text-2xl font-bold text-stone-900">{pct(p.estimated_visual_severity, 1)}</p>
          <p className="mt-1.5 text-xs leading-5 text-stone-500">visual proxy — not an agronomic measurement</p>
        </div>
        <div className="stat-card">
          <p className="field-label">Crop / condition</p>
          <p className="mt-1 text-lg font-bold capitalize text-stone-900">{p.crop}</p>
          <p className="text-sm text-stone-600">{p.condition.name}</p>
          <p className="mt-1 font-mono text-xs text-stone-400">{p.condition.disease_id}</p>
        </div>
      </div>

      <section aria-label="Model identity" className="overflow-x-auto">
        <table className="table-basic">
          <caption className="sr-only">Model identity and reproducibility fields</caption>
          <tbody>
            <tr>
              <th scope="row" className="pr-4 text-left align-top text-xs font-semibold uppercase tracking-wider text-stone-500">Model</th>
              <td>
                {p.model.name} · v{p.model.version}
                {p.model.demo ? <span className="text-amber-800"> (synthetic sample model)</span> : null}
              </td>
            </tr>
            <tr>
              <th scope="row" className="pr-4 text-left align-top text-xs font-semibold uppercase tracking-wider text-stone-500">Dataset version</th>
              <td>{p.model.dataset_version ?? "— (sample model uses no training dataset)"}</td>
            </tr>
            <tr>
              <th scope="row" className="pr-4 text-left align-top text-xs font-semibold uppercase tracking-wider text-stone-500">Threshold version</th>
              <td>{p.model.threshold_version ?? "—"}</td>
            </tr>
            <tr>
              <th scope="row" className="pr-4 text-left align-top text-xs font-semibold uppercase tracking-wider text-stone-500">Latency</th>
              <td>{Math.round(p.latency_ms)} ms (model call, this worker)</td>
            </tr>
          </tbody>
        </table>
      </section>

      {p.regions.length > 0 ? (
        <section aria-label="Detected regions">
          <h3 className="text-sm font-semibold text-stone-900">Detected regions</h3>
          <ul className="mt-2 space-y-2 text-sm text-stone-700">
            {p.regions.map((region, i) => (
              <li key={i} className="rounded-lg border border-stone-200 bg-stone-50 px-3 py-2">
                Image-space box{" "}
                <span className="font-mono text-xs">
                  [{region.geometry.coordinates[0][0].map((n) => n.toFixed(2)).join(", ")}
                  {" → "}
                  {region.geometry.coordinates[0][2].map((n) => n.toFixed(2)).join(", ")}]
                </span>{" "}
                · ≈{(region.area_px ?? 0).toLocaleString()} px² of the stored image ·{" "}
                <span className="text-xs text-stone-500">{region.geometry.coordinate_space}</span>
              </li>
            ))}
          </ul>
          <p className="mt-2 text-xs leading-5 text-stone-500">{p.explainability_caveat}</p>
        </section>
      ) : null}

      <details className="rounded-lg border border-stone-200 bg-stone-50 px-4 py-3">
        <summary className="cursor-pointer text-sm font-semibold text-stone-700">
          Raw prediction contract (verbatim, as stored)
        </summary>
        <pre className="mt-3 max-h-96 overflow-auto rounded bg-stone-900 p-3 text-xs leading-5 text-stone-100">
          {JSON.stringify(p.raw, null, 2)}
        </pre>
      </details>

      <p className="alert-info" role="note">{p.client_notice}</p>
    </article>
  );
}
