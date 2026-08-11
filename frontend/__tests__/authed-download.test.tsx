import { cleanup, render } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError, downloadAuthedFile, fetchAuthedBlob } from "@/lib/api";
import { clearSession, saveSession, type Session } from "@/lib/auth";
import AuthedImage from "@/components/AuthedImage";

const renderAuthedImage = (url: string, alt: string) => render(<AuthedImage url={url} alt={alt} />);

/**
 * Regression for the live-found bug: owner-scoped binary routes (report PDFs, stored
 * imagery, Grad-CAM, zone exports) returned the by-design 404 when reached by a plain
 * <a href>/<img src> — because that navigation carries no session token. All binary
 * loads go through these helpers; these tests pin the token actually rides along.
 */

/** Unsigned-structure test JWT (the client never validates; the API does). */
function fakeJwt(expSecondsFromNow: number): string {
  const header = btoa(JSON.stringify({ alg: "HS256", typ: "JWT" }));
  const payload = btoa(
    JSON.stringify({ sub: "u1", role: "FARMER", jti: "j1", exp: Math.floor(Date.now() / 1000) + expSecondsFromNow })
  );
  return `${header}.${payload}.testsig`;
}

function liveSession(token: string): Session {
  return {
    access_token: token,
    expires_at: new Date(Date.now() + 3_600_000).toISOString(),
    user: { id: "u1", email: "farmer@example.test", role: "FARMER", created_at: null },
  };
}

function stubObjectUrls() {
  vi.stubGlobal("URL", {
    ...URL,
    createObjectURL: vi.fn(() => "blob:mock-object-url"),
    revokeObjectURL: vi.fn(),
  });
}

describe("authenticated binary downloads", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });
  afterEach(() => {
    clearSession();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("attaches the session token to blob fetches", async () => {
    saveSession(liveSession(fakeJwt(3600)));
    const mockFetch = vi.fn(async () => new Response(new Blob(["%PDF"]), { status: 200 }));
    vi.stubGlobal("fetch", mockFetch);
    const { blob } = await fetchAuthedBlob("http://api.test/reports/r1/download");
    expect(blob.size).toBeGreaterThan(0);
    const init = (mockFetch.mock.calls[0] as unknown[])[1] as RequestInit;
    expect((init.headers as Record<string, string>).Authorization).toBe(
      `Bearer ${fakeJwt(3600)}`
    );
  });

  it("sends no Authorization header when signed out (anonymous demo path)", async () => {
    const mockFetch = vi.fn(async () => new Response(new Blob(["x"]), { status: 200 }));
    vi.stubGlobal("fetch", mockFetch);
    await fetchAuthedBlob("http://api.test/images/i1/download");
    const init = (mockFetch.mock.calls[0] as unknown[])[1] as RequestInit;
    expect((init.headers as Record<string, string>).Authorization).toBeUndefined();
  });

  it("reads the server-set filename from Content-Disposition", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(new Blob(["x"]), {
            status: 200,
            headers: { "content-disposition": 'attachment; filename="cropmind-field-report-CMA-20260811-ABC123.pdf"' },
          })
      )
    );
    const { filename } = await fetchAuthedBlob("http://api.test/reports/r1/download");
    expect(filename).toBe("cropmind-field-report-CMA-20260811-ABC123.pdf");
  });

  it("throws the real ApiError status on failure — never a fake success", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response(JSON.stringify({ detail: "report not found" }), { status: 404 })));
    await expect(fetchAuthedBlob("http://api.test/reports/nope/download")).rejects.toBeInstanceOf(ApiError);
    const err = (await fetchAuthedBlob("http://api.test/reports/nope/download").catch((e) => e)) as ApiError;
    expect(err.status).toBe(404);
    expect(err.detail).toMatchObject({ detail: "report not found" });
  });

  it("downloadAuthedFile prefers the server filename, falls back honestly, then revokes", async () => {
    saveSession(liveSession(fakeJwt(3600)));
    stubObjectUrls();
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(new Blob(["x"]), {
            status: 200,
            headers: { "content-disposition": 'attachment; filename="cropmind-zone-simulation-ab12cd34.csv"' },
          })
      )
    );
    const clicks: string[] = [];
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (this: HTMLAnchorElement) {
      clicks.push(this.download);
    });
    await downloadAuthedFile("http://api.test/intervention-zones/export?format=csv", "cropmind-zone-simulation.csv");
    expect(clicks).toEqual(["cropmind-zone-simulation-ab12cd34.csv"]);
    expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:mock-object-url");
  });

  it("downloadAuthedFile uses the caller's fallback when no filename header", async () => {
    saveSession(liveSession(fakeJwt(3600)));
    stubObjectUrls();
    vi.stubGlobal("fetch", vi.fn(async () => new Response(new Blob(["x"]), { status: 200 })));
    const clicks: string[] = [];
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (this: HTMLAnchorElement) {
      clicks.push(this.download);
    });
    await downloadAuthedFile("http://api.test/reports/r1/download", "cropmind-field-report-CMA-X.pdf");
    expect(clicks).toEqual(["cropmind-field-report-CMA-X.pdf"]);
  });
});

describe("AuthedImage", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });
  afterEach(() => {
    cleanup(); // unmount BEFORE unstuubing — effect cleanup calls URL.revokeObjectURL
    clearSession();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("renders stored media via token-fetched object URL", async () => {
    saveSession(liveSession(fakeJwt(3600)));
    vi.stubGlobal("URL", { ...URL, createObjectURL: vi.fn(() => "blob:mock-object-url"), revokeObjectURL: vi.fn() });
    const mockFetch = vi.fn(async () => new Response(new Blob(["img"]), { status: 200 }));
    vi.stubGlobal("fetch", mockFetch);
    const { findByAltText } = renderAuthedImage("http://api.test/images/i1/download", "Stored upload");
    const img = (await findByAltText("Stored upload")) as HTMLImageElement;
    expect(img.src).toBe("blob:mock-object-url");
    const init = (mockFetch.mock.calls[0] as unknown[])[1] as RequestInit;
    expect((init.headers as Record<string, string>).Authorization).toBeDefined();
  });

  it("shows the honest failure text when the API refuses", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response("{}", { status: 404, statusText: "Not Found" })));
    const { findByRole } = renderAuthedImage("http://api.test/images/nope/download", "missing");
    const note = await findByRole("note");
    expect(note).toHaveTextContent(/not available to this session/i);
  });
});
