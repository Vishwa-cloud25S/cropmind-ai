import type { Metadata } from "next";

import HistoryTable from "@/components/HistoryTable";

export const metadata: Metadata = {
  title: "Analysis history",
  description: "Every analysis persisted and auditable — status, attempts, failures included.",
};

export default function AnalysesPage() {
  return (
    <div className="container-shell max-w-5xl py-10">
      <p className="eyebrow">Audit trail</p>
      <h1 className="section-title">Analysis history</h1>
      <p className="section-lede">
        Completed, queued and failed runs alike — failures stay visible, nothing is quietly dropped.
      </p>
      <div className="mt-8">
        <HistoryTable />
      </div>
    </div>
  );
}
