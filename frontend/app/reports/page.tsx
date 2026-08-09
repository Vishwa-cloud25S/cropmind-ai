import type { Metadata } from "next";

import ReportsPanel from "@/components/ReportsPanel";

export const metadata: Metadata = {
  title: "Field reports",
  description:
    "Every stored PDF field report — suspected findings with confidence bands, zone review ledger, model version and limitations, each with a unique report ID.",
};

export default function ReportsPage() {
  return (
    <div className="container-shell max-w-5xl py-10">
      <p className="eyebrow">Audit-ready documents</p>
      <h1 className="section-title">Field reports</h1>
      <p className="section-lede">
        Each report is a stored PDF artifact with a unique ID: the suspected finding verbatim, confidence and
        severity, the intervention-zone review ledger (pending / approved / rejected), model version and
        limitations. Nothing on a report is advice — it is honest evidence for a human reviewer.
      </p>
      <div className="mt-8">
        <ReportsPanel />
      </div>
    </div>
  );
}
