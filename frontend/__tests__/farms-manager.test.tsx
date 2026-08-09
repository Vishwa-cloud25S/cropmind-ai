import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import FarmsManager from "@/components/FarmsManager";
import { ApiError } from "@/lib/api";
import type { Farm } from "@/lib/types";

vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}));

const RECTORY: Farm = {
  id: "farm-1",
  name: "Rectory Farm",
  location: "Kent, UK",
  field_count: 3,
  created_at: "2026-08-09T08:00:00+00:00",
};

function makeDeps() {
  return {
    listFarmsFn: vi.fn().mockResolvedValue({ count: 1, farms: [RECTORY] }),
    createFarmFn: vi.fn().mockResolvedValue({ farm: { ...RECTORY, id: "farm-2", name: "Manor Farm", field_count: 0 } }),
    deleteFarmFn: vi.fn().mockResolvedValue(undefined),
  };
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("FarmsManager", () => {
  it("lists farms returned by the API", async () => {
    const deps = makeDeps();
    render(<FarmsManager {...deps} />);
    expect(await screen.findByText("Rectory Farm")).toBeInTheDocument();
    expect(screen.getByText(/3 fields/)).toBeInTheDocument();
  });

  it("creates a farm and refreshes the list", async () => {
    const deps = makeDeps();
    deps.listFarmsFn
      .mockResolvedValueOnce({ count: 1, farms: [RECTORY] })
      .mockResolvedValue({
        count: 2,
        farms: [RECTORY, { ...RECTORY, id: "farm-2", name: "Manor Farm", field_count: 0 }],
      });
    const user = userEvent.setup();
    render(<FarmsManager {...deps} />);

    await screen.findByText("Rectory Farm");
    await user.type(screen.getByLabelText("Name"), "Manor Farm");
    await user.click(screen.getByRole("button", { name: "Create farm" }));

    expect(deps.createFarmFn).toHaveBeenCalledWith({ name: "Manor Farm", location: undefined });
    expect(await screen.findByText("Manor Farm")).toBeInTheDocument();
  });

  it("surfaces a delete 409 with the honest blocking counts", async () => {
    const deps = makeDeps();
    deps.deleteFarmFn.mockRejectedValue(
      new ApiError(409, { detail: "farm still has fields — delete them first", field_count: 3 }),
    );
    const user = userEvent.setup();
    render(<FarmsManager {...deps} />);

    await screen.findByText("Rectory Farm");
    await user.click(screen.getByRole("button", { name: "Delete" }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("farm still has fields");
    expect(alert).toHaveTextContent("field count: 3");
  });
});
