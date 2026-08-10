"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { getMe, logoutAccount } from "@/lib/api";
import { clearSession, getCachedUser, isSessionAlive, type SessionUser } from "@/lib/auth";

/**
 * Settings (Phase 10): the session as the server sees it (fresh /auth/me read
 * — the localStorage profile is only a display cache), sign-out with real
 * server-side revocation, and pointers to where configuration truth lives.
 */
export default function SettingsPanel() {
  const router = useRouter();
  const [user, setUser] = useState<SessionUser | null>(null);
  const [sessionNote, setSessionNote] = useState<string | null>(null);
  const [expiresAt, setExpiresAt] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!isSessionAlive()) {
      setUser(null);
      return;
    }
    setUser(getCachedUser());
    getMe()
      .then((me) => {
        setUser(me.user);
        setExpiresAt(me.session.expires_at);
        setSessionNote(me.session.revocation);
      })
      .catch(() => {
        /* 401 handling in api.ts already routes to /login */
      });
  }, []);

  async function signOut() {
    setBusy(true);
    try {
      await logoutAccount();
    } catch {
      /* local session clears regardless */
    } finally {
      clearSession();
      setBusy(false);
      router.push("/");
    }
  }

  if (!user) {
    return (
      <div className="card" role="note">
        <p className="font-semibold text-stone-900">Signed out</p>
        <p className="mt-1 text-sm text-stone-600">
          There is no active session in this browser.{" "}
          <Link href="/login?next=/settings" className="link-cta">
            Sign in
          </Link>{" "}
          to see account settings.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <section className="card" aria-label="Account">
        <h2 className="text-lg font-bold text-stone-900">Account</h2>
        <dl className="mt-3 grid gap-3 text-sm sm:grid-cols-2">
          <div>
            <dt className="field-label">Email</dt>
            <dd className="mt-1 font-medium text-stone-900">{user.email}</dd>
          </div>
          <div>
            <dt className="field-label">Role</dt>
            <dd className="mt-1">
              <span className="chip-info">{user.role}</span>
            </dd>
          </div>
          <div>
            <dt className="field-label">Session expires</dt>
            <dd className="mt-1 font-medium text-stone-900">
              {expiresAt ? new Date(expiresAt).toLocaleString() : "—"}
            </dd>
          </div>
          <div>
            <dt className="field-label">Sign-out behaviour</dt>
            <dd className="mt-1 text-xs text-stone-600">{sessionNote ?? "server-side denylist revocation"}</dd>
          </div>
        </dl>
        <div className="mt-4">
          <button type="button" className="btn-secondary" onClick={() => void signOut()} disabled={busy}>
            {busy ? "Signing out…" : "Sign out (revokes this token server-side)"}
          </button>
        </div>
      </section>

      <section className="card" aria-label="Configuration pointers">
        <h2 className="text-lg font-bold text-stone-900">Where the real configuration lives</h2>
        <ul className="mt-2 list-inside list-disc space-y-1 text-sm text-stone-600">
          <li>
            Confidence bands, abstain rule, supported crops →{" "}
            <Link href="/model-information" className="link-cta">
              Model information
            </Link>{" "}
            (served live from the ML config — never duplicated here)
          </li>
          <li>
            Farm/field defaults (names, crops, boundaries) →{" "}
            <Link href="/farms" className="link-cta">
              Farms
            </Link>
          </li>
          <li>Theme/language: none yet — no hidden preference state exists to pretend otherwise</li>
        </ul>
      </section>
    </div>
  );
}
