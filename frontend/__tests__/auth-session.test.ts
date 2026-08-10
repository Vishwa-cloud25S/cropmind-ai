import { afterEach, beforeEach, describe, expect, it } from "vitest";

import {
  clearSession,
  getCachedUser,
  getToken,
  isSessionAlive,
  saveSession,
  tokenTimeLeftMs,
  type Session,
} from "@/lib/auth";

/** Unsigned-structure test JWT (signature untouched by the client — the API validates). */
function fakeJwt(expSecondsFromNow: number): string {
  const header = btoa(JSON.stringify({ alg: "HS256", typ: "JWT" }));
  const payload = btoa(JSON.stringify({ sub: "u1", role: "FARMER", jti: "j1", exp: Math.floor(Date.now() / 1000) + expSecondsFromNow }));
  return `${header}.${payload}.testsig`;
}

function sessionWith(token: string, expiresAt: string): Session {
  return {
    access_token: token,
    expires_at: expiresAt,
    user: { id: "u1", email: "farmer@example.test", role: "FARMER", created_at: null },
  };
}

describe("auth session client (localStorage + proactive expiry)", () => {
  beforeEach(() => window.localStorage.clear());
  afterEach(() => window.localStorage.clear());

  it("saves and returns the token + cached profile", () => {
    const token = fakeJwt(3600);
    saveSession(sessionWith(token, new Date(Date.now() + 3_600_000).toISOString()));
    expect(getToken()).toBe(token);
    expect(getCachedUser()?.email).toBe("farmer@example.test");
    expect(isSessionAlive()).toBe(true);
  });

  it("drops sessions past expiry (with skew) instead of sending dead tokens", () => {
    const expired = fakeJwt(-60);
    saveSession(sessionWith(expired, new Date(Date.now() - 60_000).toISOString()));
    expect(isSessionAlive()).toBe(false);
    expect(tokenTimeLeftMs()).toBeLessThanOrEqual(0);
  });

  it("missing session means signed out (null, never a crash)", () => {
    expect(getToken()).toBeNull();
    expect(getCachedUser()).toBeNull();
    expect(isSessionAlive()).toBe(false);
  });

  it("clearSession removes both keys", () => {
    saveSession(sessionWith(fakeJwt(3600), new Date(Date.now() + 3_600_000).toISOString()));
    clearSession();
    expect(getToken()).toBeNull();
    expect(window.localStorage.getItem("cropmind.session")).toBeNull();
  });
});
