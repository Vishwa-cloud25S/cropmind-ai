/**
 * Phase 15 (FR-20) regression: the no-account demo flow must never bounce to /login.
 *
 * Root cause found via live capture 2026-09-28: components fetched account-scoped
 * endpoints on mount, the shared wrapper's `handleUnauthorized()` redirected any 401
 * to /login — so "Try the Demo" and /analyze were unreachable anonymously.
 * These tests pin the gate: anonymous ⇒ demo=true reads, account scopes untouched.
 */
import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}));

vi.mock("@/components/ModelTruthPanel", () => ({
  default: () => <div data-testid="model-truth-stub" />,
}));

import DashboardView from "@/components/DashboardView";
import HistoryTable from "@/components/HistoryTable";
import { saveSession } from "@/lib/auth";

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

beforeEach(() => {
  vi.clearAllMocks();
  window.localStorage.clear();
});

describe("DashboardView demo-path gating", () => {
  const farmsList = { count: 2, farms: [
    { id: "f1", name: "A", location: null, field_count: 3, created_at: null },
    { id: "f2", name: "B", location: null, field_count: 1, created_at: null },
  ] };
  const analysesList = { count: 7, analyses: [] };

  it("anonymous: farms untouched (account scope), analyses fetched with demo=true", async () => {
    const listFarmsFn = vi.fn().mockResolvedValue(farmsList);
    const listAnalysesFn = vi.fn().mockResolvedValue(analysesList);
    // HistoryTable is rendered inside DashboardView with the REAL listAnalyses — give
    // it a benign stub fetch so the assertion surface stays on the dashboard effect.
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true, status: 200,
      json: async () => analysesList,
      headers: new Headers({ "content-type": "application/json" }),
    }));

    render(<DashboardView listFarmsFn={listFarmsFn} listAnalysesFn={listAnalysesFn} />);

    await waitFor(() => expect(listAnalysesFn).toHaveBeenCalled());
    expect(listAnalysesFn).toHaveBeenCalledWith({ limit: 100, demo: true });
    expect(listFarmsFn).not.toHaveBeenCalled();
    expect(await screen.findByText("7")).toBeInTheDocument();
    vi.unstubAllGlobals();
  });

  it("signed in: farms counted, analyses without the demo flag", async () => {
    saveLiveSession();
    const listFarmsFn = vi.fn().mockResolvedValue(farmsList);
    const listAnalysesFn = vi.fn().mockResolvedValue(analysesList);

    render(<DashboardView listFarmsFn={listFarmsFn} listAnalysesFn={listAnalysesFn} />);

    await waitFor(() => expect(listAnalysesFn).toHaveBeenCalled());
    expect(listFarmsFn).toHaveBeenCalled();
    expect(listAnalysesFn).toHaveBeenCalledWith({ limit: 100, demo: undefined });
    expect(await screen.findByText("2")).toBeInTheDocument(); // farm count
    expect(screen.getByText("4")).toBeInTheDocument(); // 3+1 fields
  });
});

describe("HistoryTable demo-path gating", () => {
  const analysesList = { count: 0, analyses: [] };

  it("anonymous: refresh carries demo=true (shared flagged history, no redirect)", async () => {
    const listAnalysesFn = vi.fn().mockResolvedValue(analysesList);
    render(<HistoryTable listAnalysesFn={listAnalysesFn} />);
    await screen.findByTestId("history-table");
    await waitFor(() =>
      expect(listAnalysesFn).toHaveBeenCalledWith({ limit: 20, status: undefined, demo: true }),
    );
  });

  it("signed in: refresh carries no demo flag", async () => {
    saveLiveSession();
    const listAnalysesFn = vi.fn().mockResolvedValue(analysesList);
    render(<HistoryTable listAnalysesFn={listAnalysesFn} />);
    await screen.findByTestId("history-table");
    await waitFor(() =>
      expect(listAnalysesFn).toHaveBeenCalledWith({ limit: 20, status: undefined, demo: undefined }),
    );
  });
});
