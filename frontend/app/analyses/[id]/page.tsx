import type { Metadata } from "next";

import AnalysisView from "@/components/AnalysisView";

export const metadata: Metadata = {
  title: "Analysis",
  description: "One analysis, completely traceable: phrasing, bands, Grad-CAM, regions, model identity, raw contract.",
};

export default function AnalysisPage({ params }: { params: { id: string } }) {
  return (
    <div className="container-shell max-w-4xl py-10">
      <AnalysisView analysisId={params.id} />
    </div>
  );
}
