import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import AnalyzeWizard from "@/components/AnalyzeWizard";
import type { AnalysisCreateResponse, AnalysisStatus, ImageUploadResponse } from "@/lib/types";

vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}));

const UPLOAD_OK: ImageUploadResponse = {
  image: {
    id: "img-111",
    field_id: null,
    sha256: "ab".repeat(32),
    width: 640,
    height: 480,
    byte_size: 102_400,
    captured_at: null,
    exif: null,
    source_type: "upload",
    created_at: "2026-08-09T09:00:00+00:00",
    deduplicated: true,
  },
};

const CREATED: AnalysisCreateResponse = {
  analysis_id: "ana-222",
  job_id: "job-333",
  status: "QUEUED",
  poll: "/analyses/ana-222",
  note: "202 Accepted — the ML worker picks this up asynchronously.",
};

function analysisStatus(status: AnalysisStatus["status"], error: string | null = null): AnalysisStatus {
  return {
    analysis_id: "ana-222",
    image_id: "img-111",
    status,
    demo: false,
    created_at: "2026-08-09T09:00:01+00:00",
    started_at: null,
    completed_at: null,
    error,
    job: { id: "job-333", status: "PENDING", attempts: 1, max_attempts: 3 },
  };
}

function makeDeps(overrides: Partial<Parameters<typeof AnalyzeWizard>[0]> = {}) {
  return {
    uploadImageFn: vi.fn().mockResolvedValue(UPLOAD_OK),
    createAnalysisFn: vi.fn().mockResolvedValue(CREATED),
    getAnalysisFn: vi.fn(),
    listFarmsFn: vi.fn().mockResolvedValue({ count: 0, farms: [] }),
    getFarmFn: vi.fn(),
    pollMs: 5,
    ...overrides,
  };
}

async function pickPhoto(user: ReturnType<typeof userEvent.setup>, file: File) {
  const input = screen.getByLabelText("Image file") as HTMLInputElement;
  await user.upload(input, file);
  return input;
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("AnalyzeWizard", () => {
  it("rejects an oversized file honestly before any network call", async () => {
    const deps = makeDeps();
    const user = userEvent.setup();
    render(<AnalyzeWizard {...deps} />);

    const big = new File(["x"], "huge.jpg", { type: "image/jpeg" });
    Object.defineProperty(big, "size", { value: 26 * 1024 * 1024 });
    await pickPhoto(user, big);

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("the limit is 25 MB");
    expect(alert).toHaveTextContent("magic bytes"); // no "rename it" loophole claims
    expect(deps.uploadImageFn).not.toHaveBeenCalled();
  });

  it("runs upload → analysis → poll until COMPLETED, surfacing dedup and the verdict link", async () => {
    const deps = makeDeps({
      getAnalysisFn: vi
        .fn()
        .mockResolvedValueOnce(analysisStatus("QUEUED"))
        .mockResolvedValue(analysisStatus("COMPLETED")),
    });
    const user = userEvent.setup();
    render(<AnalyzeWizard {...deps} />);

    await pickPhoto(user, new File(["jpeg-bytes"], "leaf.jpg", { type: "image/jpeg" }));
    await user.click(screen.getByRole("button", { name: "Upload" }));

    expect(screen.getByText("Stored copy")).toBeInTheDocument();
    expect(screen.getByText(/Identical content was already uploaded/)).toBeInTheDocument(); // dedup note
    expect(deps.uploadImageFn).toHaveBeenCalledWith(expect.anything(), { fieldId: undefined });

    await user.click(screen.getByRole("button", { name: "Run analysis" }));
    expect(deps.createAnalysisFn).toHaveBeenCalledWith("img-111", { fieldId: undefined });

    const link = await screen.findByRole("link", { name: /View the full analysis/ });
    expect(link).toHaveAttribute("href", "/analyses/ana-222");
    expect(screen.getByText("COMPLETED")).toBeInTheDocument();
  });

  it("surfaces a FAILED analysis with the recorded error and a retry", async () => {
    const deps = makeDeps({
      getAnalysisFn: vi.fn().mockResolvedValue(analysisStatus("FAILED", "sample model subprocess failed")),
    });
    const user = userEvent.setup();
    render(<AnalyzeWizard {...deps} />);

    await pickPhoto(user, new File(["jpeg-bytes"], "leaf.jpg", { type: "image/jpeg" }));
    await user.click(screen.getByRole("button", { name: "Upload" }));
    await user.click(screen.getByRole("button", { name: "Run analysis" }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("sample model subprocess failed");
    expect(alert).toHaveTextContent("Try again");
    expect(screen.getByText("FAILED")).toBeInTheDocument();
  });

  it("shows farm/field pickers only when farms exist (and fields follow the chosen farm)", async () => {
    const deps = makeDeps({
      listFarmsFn: vi.fn().mockResolvedValue({
        count: 1,
        farms: [{ id: "farm-1", name: "Rectory Farm", location: null, field_count: 1, created_at: null }],
      }),
      getFarmFn: vi.fn().mockResolvedValue({
        farm: { id: "farm-1", name: "Rectory Farm", location: null, field_count: 1, created_at: null },
        fields: [
          { id: "field-9", farm_id: "farm-1", name: "North paddock", crop_id: "tomato", area_ha: 2.5, created_at: null },
        ],
      }),
    });
    const user = userEvent.setup();
    render(<AnalyzeWizard {...deps} />);

    const farmSelect = await screen.findByLabelText("Farm (optional)");
    const fieldSelect = screen.getByLabelText("Field (optional)") as HTMLSelectElement;
    expect(fieldSelect).toBeDisabled(); // wait for a farm choice; no guessing

    await user.selectOptions(farmSelect, "farm-1");
    await waitFor(() => expect(fieldSelect).toBeEnabled());
    await user.selectOptions(fieldSelect, "field-9");

    await pickPhoto(user, new File(["jpeg-bytes"], "leaf.jpg", { type: "image/jpeg" }));
    await user.click(screen.getByRole("button", { name: "Upload" }));
    expect(deps.uploadImageFn).toHaveBeenCalledWith(expect.anything(), { fieldId: "field-9" });
  });
});
