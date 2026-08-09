import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AnalysisStatusChip, BandChip, DemoBadge, PredictionStatusChip } from "@/components/StatusBadge";

/** Colour is never the only signal — these tests pin the text that accompanies every chip. */

describe("BandChip", () => {
  it.each([
    ["HIGH", "HIGH confidence"],
    ["MEDIUM", "MEDIUM confidence"],
    ["LOW", "LOW confidence"],
  ] as const)("renders %s with its text label", (band, label) => {
    render(<BandChip band={band} />);
    expect(screen.getByText(label)).toBeInTheDocument();
  });

  it("renders the abstention label for a null band", () => {
    render(<BandChip band={null} />);
    expect(screen.getByText("INCONCLUSIVE — below LOW band")).toBeInTheDocument();
  });
});

describe("PredictionStatusChip", () => {
  it("keeps 'Suspected' visibly provisional", () => {
    render(<PredictionStatusChip status="SUSPECTED" />);
    expect(screen.getByText("SUSPECTED — verify before acting")).toBeInTheDocument();
  });

  it("tells the user what to do when inconclusive", () => {
    render(<PredictionStatusChip status="INCONCLUSIVE" />);
    expect(screen.getByText("INCONCLUSIVE — retake photo")).toBeInTheDocument();
  });
});

describe("AnalysisStatusChip", () => {
  it("renders the status", () => {
    render(<AnalysisStatusChip status="PROCESSING" />);
    expect(screen.getByText("PROCESSING")).toBeInTheDocument();
  });

  it("flags demo analyses", () => {
    render(<AnalysisStatusChip status="COMPLETED" demo />);
    expect(screen.getByText("demo image")).toBeInTheDocument();
  });
});

describe("DemoBadge", () => {
  it("renders only for demo predictions", () => {
    render(<DemoBadge demo />);
    expect(screen.getByText("DEMO MODEL")).toBeInTheDocument();
  });

  it("is silent for real predictions", () => {
    const { container } = render(<DemoBadge demo={false} />);
    expect(container).toBeEmptyDOMElement();
  });
});
