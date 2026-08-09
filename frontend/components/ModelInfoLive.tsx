"use client";

import { useEffect, useState } from "react";

import { errorMessage, getModelInfo, getSupportedCrops } from "@/lib/api";
import type { ModelInfo, SupportedCrops } from "@/lib/types";

/**
 * Live registry read (ml/configs/model.yaml + taxonomy.yaml via the backend).
 * Data below comes from the API only; on failure we show the failure, never
 * cached or assumed numbers.
 */
export default function ModelInfoLive() {
  const [info, setInfo] = useState<ModelInfo | null>(null);
  const [truth, setTruth] = useState<SupportedCrops | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        setInfo(await getModelInfo());
      } catch (err) {
        if (!cancelled) setError(errorMessage(err));
      }
      try {
        setTruth(await getSupportedCrops());
      } catch (err) {
        if (!cancelled) setError((prev) => prev ?? errorMessage(err));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  if (error) {
    return (
      <p className="alert-caution" role="note">
        Live registry data unavailable right now ({error}). The static policy sections on this page still apply;
        nothing here is served from stale cached numbers.
      </p>
    );
  }

  if (!info || !truth) return <p className="text-sm text-stone-500">Loading live registry…</p>;

  const model = info.model as Record<string, unknown>;
  const bands = info.confidence_bands;

  return (
    <div className="space-y-8">
      <section className="card" aria-label="Current model status">
        <div className="flex flex-wrap items-center gap-2">
          <span className={truth.model_available ? "chip-high" : "chip-low"}>
            {truth.model_available ? "MODEL AVAILABLE" : "MODEL AVAILABLE: FALSE"}
          </span>
          <span className="chip-muted">taxonomy v{truth.taxonomy_version}</span>
          {truth.updated ? <span className="chip-muted">updated {truth.updated}</span> : null}
        </div>
        <dl className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div>
            <dt className="field-label">Name / version</dt>
            <dd className="mt-1 font-semibold text-stone-900">
              {String(model.name ?? "—")} · v{String(model.version ?? "—")}
            </dd>
          </div>
          <div>
            <dt className="field-label">Registry status</dt>
            <dd className="mt-1 font-semibold text-stone-900">{String(model.status ?? "—")}</dd>
          </div>
          <div>
            <dt className="field-label">Uncertainty method</dt>
            <dd className="mt-1 font-semibold text-stone-900">{info.uncertainty_method ?? "—"}</dd>
          </div>
          <div>
            <dt className="field-label">Severity method</dt>
            <dd className="mt-1 font-semibold text-stone-900">{info.severity_method ?? "—"}</dd>
          </div>
        </dl>
        {truth.note ? <p className="mt-3 text-sm leading-6 text-stone-600">{truth.note}</p> : null}
        {!truth.model_available ? (
          <p className="alert-caution mt-3" role="note">
            The production model is not wired into live serving on this deployment yet. Analyses currently run
            against the synthetic sample model and every prediction is stamped <code>demo: true</code>. A trained
            baseline exists in the registry (status: EVALUATED) with its metrics published in the model card —
            including a published out-of-distribution shortfall on PlantDoc field imagery.
          </p>
        ) : null}
      </section>

      <section className="card" aria-label="Confidence bands">
        <h2 className="text-lg font-bold text-stone-900">Confidence bands (live config)</h2>
        <p className="mt-1 text-sm leading-6 text-stone-600">
          Bands are configuration, tuned only with published evaluation evidence. Below the LOW band the system
          abstains: INCONCLUSIVE with retake / agronomist-review advice instead of a guess.
        </p>
        <div className="mt-4 grid gap-3 sm:grid-cols-4">
          <div className="stat-card">
            <span className="chip-high">HIGH</span>
            <p className="mt-2 text-2xl font-bold text-stone-900">≥ {bands.high}</p>
          </div>
          <div className="stat-card">
            <span className="chip-medium">MEDIUM</span>
            <p className="mt-2 text-2xl font-bold text-stone-900">≥ {bands.medium}</p>
          </div>
          <div className="stat-card">
            <span className="chip-low">LOW</span>
            <p className="mt-2 text-2xl font-bold text-stone-900">≥ {bands.low}</p>
          </div>
          <div className="stat-card">
            <span className="chip-muted">BELOW LOW</span>
            <p className="mt-2 font-bold text-stone-900">INCONCLUSIVE — we abstain</p>
          </div>
        </div>
      </section>

      <section className="card" aria-label="Supported crops and conditions">
        <h2 className="text-lg font-bold text-stone-900">
          Supported crops &amp; conditions ({truth.crop_count} crops)
        </h2>
        <p className="mt-1 text-sm leading-6 text-stone-600">
          “Type to search” is deliberately absent — the crop/condition vocabulary is closed, so the UI can never
          hallucinate an unsupported label.
        </p>
        <div className="mt-5 space-y-5">
          {truth.crops.map((crop) => (
            <div key={crop.crop_id}>
              <h3 className="flex items-center gap-2 font-semibold capitalize text-stone-900">
                {crop.name}
                <span className="chip-muted">{crop.status}</span>
              </h3>
              <ul className="mt-2 flex flex-wrap gap-2">
                {crop.conditions.map((condition) => (
                  <li
                    key={condition.disease_id}
                    className={condition.supported_by_model ? "chip-high" : "chip-muted"}
                    title={
                      condition.supported_by_model
                        ? `supported by model${condition.confidence_threshold !== null ? ` · threshold ${condition.confidence_threshold}` : ""}${condition.dataset_source ? ` · data: ${condition.dataset_source}` : ""}`
                        : "in taxonomy, not yet supported by the model"
                    }
                  >
                    {condition.name}
                    {condition.supported_by_model ? "" : " (not yet)"}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
        <p className="alert-info mt-5" role="note">
          {truth.disclaimer}
        </p>
      </section>

      <p className="text-xs leading-5 text-stone-500">
        {info.registry_note} {info.client_notice}
      </p>
    </div>
  );
}
