/**
 * Phase 14 (AD-009): the ModelTruthPanel derives every "sample vs real" label
 * from the live /model-info `serving` block — never from hardcoded copy.
 * Pinned: sample stays flagged; real weights always carry BOTH evaluation figures.
 */
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import ModelTruthPanel from "@/components/ModelTruthPanel";
import type { ModelInfo, ServingInfo, SupportedCrops } from "@/lib/types";

const TRUTH: SupportedCrops = {
  taxonomy_version: "0.3",
  updated: "2026-08-11",
  model_available: true,
  note: "",
  crop_count: 4,
  crops: [],
  disclaimer: "",
};

const serving = (origin: ServingInfo["weights_origin"], state = "present"): ServingInfo => ({
  weights_origin: origin,
  demo_mode: true,
  weights_state: state,
  source_host: origin === "remote-checkpoint" ? "huggingface.co" : null,
  integrity: "sha256-pinned",
  label_rule: "labels derive from this block",
});

const info = (s: ServingInfo | undefined): ModelInfo => ({
  model: { name: "cropmind-leaf-classifier", version: "0.1.0", status: "PROMOTED" },
  confidence_bands: { high: 0.6, medium: 0.45, low: 0.25 },
  uncertainty_method: "predictive_entropy",
  severity_method: "heatmap_area_ratio",
  updated: "2026-08-11",
  registry_note: "",
  client_notice: "notice",
  serving: s,
  evaluation: { in_domain_top1: 0.9959, out_of_domain_top1: 0.2349, out_of_domain_dataset: "plantdoc", rule: "pair" },
});

const deps = (s: ServingInfo | undefined) => ({
  getReadinessFn: vi.fn().mockResolvedValue({ status: "ready" }),
  getModelInfoFn: vi.fn().mockResolvedValue(info(s)),
  getSupportedCropsFn: vi.fn().mockResolvedValue(TRUTH),
});

describe("ModelTruthPanel serving derivation (AD-009)", () => {
  it("flags the sample model honestly when the deployment serves sample weights", async () => {
    render(<ModelTruthPanel {...deps(serving("sample", "generated-on-first-analysis"))} />);
    const notice = await screen.findByTestId("serving-notice");
    expect(notice).toHaveTextContent("synthetic sample model");
    expect(notice).toHaveTextContent("generated-on-first-analysis");
    expect(notice).toHaveTextContent("plumbing evidence");
    expect(screen.getByTestId("serving-chip")).toHaveTextContent("serving: sample model (flagged)");
  });

  it("names the real model and always quotes both evaluation figures together", async () => {
    render(<ModelTruthPanel {...deps(serving("remote-checkpoint", "downloaded"))} />);
    const notice = await screen.findByTestId("serving-notice");
    expect(notice).toHaveTextContent("real cropmind-leaf-classifier v0.1.0");
    expect(notice).toHaveTextContent("0.9959");
    expect(notice).toHaveTextContent("0.2349");
    expect(notice).toHaveTextContent("quoted together");
    expect(notice).not.toHaveTextContent("synthetic sample model");
    expect(screen.getByTestId("serving-chip")).toHaveTextContent("serving: real model · remote (AD-009)");
  });

  it("shows the operator-local origin without remote wording", async () => {
    render(<ModelTruthPanel {...deps(serving("local-checkpoint"))} />);
    const notice = await screen.findByTestId("serving-notice");
    expect(notice).toHaveTextContent("operator-local checkpoint");
    expect(screen.getByTestId("serving-chip")).toHaveTextContent("serving: real model · local");
  });

  it("keeps the legacy fallback when the API has no serving block", async () => {
    render(
      <ModelTruthPanel
        {...deps(undefined)}
        getSupportedCropsFn={vi.fn().mockResolvedValue({ ...TRUTH, model_available: false })}
      />,
    );
    const notice = await screen.findByTestId("serving-notice");
    expect(notice).toHaveTextContent("production model is not wired");
  });
});
