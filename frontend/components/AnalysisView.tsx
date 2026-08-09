"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";

import { ApiError, errorMessage, getAnalysis, getPredictionForAnalysis, gradcamUrl, imageDownloadUrl } from "@/lib/api";
import type { AnalysisStatus, Prediction } from "@/lib/types";
import PredictionCard from "@/components/PredictionCard";
import { AnalysisStatusChip } from "@/components/StatusBadge";

export interface AnalysisViewDeps {
  getAnalysisFn?: typeof getAnalysis;
  getPredictionForAnalysisFn?: typeof getPredictionForAnalysis;
  pollMs?: number;
}

/**
 * One analysis, completely traceable: live status while running, then the full
 * honesty prediction (verbatim phrasing, bands, Grad-CAM with caveat, regions,
 * model identity, raw contract). Prediction payload comes from the stored record.
 */
export default function AnalysisView({ analysisId, ...props }: AnalysisViewDeps & { analysisId: string }) {
  const getAnalysisFn = props.getAnalysisFn ?? getAnalysis;
  const getPredictionForAnalysisFn = props.getPredictionForAnalysisFn ?? getPredictionForAnalysis;
  const pollMs = props.pollMs ?? 2000;

  const [status, setStatus] = useState<AnalysisStatus | null>(null);
  const [prediction, setPrediction] = useState<Prediction | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [missing, setMissing] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPolling = useCallback(() => {
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = null;
  }, []);

  useEffect(() => stopPolling, [stopPolling]);

  const loadPrediction = useCallback(async () => {
    try {
      setPrediction(await getPredictionForAnalysisFn(analysisId));
    } catch (err) {
      // 409 = still racing the worker commit; keep the status visible and retry once.
      if (err instanceof ApiError && err.status === 409) return;
      setError(errorMessage(err));
    }
  }, [getPredictionForAnalysisFn, analysisId]);

  const refreshStatus = useCallback(async () => {
    try {
      const next = await getAnalysisFn(analysisId);
      setStatus(next);
      if (next.status === "COMPLETED") {
        stopPolling();
        await loadPrediction();
      } else if (next.status === "FAILED") {
        stopPolling();
      }
    } catch (err) {
      if (err instanceof ApiError && err.status === 404 && status === null) {
        // Very first fetch racing job commit — retry on the interval instead of failing the page.
        return;
      }
      stopPolling();
      if (err instanceof ApiError && err.status === 404) {
        setMissing(true);
      } else {
        setError(errorMessage(err));
      }
    }
  }, [analysisId, getAnalysisFn, loadPrediction, status, stopPolling]);

  useEffect(() => {
    void refreshStatus();
    pollRef.current = setInterval(() => void refreshStatus(), pollMs);
    return stopPolling;
  }, [refreshStatus, pollMs, stopPolling]);

  useEffect(() => {
    if (status?.status === "COMPLETED" && !prediction) void loadPrediction();
  }, [status?.status, prediction, loadPrediction]);

  if (missing) {
    return (
      <div className="card" role="alert">
        <p className="font-semibold text-stone-900">Analysis not found</p>
        <p className="mt-1 text-sm text-stone-600">
          Note: an <em>image</em> id and an <em>analysis</em> id are different — upload returns an image id, the
          analysis page lives at the analysis id returned when you ran it.{" "}
          <Link href="/analyses" className="link-cta">
            Open analysis history
          </Link>
        </p>
      </div>
    );
  }

  if (error) {
    return (
      <p className="alert-error" role="alert">
        {error}{" "}
        <button
          type="button"
          className="font-semibold underline"
          onClick={() => {
            setError(null);
            void refreshStatus();
          }}
        >
          Try again
        </button>
      </p>
    );
  }

  if (!status) return <p className="text-sm text-stone-500">Loading analysis…</p>;

  return (
    <div className="space-y-6" data-testid="analysis-view">
      <div className="card">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="eyebrow">Analysis</p>
            <h1 className="mt-1 font-mono text-sm text-stone-700">{status.analysis_id}</h1>
            <p className="mt-1 text-xs text-stone-500">
              image {status.image_id.slice(0, 8)}…
              {status.created_at ? ` · created ${new Date(status.created_at).toLocaleString()}` : ""}
            </p>
          </div>
          <AnalysisStatusChip status={status.status} demo={status.demo} />
        </div>

        {status.status === "QUEUED" || status.status === "PROCESSING" ? (
          <p className="alert-info mt-4" role="status" aria-live="polite">
            {status.status === "QUEUED"
              ? "Queued — the ML worker picks this up in a few seconds."
              : "Processing — the model is running on the stored image."}{" "}
            This page updates itself.
          </p>
        ) : null}

        {status.status === "FAILED" ? (
          <div className="alert-error mt-4" role="alert">
            <p className="font-semibold">Analysis failed{status.job ? ` after ${status.job.attempts} attempt${status.job.attempts === 1 ? "" : "s"}` : ""}.</p>
            <p className="mt-1 text-sm">{status.error ?? "The worker recorded no error detail."}</p>
            <p className="mt-2 text-sm">
              <Link href="/analyze" className="link-cta">
                Start a new analysis
              </Link>
            </p>
          </div>
        ) : null}
      </div>

      {prediction ? <PredictionCard prediction={prediction} /> : null}

      {prediction ? (
        <section className="card" aria-label="Imagery">
          <h2 className="text-lg font-bold text-stone-900">Stored imagery</h2>
          <p className="mt-1 text-sm text-stone-600">
            Both images below come from the stored, normalized upload — not from your device. Grad-CAM highlight
            semantics: {prediction.explainability_caveat}
          </p>
          <div className="mt-4 grid gap-4 md:grid-cols-2">
            <figure>
              {/* eslint-disable-next-line @next/next/no-img-element -- dynamic API image URL */}
              <img
                src={imageDownloadUrl(status.image_id)}
                alt="Your stored upload, server-normalized"
                className="w-full rounded-lg border border-stone-200 object-contain"
              />
              <figcaption className="mt-1 text-xs text-stone-500">Stored upload (normalized, EXIF re-orientated)</figcaption>
            </figure>
            <figure>
              {/* eslint-disable-next-line @next/next/no-img-element -- dynamic API image URL */}
              <img
                src={gradcamUrl(analysisId)}
                alt="Grad-CAM overlay: regions that contributed strongly to the machine's prediction"
                className="w-full rounded-lg border border-stone-200 object-contain"
                onError={(event) => {
                  event.currentTarget.closest("figure")?.setAttribute("hidden", "");
                }}
              />
              <figcaption className="mt-1 text-xs text-stone-500">
                Grad-CAM overlay — strong contributors to the prediction, not a disease-location guarantee
              </figcaption>
            </figure>
          </div>
        </section>
      ) : null}
    </div>
  );
}
