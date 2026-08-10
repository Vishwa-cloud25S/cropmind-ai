import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import FeedbackPanel from "@/components/FeedbackPanel";
import type { FeedbackList } from "@/lib/types";

const EMPTY_LIST: FeedbackList = { count: 0, feedback: [] };

function deps(overrides: Record<string, unknown> = {}) {
  return {
    listFn: vi.fn(async () => EMPTY_LIST),
    submitFn: vi.fn(async () => ({
      feedback: {
        id: "fb-1",
        analysis_id: "ana-1",
        user_id: "u1",
        correctness: "NO" as const,
        actual_condition: "healthy",
        notes: "looked fine to me",
        image_quality: "GOOD",
        created_at: "2026-08-10T08:00:00+00:00",
      },
      note: "recorded against your account — it informs the data strategy; no automatic retraining happens",
    })),
    ...overrides,
  };
}

describe("FeedbackPanel (per-account verdicts)", () => {
  it("states where feedback goes — data strategy, no automatic retraining", () => {
    render(<FeedbackPanel analysisId="ana-1" {...deps()} />);
    expect(screen.getByText(/informs the data/)).toBeInTheDocument();
    expect(screen.getByText(/retrain anything automatically/)).toBeInTheDocument();
  });

  it("requires a verdict before submit is enabled", () => {
    render(<FeedbackPanel analysisId="ana-1" {...deps()} />);
    const button = screen.getByRole("button", { name: /record verdict/i });
    expect(button).toBeDisabled();
    fireEvent.click(screen.getByText("No — wrong"));
    expect(button).toBeEnabled();
  });

  it("submits the verdict verbatim and shows the backend note after recording", async () => {
    const bag = deps();
    render(<FeedbackPanel analysisId="ana-1" {...bag} />);
    fireEvent.click(screen.getByText("No — wrong"));
    fireEvent.change(screen.getByLabelText(/actual condition/i), { target: { value: "healthy" } });
    fireEvent.change(screen.getByLabelText(/notes/i), { target: { value: "looked fine to me" } });
    fireEvent.click(screen.getByRole("button", { name: /record verdict/i }));
    await waitFor(() => expect(screen.getByText(/recorded against your account/)).toBeInTheDocument());
    expect(bag.submitFn).toHaveBeenCalledWith("ana-1", {
      correctness: "NO",
      actual_condition: "healthy",
      notes: "looked fine to me",
      image_quality: null,
    });
  });

  it("surfaces backend rejection reasons verbatim (e.g. 401 sign-in required)", async () => {
    const bag = deps({
      submitFn: vi.fn(async () => {
        throw new Error("authentication required for this action — sign in first");
      }),
    });
    render(<FeedbackPanel analysisId="ana-1" {...bag} />);
    fireEvent.click(screen.getByText("Yes — correct"));
    fireEvent.click(screen.getByRole("button", { name: /record verdict/i }));
    await waitFor(() =>
      expect(screen.getByText("authentication required for this action — sign in first")).toBeInTheDocument(),
    );
  });
});
