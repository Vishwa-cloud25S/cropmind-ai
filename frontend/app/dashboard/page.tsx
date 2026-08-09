import type { Metadata } from "next";

import DashboardView from "@/components/DashboardView";

export const metadata: Metadata = {
  title: "Dashboard",
  description: "Live overview of the CropMind deployment: real record counts, recent analyses and model truth.",
};

export default function DashboardPage() {
  return (
    <div className="container-shell max-w-5xl py-10">
      <p className="eyebrow">Deployment overview</p>
      <h1 className="section-title">Dashboard</h1>
      <p className="section-lede">
        Everything here is a live count of records on this deployment — no vanity metrics.
      </p>
      <div className="mt-8">
        <DashboardView />
      </div>
    </div>
  );
}
