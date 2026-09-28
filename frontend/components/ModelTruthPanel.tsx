"use client";

import { useEffect, useState } from "react";

import { errorMessage, getModelInfo, getReadiness, getSupportedCrops } from "@/lib/api";
import type { ModelInfo, SupportedCrops } from "@/lib/types";

export interface TruthDeps {
  getReadinessFn?: typeof getReadiness;
  getModelInfoFn?: typeof getModelInfo;
  getSupportedCropsFn?: typeof getSupportedCrops;
}

/**
 * Live model-truth strip: readiness, registry identity, confidence bands and
 * crop coverage pulled straight from the backend — the UI shows config state,
 * never marketing copy. If the API is unreachable it says so plainly.
 */
export default function ModelTruthPanel(props: TruthDeps) {
  const getReadinessFn = props.getReadinessFn ?? getReadiness;
  const getModelInfoFn = props.getModelInfoFn ?? getModelInfo;
  const getSupportedCropsFn = props.getSupportedCropsFn ?? getSupportedCrops;

  const [ready, setReady] = useState<boolean | null>(null);
  const [info, setInfo] = useState<ModelInfo | null>(null);
  const [truth, setTruth] = useState<SupportedCrops | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        await getReadinessFn();
        if (!cancelled) setReady(true);
      } catch {
        if (!cancelled) setReady(false);
      }
      try {
        setInfo(await getModelInfoFn());
      } catch (err) {
        if (!cancelled) setError(errorMessage(err));
      }
      try {
        setTruth(await getSupportedCropsFn());
      } catch (err) {
        if (!cancelled) setError((prev) => prev ?? errorMessage(err));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [getReadinessFn, getModelInfoFn, getSupportedCropsFn]);

  const model = info?.model ?? {};
  const modelName = typeof model.name === "string" ? model.name : "—";
  const modelVersion = typeof model.version === "string" ? model.version : "—";
  const modelStatus = typeof model.status === "string" ? model.status : "—";
  const supportedCount =
    truth?.crops.reduce(
      (total, crop) => total + crop.conditions.filter((condition) => condition.supported_by_model).length,
      0,
    ) ?? null;

  return (
    <section className="card" aria-label="Model truth" data-testid="model-truth">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-lg font-bold text-stone-900">Model truth (live from this deployment)</h2>
        <div className="flex flex-wrap items-center gap-2">
          {info?.serving ? (
            <span className={info.serving.weights_origin === "sample" ? "chip-muted" : "chip-high"} data-testid="serving-chip">
              {info.serving.weights_origin === "sample"
                ? "serving: sample model (flagged)"
                : `serving: real model · ${info.serving.weights_origin === "remote-checkpoint" ? "remote (AD-009)" : "local"}`}
            </span>
          ) : null}
          {ready === null ? null : (
            <span className={ready ? "chip-high" : "chip-low"}>{ready ? "API + database ready" : "API not ready"}</span>
          )}
        </div>
      </div>

      {error ? (
        <p className="alert-caution mt-3" role="note">
          {error} Showing nothing beyond that — the UI never fills in assumed values.
        </p>
      ) : null}

      <dl className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div>
          <dt className="field-label">Model</dt>
          <dd className="mt-1 font-semibold text-stone-900">
            {modelName} · v{modelVersion}
          </dd>
          <dd className="text-xs text-stone-500">status: {modelStatus}</dd>
        </div>
        <div>
          <dt className="field-label">Confidence bands</dt>
          <dd className="mt-1 font-semibold text-stone-900">
            {info
              ? `HIGH ≥ ${info.confidence_bands.high} · MEDIUM ≥ ${info.confidence_bands.medium} · LOW ≥ ${info.confidence_bands.low}`
              : "—"}
          </dd>
          <dd className="text-xs text-stone-500">below LOW → INCONCLUSIVE, we abstain</dd>
        </div>
        <div>
          <dt className="field-label">Crop coverage</dt>
          <dd className="mt-1 font-semibold text-stone-900">
            {truth ? `${truth.crop_count} crops · ${supportedCount} conditions` : "—"}
          </dd>
          <dd className="text-xs text-stone-500">
            taxonomy v{truth?.taxonomy_version ?? "—"} · model_available: {String(truth?.model_available ?? false)}
          </dd>
        </div>
        <div>
          <dt className="field-label">Uncertainty / severity</dt>
          <dd className="mt-1 font-semibold text-stone-900">
            {info?.uncertainty_method ?? "—"}
          </dd>
          <dd className="text-xs text-stone-500">severity: {info?.severity_method ?? "—"}</dd>
        </div>
      </dl>

      {info?.serving?.weights_origin === "sample" ? (
        <p className="alert-caution mt-4" role="note" data-testid="serving-notice">
          This deployment serves the clearly-flagged synthetic sample model ({info.serving.weights_state}) — every
          prediction is stamped <code>demo: true</code> and is plumbing evidence, never field performance. The real
          checkpoint can be wired into this same deployment without any code change (AD-009, operator steps in
          docs/12 §8).
        </p>
      ) : info?.serving ? (
        <p className="alert-caution mt-4" role="note" data-testid="serving-notice">
          This deployment serves the real {modelName} v{modelVersion} (
          {info.serving.weights_origin === "remote-checkpoint"
            ? `delivered out-of-band, ${info.serving.integrity}`
            : "operator-local checkpoint"}
          ). In-domain held-out top-1 {info.evaluation?.in_domain_top1 ?? "—"} and{" "}
          {info.evaluation?.out_of_domain_dataset ?? "PlantDoc"} field OOD top-1{" "}
          {info.evaluation?.out_of_domain_top1 ?? "—"} are always quoted together — field images differ from lab
          images, and every prediction still requires human verification.
        </p>
      ) : truth?.model_available === false ? (
        <p className="alert-caution mt-4" role="note" data-testid="serving-notice">
          The production model is not wired into this deployment yet — analyses run against the clearly-flagged
          synthetic sample model and every prediction is stamped <code>demo: true</code>. In-domain and
          out-of-distribution evaluation numbers live on the Model information page.
        </p>
      ) : null}

      {info ? <p className="mt-3 text-xs leading-5 text-stone-500">{info.client_notice}</p> : null}
    </section>
  );
}
