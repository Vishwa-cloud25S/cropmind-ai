import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, createFarm, errorMessage, getPredictionForAnalysis } from "@/lib/api";

/** The error-normalization tests guard honesty plumbing: detail payloads surface verbatim. */

afterEach(() => {
  vi.unstubAllGlobals();
});

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("ApiError + errorMessage", () => {
  it("surfaces a plain string detail verbatim", () => {
    const err = new ApiError(404, "analysis not found");
    expect(errorMessage(err)).toBe("analysis not found");
  });

  it("unwraps object details to the inner honesty line", () => {
    const err = new ApiError(409, { detail: "Grad-CAM overlay not available", analysis_status: "FAILED" });
    expect(errorMessage(err)).toBe("Grad-CAM overlay not available");
  });

  it("summarizes validation-error arrays without inventing content", () => {
    const err = new ApiError(422, [{ loc: ["body", "image_id"], msg: "field required" }]);
    expect(errorMessage(err)).toBe("Invalid input — please review the highlighted fields.");
  });

  it("falls back to the status for unknown shapes", () => {
    expect(errorMessage(new ApiError(500, { unexpected: true }))).toBe("Request failed (HTTP 500)");
    expect(errorMessage("nope")).toBe("Unexpected error");
  });
});

describe("request layer", () => {
  it("rejects with ApiError carrying the backend detail shape on failure", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        // FastAPI wraps HTTPException payloads: {"detail": <the honesty object>}
        jsonResponse(409, { detail: { detail: "prediction not ready", analysis_status: "QUEUED", poll: "/analyses/x" } }),
      ),
    );
    const caught = await getPredictionForAnalysis("x").catch((err) => err);
    expect(caught).toBeInstanceOf(ApiError);
    expect(caught.status).toBe(409);
    expect((caught.detail as Record<string, unknown>).analysis_status).toBe("QUEUED");
    expect(errorMessage(caught)).toBe("prediction not ready");
  });

  it("never invents an HTTP status on a network failure", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("fetch failed")));
    const caught = await createFarm({ name: "Rectory" }).catch((err) => err);
    expect(caught).toBeInstanceOf(ApiError);
    expect(caught.status).toBe(0);
    expect(errorMessage(caught)).toBe("cannot reach the CropMind API — is the backend running?");
  });

  it("resolves undefined for 204 delete responses", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 204 })));
    const { deleteFarm } = await import("@/lib/api");
    await expect(deleteFarm("farm-1")).resolves.toBeUndefined();
  });
});
