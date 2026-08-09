import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import SprayResultCard from "@/components/SprayResultCard";
import { API_BASE } from "@/lib/api";
import type { SprayResults } from "@/lib/types";

/** Fixture mirrors the stored Phase 8 engine payload for the half-field case. */
const RESULTS: SprayResults = {
  field_area_ha: 1.0038,
  treated_area_ha: 0.5019,
  untreated_area_ha: 0.5019,
  treated_fraction: 0.5,
  swath_count: 4,
  spray_on_length_m: 200.4,
  route_length_m: 476.0,
  est_time_s: 107.2,
  blanket_volume_l: 200.8,
  precision_volume_l: 100.4,
  savings_volume_l: 100.4,
  savings_pct: 50.0,
  route_geojson: { type: "FeatureCollection", simulation: "precision input-application simulation", features: [] },
  simulation_label: "precision input-application simulation",
  assumptions: [
    "Planar equirectangular projection anchored at the field centroid (area error << 1% for fields up to a few km)",
    "The rate is whatever you declared — the simulator never suggests products, chemicals or doses",
  ],
  provider_receipt: {
    provider: "simulated-drone-v1",
    mission_id: "SIM-ab12cd34",
    status: "ACCEPTED-SIMULATED",
    note: "simulated provider — no aircraft exists; this records intent only",
  },
  engine: { package: "simulation", version: "0.1.0" },
  honesty_notice: "SIMULATION: area × declared-rate arithmetic only — no product, chemical or dosage guidance exists in this output",
};

describe("SprayResultCard (SIMULATION honesty surface)", () => {
  it("is unmistakably labelled a simulation", () => {
    render(<SprayResultCard results={RESULTS} simulationId="sim-1" />);
    expect(screen.getByText("SIMULATION")).toBeInTheDocument();
    expect(screen.getAllByText("precision input-application simulation").length).toBeGreaterThan(0);
    expect(screen.getByText(/planning illustration, not a field guarantee/)).toBeInTheDocument();
    expect(screen.getByText(/no product, chemical or dosage guidance/)).toBeInTheDocument();
  });

  it("echoes the engine's assumptions verbatim and the provider's no-hardware note", () => {
    render(<SprayResultCard results={RESULTS} simulationId="sim-1" />);
    for (const assumption of RESULTS.assumptions) {
      expect(screen.getByText(assumption)).toBeInTheDocument();
    }
    expect(screen.getByText(/no aircraft exists/)).toBeInTheDocument();
    expect(screen.getByText(/SIM-ab12cd34/)).toBeInTheDocument();
  });

  it("renders the stored numbers as stored (UI never recomputes)", () => {
    render(<SprayResultCard results={RESULTS} simulationId="sim-1" />);
    expect(screen.getByText(/100 L \(50\.0%\)/)).toBeInTheDocument(); // savings, one figure as stored
    expect(screen.getByText(/50\.0% of the drawn boundary/)).toBeInTheDocument();
    expect(screen.getByText(/0\.48 km/)).toBeInTheDocument(); // route length formatted from stored metres
    expect(screen.getByText("4 swaths · spray-on 0.20 km")).toBeInTheDocument();
  });

  it("links to the labelled route download for THIS stored run", () => {
    render(<SprayResultCard results={RESULTS} simulationId="sim-1" />);
    expect(screen.getByRole("link", { name: /Download route/ })).toHaveAttribute(
      "href",
      `${API_BASE}/simulations/sim-1/route.geojson`,
    );
  });
});
