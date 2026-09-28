/**
 * Phase 15 (FR-20): bundled demo sample photos.
 * Pins: manifest completeness/provenance, domain honesty notes, and the wizard
 * path — a picked sample goes through the EXACT same File pipeline as a manual
 * pick (no shortcut plumbing), with its provenance note shown.
 */
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import AnalyzeWizard from "@/components/AnalyzeWizard";
import { ApiError } from "@/lib/api";
import { DEMO_SAMPLES, sampleAssetPath } from "@/lib/demo-samples";

vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}));

describe("demo sample manifest", () => {
  it("ships 3–5 samples, each with provenance and an integrity pin", () => {
    expect(DEMO_SAMPLES.length).toBeGreaterThanOrEqual(3);
    expect(DEMO_SAMPLES.length).toBeLessThanOrEqual(5);
    for (const sample of DEMO_SAMPLES) {
      expect(sample.provenance).toMatch(/PlantVillage|PlantDoc/);
      expect(sample.provenance).toMatch(/CC0|CC BY/);
      expect(sample.sha256_12).toMatch(/^[0-9a-f]{12}$/);
      expect(sample.file).toMatch(/\.jpg$/);
    }
  });

  it("states domain expectations honestly on every sample", () => {
    const all = DEMO_SAMPLES.map((s) => s.honestyNote).join(" ");
    // the domain split is the point of the demo — both must be present
    expect(all).toContain("0.9959");
    expect(all).toContain("0.2349");
    expect(all).toMatch(/abstain|land low/i);
  });
});

describe("AnalyzeWizard bundled samples", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("lists the samples and loads a pick through the same File pipeline", async () => {
    const blob = new Blob([new Uint8Array([0xff, 0xd8, 0xff, 0xe0, 1, 2, 3])], { type: "image/jpeg" });
    // plain-object response: the wizard only needs ok/status/blob() (undici Response
    // brand-checks jsdom Blobs, which is a harness artefact, not product behaviour)
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, status: 200, blob: async () => blob }));
    render(<AnalyzeWizard />);

    const select = screen.getByTestId("sample-select") as HTMLSelectElement;
    expect(select).toBeInTheDocument();
    expect(screen.getByText(/Tomato — Early blight \(in-domain photo\)/)).toBeInTheDocument();

    await userEvent.selectOptions(select, DEMO_SAMPLES[0].id);
    // fetch targeted the static asset path
    await waitFor(() => expect(fetch).toHaveBeenCalledWith(sampleAssetPath(DEMO_SAMPLES[0])));
    // …and the result flows through the SAME Selected:<file> rendering as a manual pick
    await screen.findByText(new RegExp(`Selected: ${DEMO_SAMPLES[0].file}`));
    // provenance + honesty note are shown alongside — never hidden
    expect(screen.getByTestId("sample-provenance")).toHaveTextContent(DEMO_SAMPLES[0].provenance);
    expect(screen.getByTestId("sample-provenance")).toHaveTextContent("0.9959");
  });

  it("reports a failed sample fetch honestly and offers the manual path", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 500, blob: async () => new Blob() }));
    render(<AnalyzeWizard />);
    await userEvent.selectOptions(screen.getByTestId("sample-select"), DEMO_SAMPLES[1].id);
    await screen.findByText(/Could not load the bundled sample \(HTTP 500\)/);
    expect(screen.getByText(/pick your own file instead/)).toBeInTheDocument();
  });

  it("dedupe-409 on a bundled sample triggers exactly one honest in-browser retake", async () => {
    const blob = new Blob([new Uint8Array([0xff, 0xd8, 0xff, 0xe0, 9, 9])], { type: "image/jpeg" });
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, status: 200, blob: async () => blob }));
    // jsdom has no canvas — stub the minimal re-encode surface the wizard uses
    vi.stubGlobal("createImageBitmap", vi.fn().mockResolvedValue({ width: 8, height: 8, close: () => {} }));
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue({ drawImage: () => {} } as never);
    vi.spyOn(HTMLCanvasElement.prototype, "toBlob").mockImplementation(function (cb: BlobCallback) {
      cb(new Blob([new Uint8Array([0xff, 0xd8, 0xff, 0xd9])], { type: "image/jpeg" }));
    });

    const uploadImageFn = vi
      .fn()
      .mockRejectedValueOnce(new ApiError(409, { detail: { detail: "these exact bytes are already stored", deduplicated: true } }))
      .mockResolvedValue({
        image: {
          id: "img-retake-1", field_id: null, sha256: "cd".repeat(32), width: 8, height: 8,
          byte_size: 4, captured_at: null, exif: null, source_type: "upload",
          created_at: "2026-09-28T10:00:00+00:00", deduplicated: false,
        },
      });
    render(<AnalyzeWizard uploadImageFn={uploadImageFn} />);

    await userEvent.selectOptions(screen.getByTestId("sample-select"), DEMO_SAMPLES[0].id);
    await screen.findByText(new RegExp(`Selected: ${DEMO_SAMPLES[0].file}`));
    await userEvent.click(screen.getByRole("button", { name: "Upload" }));

    await screen.findByText("Stored copy");
    expect(uploadImageFn).toHaveBeenCalledTimes(2);
    const retakeFile = uploadImageFn.mock.calls[1][0] as File;
    expect(retakeFile.name).toBe(`${DEMO_SAMPLES[0].file.replace(/\.jpe?g$/i, "")}-retake.jpg`);
    const notice = screen.getByTestId("retake-notice");
    expect(notice).toHaveTextContent(/content-dedupe doing its job/);
    expect(notice).toHaveTextContent(/never re-encoded/i);
  });
});
