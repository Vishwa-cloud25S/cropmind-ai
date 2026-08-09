import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import PredictionCard from "@/components/PredictionCard";
import type { Prediction } from "@/lib/types";

/**
 * Fixture mirrors the live-accepted Phase 5 payload (analysis 9d774326):
 * INCONCLUSIVE demo-mode output from the synthetic sample model.
 */
const INCONCLUSIVE: Prediction = {
  prediction_id: "bb1fed82-0ca1-40b6-afd1-4306bbf3cea6",
  analysis_id: "9d774326-82a5-4741-b124-0c4328ef1dae",
  status: "INCONCLUSIVE",
  phrasing:
    "Inconclusive (Tomato - Early blight at 9% is below the LOW band) - retake photo or request agronomist review",
  crop: "tomato",
  condition: { disease_id: "tomato_early_blight", name: "Early blight" },
  confidence: 0.0924,
  band: null,
  uncertainty: 0.9766,
  estimated_visual_severity: 0.31,
  severity_label: "Estimated visual severity",
  latency_ms: 1058,
  demo: true,
  model: {
    name: "cropmind-leaf-classifier",
    version: "0.0.0-sample",
    dataset_version: null,
    threshold_version: "0.1",
    demo: true,
  },
  regions: [
    {
      geometry: {
        type: "Polygon",
        coordinate_space: "image-normalized-xyxy",
        coordinates: [
          [
            [0.25, 0.25],
            [0.8125, 0.25],
            [0.8125, 1],
            [0.25, 1],
            [0.25, 0.25],
          ],
        ],
      },
      area_px: 728064,
      confidence: null,
    },
  ],
  gradcam_available: true,
  created_at: "2026-08-08T18:44:41.249112+00:00",
  analysis_demo_requested: false,
  client_notice:
    "Predictions are decision support requiring human verification. No chemical product or dosage guidance is provided.",
  explainability_caveat:
    "Highlighted regions contributed strongly to the prediction — not a guarantee of disease location.",
  raw: { top_k: [{ disease_id: "tomato_early_blight", score: 0.0924 }] },
};

const SUSPECTED: Prediction = {
  ...INCONCLUSIVE,
  status: "SUSPECTED",
  phrasing: "Suspected Tomato - Early blight - 71% confidence",
  confidence: 0.71,
  band: "MEDIUM",
  uncertainty: 0.21,
  demo: false,
  model: { ...INCONCLUSIVE.model, version: "0.1.0", demo: false, dataset_version: "plantvillage-v1" },
  analysis_demo_requested: true,
};

describe("PredictionCard (honesty contract)", () => {
  it("shows the model module's phrasing verbatim as the heading", () => {
    render(<PredictionCard prediction={INCONCLUSIVE} />);
    const heading = screen.getByRole("heading", { level: 2 });
    expect(heading).toHaveTextContent(INCONCLUSIVE.phrasing);
  });

  it("explains the abstention with the real score when inconclusive", () => {
    render(<PredictionCard prediction={INCONCLUSIVE} />);
    expect(screen.getByText("INCONCLUSIVE — retake photo")).toBeInTheDocument();
    expect(screen.getByText("INCONCLUSIVE — below LOW band")).toBeInTheDocument();
    const explainer = screen.getByText(/Why inconclusive\?/).parentElement as HTMLElement;
    expect(explainer).toHaveTextContent("9.2%");
  });

  it("flags the sample model everywhere it matters", () => {
    render(<PredictionCard prediction={INCONCLUSIVE} />);
    expect(screen.getByText("DEMO MODEL")).toBeInTheDocument();
    expect(screen.getByText(/0\.0\.0-sample/)).toBeInTheDocument();
    expect(screen.getByText(/synthetic sample model/)).toBeInTheDocument();
  });

  it("labels severity as a visual proxy, never an agronomic measurement", () => {
    render(<PredictionCard prediction={INCONCLUSIVE} />);
    expect(screen.getByText("visual proxy — not an agronomic measurement")).toBeInTheDocument();
  });

  it("keeps the raw contract accessible and shows the standing client notice", () => {
    render(<PredictionCard prediction={INCONCLUSIVE} />);
    expect(screen.getByText(/Raw prediction contract/)).toBeInTheDocument();
    expect(
      screen.getByText(/decision support requiring human verification/),
    ).toBeInTheDocument();
  });

  it("renders detected regions with their coordinate space", () => {
    render(<PredictionCard prediction={INCONCLUSIVE} />);
    expect(screen.getByText("image-normalized-xyxy")).toBeInTheDocument();
    expect(screen.getByText(/728,064/)).toBeInTheDocument();
  });

  it("renders the SUSPECTED branch with its band and demo-by-request note", () => {
    render(<PredictionCard prediction={SUSPECTED} />);
    expect(screen.getByText("SUSPECTED — verify before acting")).toBeInTheDocument();
    expect(screen.getByText("MEDIUM confidence")).toBeInTheDocument();
    expect(screen.queryByText(/Why inconclusive\?/)).not.toBeInTheDocument();
    expect(screen.getByText(/demo mode by request/)).toBeInTheDocument();
    const identity = screen.getByRole("table", { name: /model identity/i });
    expect(within(identity).getByText(/plantvillage-v1/)).toBeInTheDocument();
  });
});
