import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import ReportCard from "@/components/ReportCard";
import { API_BASE } from "@/lib/api";
import type { ReportPayload } from "@/lib/types";

/** Fixture mirrors the stored Phase 9 backend payload (Suspected case, one PENDING zone). */
const REPORT: ReportPayload = {
  id: "rpt-uuid-1",
  report_id: "CMA-20260809-AB12CD",
  analysis_id: "ana-uuid-1",
  generated_at: "2026-08-09T12:00:00+00:00",
  demo: true,
  generator: { name: "reportlab", feature: "field-report", version: "1" },
  download_url: "/reports/rpt-uuid-1/download",
  hint: "the PDF file is the artifact of record (files win); this payload is a snapshot of its build basis",
  basis: {
    analysis_id: "ana-uuid-1",
    analysis_status: "COMPLETED",
    demo: true,
    generated_at_utc: "2026-08-09T12:00:00+00:00",
    prediction: {
      phrasing: "Suspected corn - Northern Leaf Blight - 92% confidence",
      status: "SUSPECTED",
      crop: "corn",
      condition: "corn_northern_leaf_blight",
      condition_name: "Northern Leaf Blight",
      confidence: 0.9231,
      band: "HIGH",
      uncertainty: 0.21,
      severity: 0.18,
      severity_label: "Estimated visual severity",
      latency_ms: 101.5,
      limitation_notice: "Decision support only - not a definitive diagnosis.",
      explainability_caveat: "Highlighted regions contribute strongly; not a disease-location guarantee.",
    },
    model: { name: "cropmind-leaf-classifier", version: "0.1.0", dataset_version: "mendeley-v1", demo: true },
    image: { id: "img-1", captured_at: null, width: 64, height: 48, source_type: "SMARTPHONE", sha256_12: "1c2d2410bcd9" },
    field: null,
    zones: [
      {
        id: "zone-1",
        risk_level: "HIGH",
        condition: "Northern Leaf Blight",
        confidence: 0.9231,
        severity: 0.18,
        review_status: "PENDING",
        review_note: null,
        reviewed_at: null,
        coordinate_space: "image-normalized-xyxy",
        georeference_source: "none",
      },
    ],
    zone_review_totals: { PENDING: 1, APPROVED: 0, REJECTED: 0 },
  },
};

describe("ReportCard (stored-report honesty preview)", () => {
  it("shows the human report ID and the verbatim Suspected phrasing", () => {
    render(<ReportCard report={REPORT} />);
    expect(screen.getByText("CMA-20260809-AB12CD")).toBeInTheDocument();
    expect(screen.getByText("Suspected corn - Northern Leaf Blight - 92% confidence")).toBeInTheDocument();
    expect(screen.getByText("SUSPECTED — verify before acting")).toBeInTheDocument();
  });

  it("flags demo reports — never silent", () => {
    render(<ReportCard report={REPORT} />);
    expect(screen.getByText("DEMO MODEL")).toBeInTheDocument();
  });

  it("renders the zone review ledger exactly as stored (never re-derived)", () => {
    render(<ReportCard report={REPORT} />);
    expect(screen.getByText(/1 pending · 0 approved ·\s*0 rejected/)).toBeInTheDocument();
    expect(screen.getByText("1 zone(s) on the report")).toBeInTheDocument();
  });

  it("states 'no field link' instead of inventing one", () => {
    render(<ReportCard report={REPORT} />);
    expect(screen.getByText(/analysed without a field link/)).toBeInTheDocument();
  });

  it("download goes through the authenticated blob path with the report's own filename", async () => {
    // Regression: a bare anchor navigation carries no session token, so owner-scoped
    // reports answered the by-design 404. The card must download via the injected fn.
    const download = vi.fn().mockResolvedValue(undefined);
    render(<ReportCard report={REPORT} downloadFn={download} />);
    fireEvent.click(screen.getByRole("button", { name: /download pdf report/i }));
    await waitFor(() =>
      expect(download).toHaveBeenCalledWith(
        `${API_BASE}/reports/rpt-uuid-1/download`,
        "cropmind-field-report-CMA-20260809-AB12CD.pdf"
      )
    );
  });

  it("download failure is visible, never silent", async () => {
    const download = vi.fn().mockRejectedValue(new Error("404 report not found"));
    render(<ReportCard report={REPORT} downloadFn={download} />);
    fireEvent.click(screen.getByRole("button", { name: /download pdf report/i }));
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent(/download failed/i));
  });

  it("INCONCLUSIVE reports render as abstentions, not findings", () => {
    const inconclusive: ReportPayload = {
      ...REPORT,
      basis: {
        ...REPORT.basis!,
        prediction: { ...REPORT.basis!.prediction, status: "INCONCLUSIVE", phrasing: "INCONCLUSIVE - below the confidence threshold" },
        zones: [],
        zone_review_totals: { PENDING: 0, APPROVED: 0, REJECTED: 0 },
      },
    };
    render(<ReportCard report={inconclusive} />);
    expect(screen.getByText("INCONCLUSIVE — retake photo")).toBeInTheDocument();
    expect(screen.getByText("— (abstained)")).toBeInTheDocument();
    expect(screen.getByText("no zones — abstention by design")).toBeInTheDocument();
    expect(screen.getByText(/below confidence threshold/)).toBeInTheDocument();
  });
});
