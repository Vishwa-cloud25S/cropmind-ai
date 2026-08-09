import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ZonesPanel from "@/components/ZonesPanel";
import { API_BASE } from "@/lib/api";
import type { DecisionSupport, InterventionZone } from "@/lib/types";

vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}));

const ZONE: InterventionZone = {
  id: "zone-1",
  analysis_id: "ana-9",
  field_id: "field-3",
  image_id: "img-7",
  geometry: {
    type: "Polygon",
    coordinate_space: "image-normalized-xyxy",
    coordinates: [[[0.25, 0.25], [0.8, 0.25], [0.8, 1], [0.25, 1], [0.25, 0.25]]],
  },
  condition: "Early blight",
  confidence: 0.71,
  severity: 0.31,
  risk_level: "HIGH",
  risk_basis: "from band MEDIUM, visual severity 0.31 (proxy)",
  review_priority: 2,
  review_priority_note: "review this week",
  review_status: "PENDING",
  review_note: null,
  reviewed_at: null,
  georeference_source: "none",
  est_area_ha: null,
  area_note: "area unknown in hectares — observation is not georeferenced (image-space evidence only)",
  simulation_label: "precision intervention zone simulation",
  created_at: "2026-08-09T10:00:00+00:00",
};

const SUPPORT: DecisionSupport = {
  risk_counts: { LOW: 0, MEDIUM: 0, HIGH: 1, CRITICAL: 0 },
  review_counts: { PENDING: 1, APPROVED: 0, REJECTED: 0 },
  pending_zone_count: 1,
  first_priority_zone_ids: ["zone-1"],
  note: "Rule-based triage from stored risk levels — review order, not an agronomic risk score.",
  simulation_label: "precision intervention zone simulation",
};

beforeEach(() => {
  vi.clearAllMocks();
});

describe("ZonesPanel (honesty surface)", () => {
  it("shows simulation labels, honest georeference and area notes on every zone", () => {
    render(<ZonesPanel zones={[ZONE]} decisionSupport={SUPPORT} fieldId="field-3" />);
    expect(screen.getAllByText(/precision intervention zone simulation/).length).toBeGreaterThan(0);
    expect(screen.getByText(/georeference:/)).toHaveTextContent("georeference: none");
    expect(screen.getByText(/image-normalized-xyxy/)).toBeInTheDocument();
    expect(screen.getByText(/not georeferenced \(image-space evidence only\)/)).toBeInTheDocument();
    expect(screen.getByText("HIGH risk")).toBeInTheDocument(); // text always accompanies colour
    expect(screen.getByText("PENDING review")).toBeInTheDocument();
  });

  it("renders the rule-based decision strip — never a fake agronomic risk score", () => {
    render(<ZonesPanel zones={[ZONE]} decisionSupport={SUPPORT} fieldId="field-3" />);
    expect(screen.getByText(/not an agronomic risk score/)).toBeInTheDocument();
    expect(screen.getByText("review first")).toBeInTheDocument(); // top-priority zone highlighted
  });

  it("calls the review API on approve and lets the parent re-read", async () => {
    const reviewZoneFn = vi.fn().mockResolvedValue({ zone: { ...ZONE, review_status: "APPROVED" } });
    const onChanged = vi.fn();
    const user = userEvent.setup();
    render(<ZonesPanel zones={[ZONE]} decisionSupport={SUPPORT} fieldId="field-3" reviewZoneFn={reviewZoneFn} onChanged={onChanged} />);

    await user.click(screen.getByRole("button", { name: "Approve" }));
    expect(reviewZoneFn).toHaveBeenCalledWith("zone-1", { review_status: "APPROVED" });
    expect(onChanged).toHaveBeenCalled();
  });

  it("surfaces a review failure instead of pretending", async () => {
    const reviewZoneFn = vi.fn().mockRejectedValue(new Error("network down"));
    const user = userEvent.setup();
    render(<ZonesPanel zones={[ZONE]} decisionSupport={SUPPORT} fieldId="field-3" reviewZoneFn={reviewZoneFn} />);

    await user.click(screen.getByRole("button", { name: "Reject" }));
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("network down");
  });

  it("points both export buttons at the labelled download endpoints", () => {
    render(<ZonesPanel zones={[ZONE]} decisionSupport={SUPPORT} fieldId="field-3" />);
    expect(screen.getByRole("link", { name: "Export GeoJSON" })).toHaveAttribute(
      "href",
      `${API_BASE}/intervention-zones/export?field_id=field-3&format=geojson`,
    );
    expect(screen.getByRole("link", { name: "Export CSV" })).toHaveAttribute(
      "href",
      `${API_BASE}/intervention-zones/export?field_id=field-3&format=csv`,
    );
  });

  it("states the abstention rule when there are no zones", () => {
    render(<ZonesPanel zones={[]} decisionSupport={{ ...SUPPORT, pending_zone_count: 0, first_priority_zone_ids: [] }} fieldId="field-3" />);
    expect(screen.getByText(/abstains on INCONCLUSIVE analyses/)).toBeInTheDocument();
  });
});
