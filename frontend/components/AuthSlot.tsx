"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { logoutAccount } from "@/lib/api";
import { clearSession, getCachedUser, isSessionAlive, onAuthChanged, type SessionUser } from "@/lib/auth";

/**
 * Header auth area. Reads the cached profile only for DISPLAY (the API makes
 * every real decision); sign-out revokes the token server-side (denylist)
 * and clears local state even if that call fails (e.g. offline).
 */
export default function AuthSlot({ mobile = false }: { mobile?: boolean }) {
  const router = useRouter();
  const [user, setUser] = useState<SessionUser | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const sync = () => setUser(isSessionAlive() ? getCachedUser() : null);
    sync();
    return onAuthChanged(sync);
  }, []);

  async function signOut() {
    setBusy(true);
    try {
      await logoutAccount(); // server-side revocation — real, audited
    } catch {
      /* e.g. offline: local session still cleared below, token dies with expiry */
    } finally {
      clearSession();
      setBusy(false);
      router.push("/");
    }
  }

  if (!user) {
    return mobile ? (
      <Link href="/login" className="btn-primary mt-2 w-full">
        Sign in
      </Link>
    ) : (
      <>
        <Link href="/login" className="text-sm font-semibold text-stone-700 hover:text-emerald-900">
          Sign in
        </Link>
        <Link href="/dashboard" className="btn-primary">
          Try the Demo
        </Link>
      </>
    );
  }

  return mobile ? (
    <div className="mt-2 space-y-2 border-t border-stone-200 pt-2">
      <p className="px-1 text-xs text-stone-600">
        {user.email} · <span className="font-semibold">{user.role}</span>
      </p>
      {user.role === "ADMIN" ? (
        <Link href="/admin" className="block rounded-lg px-3 py-2 text-sm font-medium text-stone-700 hover:bg-stone-100">
          Admin
        </Link>
      ) : null}
      <button type="button" className="btn-secondary w-full" onClick={() => void signOut()} disabled={busy}>
        {busy ? "Signing out…" : "Sign out"}
      </button>
    </div>
  ) : (
    <div className="flex items-center gap-3">
      <span className="max-w-40 truncate text-xs text-stone-600" title={user.email}>
        {user.email} · <span className="font-semibold">{user.role}</span>
      </span>
      {user.role === "ADMIN" ? (
        <Link href="/admin" className="text-sm font-medium text-stone-600 transition hover:text-emerald-900">
          Admin
        </Link>
      ) : null}
      <button type="button" className="btn-secondary text-xs" onClick={() => void signOut()} disabled={busy}>
        {busy ? "…" : "Sign out"}
      </button>
    </div>
  );
}
