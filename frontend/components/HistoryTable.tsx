"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";

import { errorMessage, listAnalyses } from "@/lib/api";
import type { AnalysisList, AnalysisState } from "@/lib/types";
import { AnalysisStatusChip } from "@/components/StatusBadge";

const FILTERS: { value: "" | AnalysisState; label: string }[] = [
  { value: "", label: "All" },
  { value: "QUEUED", label: "Queued" },
  { value: "PROCESSING", label: "Processing" },
  { value: "COMPLETED", label: "Completed" },
  { value: "FAILED", label: "Failed" },
];

export interface HistoryDeps {
  listAnalysesFn?: typeof listAnalyses;
  limit?: number;
}

function formatWhen(iso: string | null): string {
  if (!iso) return "—";
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? iso : date.toLocaleString();
}

/**
 * Analysis history (docs/04 §3.5): newest-first, status filter, manual refresh.
 * Everything shown comes from the API — nothing is cached or invented client-side.
 */
export default function HistoryTable(props: HistoryDeps) {
  const listAnalysesFn = props.listAnalysesFn ?? listAnalyses;
  const limit = props.limit ?? 20;

  const [statusFilter, setStatusFilter] = useState<"" | AnalysisState>("");
  const [data, setData] = useState<AnalysisList | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await listAnalysesFn({ limit, status: statusFilter || undefined }));
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [listAnalysesFn, limit, statusFilter]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return (
    <div className="card" data-testid="history-table">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Filter by status">
          {FILTERS.map((filter) => (
            <button
              key={filter.label}
              type="button"
              className={statusFilter === filter.value ? "chip-info" : "chip-muted"}
              aria-pressed={statusFilter === filter.value}
              onClick={() => setStatusFilter(filter.value)}
            >
              {filter.label}
            </button>
          ))}
        </div>
        <button type="button" className="btn-ghost" onClick={refresh} disabled={loading}>
          {loading ? "Refreshing…" : "Refresh"}
        </button>
      </div>

      {error ? (
        <p className="alert-error mt-4" role="alert">
          {error}{" "}
          <button type="button" className="font-semibold underline" onClick={refresh}>
            Try again
          </button>
        </p>
      ) : null}

      {!error && data && data.analyses.length === 0 ? (
        <p className="alert-info mt-4" role="note">
          No analyses{statusFilter ? ` with status ${statusFilter}` : ""} yet.{" "}
          <Link href="/analyze" className="link-cta">
            Upload a leaf photo to run one.
          </Link>
        </p>
      ) : null}

      {!error && !data ? (
        <p className="mt-4 text-sm text-stone-500">Loading history…</p>
      ) : null}

      {data && data.analyses.length > 0 ? (
        <>
          <p className="mt-4 text-xs text-stone-500">
            Showing the {data.analyses.length} most recent
            {statusFilter ? ` ${statusFilter.toLowerCase()}` : ""} analyses
            {data.analyses.length === limit ? ` (limit ${limit})` : ""}.
          </p>
          <div className="mt-2 overflow-x-auto">
            <table className="table-basic">
              <thead>
                <tr>
                  <th scope="col">Created</th>
                  <th scope="col">Analysis</th>
                  <th scope="col">Status</th>
                  <th scope="col">Attempts</th>
                  <th scope="col" className="text-right">
                    Open
                  </th>
                </tr>
              </thead>
              <tbody>
                {data.analyses.map((analysis) => (
                  <tr key={analysis.analysis_id}>
                    <td>{formatWhen(analysis.created_at)}</td>
                    <td>
                      <span className="font-mono text-xs">{analysis.analysis_id.slice(0, 8)}…</span>
                    </td>
                    <td>
                      <AnalysisStatusChip status={analysis.status} demo={analysis.demo} />
                      {analysis.status === "FAILED" && analysis.error ? (
                        <span className="mt-1 block max-w-xs truncate text-xs text-red-700" title={analysis.error}>
                          {analysis.error}
                        </span>
                      ) : null}
                    </td>
                    <td>
                      {analysis.job ? `${analysis.job.attempts}/${analysis.job.max_attempts}` : "—"}
                    </td>
                    <td className="text-right">
                      <Link href={`/analyses/${analysis.analysis_id}`} className="link-cta">
                        View →
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      ) : null}
    </div>
  );
}
