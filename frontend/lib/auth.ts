"use client";

/**
 * Session client (Phase 10): JWT in localStorage + proactive expiry.
 *
 * Documented tradeoff (docs/04 §3.10): localStorage is XSS-readable — the API
 * is the real enforcement boundary (checks on every call, denylist on logout).
 * The stored profile is a display cache, refreshed from /auth/me; role checks
 * for actual actions happen server-side, never trusted from this cache.
 * Expired sessions are dropped proactively (exp-30s skew) so a request never
 * silently goes out with a dead token.
 */

export interface SessionUser {
  id: string;
  email: string;
  role: "FARMER" | "AGRONOMIST" | "ADMIN";
  created_at: string | null;
}

export interface Session {
  access_token: string;
  expires_at: string;
  user: SessionUser;
}

export const TOKEN_KEY = "cropmind.jwt";
export const SESSION_KEY = "cropmind.session";
const EXPIRY_SKEW_MS = 30_000;

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(TOKEN_KEY);
  } catch {
    return null; // storage blocked — act signed out rather than crash
  }
}

/** Milliseconds until expiry; <= 0 when expired/unknown. */
export function tokenTimeLeftMs(token: string | null = getToken()): number {
  if (!token) return 0;
  const raw = window.localStorage.getItem(SESSION_KEY);
  if (raw) {
    try {
      const session = JSON.parse(raw) as Session;
      return new Date(session.expires_at).getTime() - EXPIRY_SKEW_MS - Date.now();
    } catch {
      /* cached profile unreadable — fall through to the JWT's own exp */
    }
  }
  try {
    const payload = JSON.parse(atob(token.split(".")[1])) as { exp?: number };
    return (payload.exp ?? 0) * 1000 - EXPIRY_SKEW_MS - Date.now();
  } catch {
    return 0;
  }
}

export function isSessionAlive(): boolean {
  return tokenTimeLeftMs() > 0;
}

export function saveSession(session: Session): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(TOKEN_KEY, session.access_token);
  window.localStorage.setItem(SESSION_KEY, JSON.stringify(session));
  emitAuthChanged();
}

export function getCachedUser(): SessionUser | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(SESSION_KEY);
    if (!raw) return null;
    return (JSON.parse(raw) as Session).user;
  } catch {
    return null;
  }
}

export function clearSession(): void {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(TOKEN_KEY);
  window.localStorage.removeItem(SESSION_KEY);
  emitAuthChanged();
}

const AUTH_EVENT = "cropmind-auth-changed";

function emitAuthChanged(): void {
  window.dispatchEvent(new Event(AUTH_EVENT));
}

/** Subscribe to login/logout/session-cleared across tabs and components. */
export function onAuthChanged(listener: () => void): () => void {
  if (typeof window === "undefined") return () => {};
  window.addEventListener(AUTH_EVENT, listener);
  window.addEventListener("storage", listener);
  return () => {
    window.removeEventListener(AUTH_EVENT, listener);
    window.removeEventListener("storage", listener);
  };
}

/** 401 anywhere ⇒ drop the session and route to /login (with return path). */
export function handleUnauthorized(): void {
  if (typeof window === "undefined") return;
  clearSession();
  const here = window.location.pathname + window.location.search;
  if (!window.location.pathname.startsWith("/login")) {
    window.location.assign(`/login?next=${encodeURIComponent(here)}`);
  }
}
