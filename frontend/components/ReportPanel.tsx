"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { ApiError, errorMessage, generateReport, getAnalysisReportView } from "@/lib/api";
import type { AnalysisReportView } from "@/lib/types";
import ReportCard from "@/components/ReportCard";

export interface ReportPanelDeps {
  getViewFn?: typeof getAnalysisReportView;
  generateFn?: typeof generateReport;
}

/**
 * Report lifecycle for one analysis (Phase 9): fetch the 200-always view,
 * render either the GENERATE explanation (+button) or the READY report card.
 * Generation errors surface the backend's verbatim honesty reason (zones not
 * generated yet, prediction not ready, …) — never swallowed, never paraphrased.
 */
export default function ReportPanel({
  analysisId,
  analysisStatus,
  ...props
}: ReportPanelDeps & { analysisId: string; analysisStatus: string }) {
  const getViewFn = props.getViewFn ?? getAnalysisReportView;
  const generateFn = props.generateFn ?? generateReport;

  const [view, setView] = useState<AnalysisReportView | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const completed = analysisStatus === "COMPLETED";

  const refresh = useCallback(async () => {
    try {
      setView(await getViewFn(analysisId));
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        setError("analysis not found");
      } else {
        setError(errorMessage(err));
      }
    }
  }, [analysisId, getViewFn]);

  useEffect(() => {
    if (completed) void refresh();
  }, [completed, refresh]);

  const onGenerate = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      await generateFn(analysisId);
      await refresh();
    } catch (err) {
      setError(errorMessage(err)); // verbatim backend honesty reason (e.g. zones missing)
    } finally {
      setBusy(false);
    }
  }, [analysisId, generateFn, refresh]);

  const body = useMemo(() => {
    if (!completed) {
      return (
        <p className="text-sm text-stone-500">
          A PDF field report becomes available once this analysis completes — it is generated from stored results,
          never drafted early.
        </p>
      );
    }
    if (error) {
      return (
        <p className="alert-error" role="alert">
          {error}{" "}
          <button type="button" className="font-semibold underline" onClick={() => void refresh()}>
            Try again
          </button>
        </p>
      );
    }
    if (!view) return <p className="text-sm text-stone-500">Checking report status…</p>;

    if (view.status === "READY" && view.report) {
      return (
        <div className="space-y-3">
          <ReportCard report={view.report} />
          <div className="flex flex-wrap items-center gap-3">
            <button type="button" className="btn-ghost" onClick={() => void onGenerate()} disabled={busy}>
              {busy ? "Refreshing…" : "Regenerate (refresh review snapshot)"}
            </button>
            <p className="text-xs text-stone-500">
              Regenerating keeps the same report ID and overwrites the stored file with the latest review ledger —
              no stale copies survive.
            </p>
          </div>
        </div>
      );
    }

    return (
      <div className="space-y-3">
        <p className="text-sm text-stone-600">
          {view.why ?? "No report generated yet."} The PDF carries the suspected finding, confidence, severity,
          zone review ledger, model version, limitations and a unique report ID — everything a reviewer needs on
          one page.
        </p>
        <div className="flex items-center gap-3">
          <button type="button" className="btn-primary" onClick={() => void onGenerate()} disabled={busy}>
            {busy ? "Generating…" : "Generate PDF report"}
          </button>
        </div>
      </div>
    );
  }, [completed, error, view, busy, onGenerate, refresh]);

  return (
    <section className="card" aria-label="PDF field report" data-testid="report-panel">
      <h2 className="text-lg font-bold text-stone-900">Field report (PDF)</h2>
      <div className="mt-4">{body}</div>
    </section>
  );
}
