"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import { errorMessage, listReports, reportDownloadUrl } from "@/lib/api";
import type { ReportPayload, ReportList } from "@/lib/types";
import { DemoBadge, PredictionStatusChip } from "@/components/StatusBadge";

export interface ReportsPanelDeps {
  listFn?: typeof listReports;
}

/**
 * /reports history surface: every stored PDF artifact, newest first, with the
 * key facts a reviewer scans for (phrasing, status, zone review ledger). The
 * files remain the artifacts of record — this table only indexes them.
 */
export default function ReportsPanel({ listFn }: ReportsPanelDeps = {}) {
  const list = listFn ?? listReports;
  const [data, setData] = useState<ReportList | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const result = await list({ limit: 50 });
        if (!cancelled) setData(result);
      } catch (err) {
        if (!cancelled) setError(errorMessage(err));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [list]);

  if (error) {
    return (
      <p className="alert-error" role="alert">
        {error}
      </p>
    );
  }
  if (!data) return <p className="text-sm text-stone-500">Loading reports…</p>;
  if (data.count === 0) {
    return (
      <div className="card" role="note">
        <p className="font-semibold text-stone-900">No reports yet</p>
        <p className="mt-1 text-sm text-stone-600">
          Reports are generated from a completed analysis — open one from{" "}
          <Link href="/analyses" className="link-cta">
            analysis history
          </Link>{" "}
          (for a suspected finding, generate intervention zones on the Map page first: the report must carry the
          full review ledger).
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <p className="text-xs text-stone-500">
        {data.total} stored report{data.total === 1 ? "" : "s"} · {data.note}
      </p>
      <div className="card overflow-x-auto p-0">
        <table className="table-basic">
          <caption className="sr-only">Stored PDF field reports with review status</caption>
          <thead>
            <tr>
              <th scope="col">Report</th>
              <th scope="col">Suspected finding</th>
              <th scope="col" className="text-center">Status</th>
              <th scope="col" className="text-center">Zone review</th>
              <th scope="col" className="text-center">Demo</th>
              <th scope="col" className="text-right">Actions</th>
            </tr>
          </thead>
          <tbody>
            {data.reports.map((report) => (
              <ReportRow key={report.id} report={report} />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function ReportRow({ report }: { report: ReportPayload }) {
  const facts = report.key_facts;
  return (
    <tr>
      <td>
        <p className="font-mono text-xs font-semibold text-stone-900">{report.report_id}</p>
        <p className="text-xs text-stone-500">
          {report.generated_at ? new Date(report.generated_at).toLocaleString() : "—"}
        </p>
      </td>
      <td className="max-w-xs">
        <p className="truncate text-sm text-stone-800" title={facts?.prediction_phrasing ?? ""}>
          {facts?.prediction_phrasing ?? "—"}
        </p>
        <Link href={`/analyses/${report.analysis_id}`} className="text-xs text-emerald-800 hover:underline">
          open analysis
        </Link>
      </td>
      <td className="text-center">
        {facts?.prediction_status ? <PredictionStatusChip status={facts.prediction_status as "SUSPECTED" | "INCONCLUSIVE"} /> : "—"}
      </td>
      <td className="text-center">
        {facts ? (
          <span className="text-xs text-stone-700">
            {facts.zones_total === 0
              ? "no zones (abstained)"
              : `${facts.zone_review_totals.PENDING}⧗ ${facts.zone_review_totals.APPROVED}✓ ${facts.zone_review_totals.REJECTED}✕`}
          </span>
        ) : (
          "—"
        )}
      </td>
      <td className="text-center">
        <DemoBadge demo={report.demo} />
      </td>
      <td className="text-right">
        <a href={reportDownloadUrl(report.id)} className="btn-secondary inline-block text-xs" download>
          PDF ↓
        </a>
      </td>
    </tr>
  );
}
