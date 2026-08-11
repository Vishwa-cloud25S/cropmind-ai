import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, createFarm, errorMessage, getAnalysis, getPredictionForAnalysis, RETRY_DELAYS_MS } from "@/lib/api";

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

  it("never invents an HTTP status on a network failure — after honest retries", async () => {
    const original = [...RETRY_DELAYS_MS.attempts];
    RETRY_DELAYS_MS.attempts = [0, 0, 0]; // same attempts, zero wall-clock waits
    try {
      const fetchMock = vi.fn().mockRejectedValue(new TypeError("fetch failed"));
      vi.stubGlobal("fetch", fetchMock);
      const caught = await createFarm({ name: "Rectory" }).catch((err) => err);
      expect(caught).toBeInstanceOf(ApiError);
      expect(caught.status).toBe(0);
      expect(fetchMock).toHaveBeenCalledTimes(3); // immediate + 2 retries, then the truth
      expect(errorMessage(caught)).toContain("cannot reach the CropMind API");
      expect(errorMessage(caught)).toContain("waking up"); // cold start stated, not denied
    } finally {
      RETRY_DELAYS_MS.attempts = original;
    }
  });

  it("recovers a call that succeeds on retry (cold-start wake)", async () => {
    const original = [...RETRY_DELAYS_MS.attempts];
    RETRY_DELAYS_MS.attempts = [0, 0, 0];
    try {
      const fetchMock = vi
        .fn()
        .mockRejectedValueOnce(new TypeError("fetch failed"))
        .mockResolvedValueOnce(jsonResponse(200, { analysis_id: "a-1", status: "QUEUED" }));
      vi.stubGlobal("fetch", fetchMock);
      const body = await getAnalysis("a-1");
      expect(fetchMock).toHaveBeenCalledTimes(2);
      expect(body.analysis_id).toBe("a-1");
    } finally {
      RETRY_DELAYS_MS.attempts = original;
    }
  });

  it("treats edge 502-with-HTML as transient and retries; JSON 502 from the app is not retried", async () => {
    const original = [...RETRY_DELAYS_MS.attempts];
    RETRY_DELAYS_MS.attempts = [0, 0, 0];
    try {
      const edgeHtml = new Response("<html>render waking</html>", {
        status: 502,
        headers: { "content-type": "text/html" },
      });
      const appJson = new Response(JSON.stringify({ detail: "real app error" }), {
        status: 502,
        headers: { "content-type": "application/json" },
      });
      const fetchMock = vi.fn().mockResolvedValueOnce(edgeHtml).mockResolvedValueOnce(appJson);
      vi.stubGlobal("fetch", fetchMock);
      const caught = await getAnalysis("a-9").catch((err) => err);
      expect(caught).toBeInstanceOf(ApiError);
      expect(fetchMock).toHaveBeenCalledTimes(2); // JSON 502 is an app truth — stop, don't spin
      expect(caught.detail).toBe("real app error");
    } finally {
      RETRY_DELAYS_MS.attempts = original;
    }
  });

  it("resolves undefined for 204 delete responses", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 204 })));
    const { deleteFarm } = await import("@/lib/api");
    await expect(deleteFarm("farm-1")).resolves.toBeUndefined();
  });
});
