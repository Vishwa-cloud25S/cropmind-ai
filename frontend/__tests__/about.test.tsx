/**
 * About page (Phase 14): the founder is named, the honesty rules are stated,
 * and every verification path points at the public repository — no marketing
 * claims that the repo cannot back.
 */
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import AboutPage from "@/app/about/page";

describe("About page", () => {
  it("names the founder and states the solo open-source build honestly", () => {
    render(<AboutPage />);
    expect(screen.getByText(/Vishwa Odduri/)).toBeInTheDocument();
    expect(screen.getByText(/independent solo founder/)).toBeInTheDocument();
  });

  it("carries the honesty rules, including the published OOD shortfall", () => {
    render(<AboutPage />);
    expect(screen.getByText(/Suspected, never certain/)).toBeInTheDocument();
    expect(screen.getByText(/0.2349 PlantDoc field OOD/)).toBeInTheDocument();
    expect(screen.getByText(/No chemical advice, anywhere/)).toBeInTheDocument();
    expect(screen.getByText(/Demo means demo/)).toBeInTheDocument();
  });

  it("points verification at the public repository", () => {
    render(<AboutPage />);
    const links = screen.getAllByRole("link");
    const hrefs = links.map((link) => link.getAttribute("href") ?? "");
    expect(hrefs).toContain("https://github.com/Vishwa-cloud25S/cropmind-ai");
    expect(hrefs).toContain("https://github.com/Vishwa-cloud25S/cropmind-ai/issues");
  });
});
