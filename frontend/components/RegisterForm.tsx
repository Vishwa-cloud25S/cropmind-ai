"use client";

import { useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { ApiError, errorMessage, registerAccount } from "@/lib/api";
import { saveSession } from "@/lib/auth";

/**
 * Registration. Policy feedback is explicit: unmet rules from the backend are
 * listed verbatim, and the bootstrap note (first account = ADMIN) is shown
 * after success so the privilege is never silent.
 */
export default function RegisterForm() {
  const router = useRouter();
  const params = useSearchParams();
  const next = params.get("next");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [unmet, setUnmet] = useState<string[]>([]);
  const [done, setDone] = useState<{ role: string; note: string | undefined } | null>(null);

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    setUnmet([]);
    if (password !== confirm) {
      setError("passwords do not match");
      return;
    }
    setBusy(true);
    try {
      const auth = await registerAccount(email.trim(), password);
      saveSession({
        access_token: auth.access_token,
        expires_at: auth.expires_at,
        user: auth.user,
      });
      // Role truth (bootstrap admin / farmer) is surfaced on-screen, never silent.
      setDone({ role: auth.user.role, note: auth.role_note });
    } catch (err) {
      if (err instanceof ApiError && err.status === 422 && err.detail && typeof err.detail === "object") {
        const detail = err.detail as { detail?: string; unmet_rules?: string[] };
        setError(detail.detail ?? errorMessage(err));
        setUnmet(detail.unmet_rules ?? []);
      } else {
        setError(errorMessage(err));
      }
    } finally {
      setBusy(false);
    }
  }

  if (done) {
    return (
      <div className="space-y-4" role="status">
        <p className="alert-info">
          Account created — you are signed in as <strong>{done.role}</strong>.
          {done.note ? <span className="block mt-1 text-sm">{done.note}</span> : null}
        </p>
        <button
          type="button"
          className="btn-primary w-full"
          onClick={() => router.replace(next && next.startsWith("/") ? next : "/dashboard")}
        >
          Continue
        </button>
      </div>
    );
  }

  return (
    <form onSubmit={onSubmit} className="space-y-4" noValidate>
      {error ? (
        <div className="alert-error" role="alert">
          <p>{error}</p>
          {unmet.length > 0 ? (
            <ul className="mt-1 list-inside list-disc text-sm">
              {unmet.map((rule) => (
                <li key={rule}>{rule}</li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}
      <div>
        <label htmlFor="reg-email" className="field-label">
          Email
        </label>
        <input
          id="reg-email"
          type="email"
          required
          autoComplete="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="mt-1 w-full rounded-lg border border-stone-300 px-3 py-2 text-sm"
        />
      </div>
      <div>
        <label htmlFor="reg-password" className="field-label">
          Password <span className="font-normal text-stone-500">(10+ chars, a letter and a digit)</span>
        </label>
        <input
          id="reg-password"
          type="password"
          required
          autoComplete="new-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="mt-1 w-full rounded-lg border border-stone-300 px-3 py-2 text-sm"
        />
      </div>
      <div>
        <label htmlFor="reg-confirm" className="field-label">
          Confirm password
        </label>
        <input
          id="reg-confirm"
          type="password"
          required
          autoComplete="new-password"
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
          className="mt-1 w-full rounded-lg border border-stone-300 px-3 py-2 text-sm"
        />
      </div>
      <button type="submit" className="btn-primary w-full" disabled={busy || !email || !password}>
        {busy ? "Creating…" : "Create account"}
      </button>
      <p className="text-xs leading-5 text-stone-500">
        No marketing email, no verification flow yet (MVP, stated in docs). The account lives in your own
        deployment&apos;s database.
      </p>
    </form>
  );
}
