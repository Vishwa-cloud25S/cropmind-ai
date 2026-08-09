import type { Metadata } from "next";

import AnalyzeWizard from "@/components/AnalyzeWizard";

export const metadata: Metadata = {
  title: "Analyze a photo",
  description:
    "Upload a leaf photo; get a Suspected-or-Inconclusive verdict with confidence band, uncertainty and Grad-CAM.",
};

export default function AnalyzePage() {
  return (
    <div className="container-shell max-w-3xl py-10">
      <p className="eyebrow">Decision-support screening</p>
      <h1 className="section-title">Analyze a leaf photo</h1>
      <p className="section-lede">
        The model gives a suspected condition with a confidence band — or abstains with{" "}
        <em>Inconclusive</em> when it is not sure enough. It never gives pesticide or dosage advice.
      </p>
      <div className="mt-8">
        <AnalyzeWizard />
      </div>
    </div>
  );
}
