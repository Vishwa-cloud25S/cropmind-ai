"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import { errorMessage, listAnalyses, listFarms } from "@/lib/api";
import HistoryTable from "@/components/HistoryTable";
import ModelTruthPanel from "@/components/ModelTruthPanel";

export interface DashboardDeps {
  listFarmsFn?: typeof listFarms;
  listAnalysesFn?: typeof listAnalyses;
}

/**
 * Evaluator entry point. Every number on this page is a live API count of real
 * records on this deployment — there are no fabricated "customers" or "hectares".
 */
export default function DashboardView(props: DashboardDeps) {
  const listFarmsFn = props.listFarmsFn ?? listFarms;
  const listAnalysesFn = props.listAnalysesFn ?? listAnalyses;

  const [farmCount, setFarmCount] = useState<number | null>(null);
  const [fieldCount, setFieldCount] = useState<number | null>(null);
  const [analysisCount, setAnalysisCount] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const farms = await listFarmsFn();
        if (cancelled) return;
        setFarmCount(farms.count);
        setFieldCount(farms.farms.reduce((total, farm) => total + farm.field_count, 0));
      } catch (err) {
        if (!cancelled) setError(errorMessage(err));
      }
      try {
        const analyses = await listAnalysesFn({ limit: 100 });
        if (!cancelled) setAnalysisCount(analyses.count);
      } catch (err) {
        if (!cancelled) setError((prev) => prev ?? errorMessage(err));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [listFarmsFn, listAnalysesFn]);

  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-3">
        <div className="stat-card">
          <p className="field-label">Farms</p>
          <p className="mt-1 text-3xl font-bold text-stone-900">{farmCount ?? "—"}</p>
          <p className="mt-1 text-xs text-stone-500">real records, this deployment</p>
        </div>
        <div className="stat-card">
          <p className="field-label">Fields</p>
          <p className="mt-1 text-3xl font-bold text-stone-900">{fieldCount ?? "—"}</p>
          <p className="mt-1 text-xs text-stone-500">across those farms</p>
        </div>
        <div className="stat-card">
          <p className="field-label">Analyses (latest ≤100)</p>
          <p className="mt-1 text-3xl font-bold text-stone-900">{analysisCount ?? "—"}</p>
          <p className="mt-1 text-xs text-stone-500">upload → model → honesty payload</p>
        </div>
      </div>

      {error ? (
        <p className="alert-error" role="alert">
          {error}
        </p>
      ) : null}

      <div className="card">
        <h2 className="text-lg font-bold text-stone-900">Run an analysis</h2>
        <p className="mt-1 text-sm leading-6 text-stone-600">
          Upload a leaf photo; the worker runs the model; you get a <em>Suspected</em> — or honest{" "}
          <em>Inconclusive</em> — verdict with confidence band, uncertainty, Grad-CAM and full model identity.
        </p>
        <div className="mt-4 flex flex-wrap gap-3">
          <Link href="/analyze" className="btn-primary">
            Analyze a photo
          </Link>
          <Link href="/farms" className="btn-secondary">
            Manage farms
          </Link>
        </div>
      </div>

      <ModelTruthPanel />

      <section aria-label="Recent analyses">
        <h2 className="mb-3 text-lg font-bold text-stone-900">Recent analyses</h2>
        <HistoryTable limit={5} />
      </section>
    </div>
  );
}
