/**
 * Phase 15 (FR-20) regression: the anonymous verdict page must render end-to-end.
 *
 * Root cause pinned against production 2026-09-28: every read endpoint on the
 * verdict page serves the flagged demo path anonymously (analysis, prediction,
 * imagery, Grad-CAM, zones, report — all verified 200), but FeedbackPanel's
 * mount-time `GET /analyses/{id}/feedback` is account-only by design (401), and
 * the shared wrapper redirected ANY 401 to /login — so a demo visitor who
 * finished an analysis could never see their own verdict page.
 */
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}));

vi.mock("@/components/AuthedImage", () => ({
  default: (props: { url: string; alt: string }) => <span data-testid="authed-image" data-url={props.url} />,
}));
vi.mock("@/components/ReportPanel", () => ({
  default: () => <div data-testid="report-panel-stub" />,
}));
vi.mock("@/components/FeedbackPanel", () => ({
  default: () => <div data-testid="feedback-panel-stub" />,
}));

import AnalysisView from "@/components/AnalysisView";
import { saveSession } from "@/lib/auth";
import type { AnalysisStatus, Prediction } from "@/lib/types";

const STATUS: AnalysisStatus = {
  analysis_id: "ana-1",
  image_id: "img-1",
  status: "COMPLETED",
  demo: true,
  created_at: "2026-09-28T10:00:00+00:00",
  started_at: null,
  completed_at: "2026-09-28T10:00:30+00:00",
  error: null,
  job: { id: "job-1", status: "COMPLETED", attempts: 1, max_attempts: 3 },
};

const PREDICTION: Prediction = {
  prediction_id: "p-1",
  analysis_id: "ana-1",
  status: "SUSPECTED",
  phrasing: "Suspected Tomato - Early blight - 91% confidence",
  crop: "Tomato",
  condition: { disease_id: "tomato_early_blight", name: "Early blight" },
  confidence: 0.91,
  band: "HIGH",
  uncertainty: 0.18,
  estimated_visual_severity: 0.1,
  severity_label: "Estimated visual severity",
  latency_ms: 1699,
  demo: false,
  model: { name: "cropmind-leaf-classifier", version: "0.1.0", dataset_version: "plantvillage@v1", threshold_version: "0.1", demo: false },
  regions: [],
  limitation_notice: "Decision support only - not a definitive diagnosis.",
  explainability_caveat: "Highlighted regions contribute strongly; not a disease-location guarantee.",
} as unknown as Prediction;

function saveLiveSession() {
  const header = btoa(JSON.stringify({ alg: "HS256", typ: "JWT" }));
  const payload = btoa(
    JSON.stringify({ sub: "u1", role: "FARMER", jti: "j1", exp: Math.floor(Date.now() / 1000) + 3600 }),
  );
  saveSession({
    access_token: `${header}.${payload}.testsig`,
    expires_at: new Date(Date.now() + 3_600_000).toISOString(),
    user: { id: "u1", email: "farmer@example.test", role: "FARMER", created_at: null },
  });
}

function deps() {
  return {
    getAnalysisFn: vi.fn().mockResolvedValue(STATUS),
    getPredictionForAnalysisFn: vi.fn().mockResolvedValue(PREDICTION),
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  window.localStorage.clear();
});

describe("AnalysisView anonymous verdict page", () => {
  it("renders the full verdict anonymously — imagery included, feedback nudged to sign-in, NO panel mounted", async () => {
    render(<AnalysisView analysisId="ana-1" {...deps()} />);

    expect(await screen.findByText(/Suspected Tomato - Early blight - 91% confidence/)).toBeInTheDocument();
    expect(screen.getByTestId("report-panel-stub")).toBeInTheDocument();
    // feedback is an account-scoped affordance: nudge, never a mount (mount ⇒ 401 ⇒ redirect)
    expect(screen.queryByTestId("feedback-panel-stub")).not.toBeInTheDocument();
    const nudge = screen.getByTestId("feedback-signin-nudge");
    expect(nudge).toHaveTextContent(/needs an account/);
    expect(screen.getByRole("link", { name: /Sign in to leave feedback/ })).toHaveAttribute(
      "href",
      "/login?next=/analyses/ana-1",
    );
    // stored imagery still loads on the demo path
    expect(screen.getAllByTestId("authed-image").length).toBeGreaterThanOrEqual(1);
  });

  it("signed-in sessions get the real feedback panel", async () => {
    saveLiveSession();
    render(<AnalysisView analysisId="ana-1" {...deps()} />);
    expect(await screen.findByText(/Suspected Tomato - Early blight - 91% confidence/)).toBeInTheDocument();
    expect(screen.getByTestId("feedback-panel-stub")).toBeInTheDocument();
    expect(screen.queryByTestId("feedback-signin-nudge")).not.toBeInTheDocument();
  });
});
