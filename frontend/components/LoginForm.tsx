"use client";

import { useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { errorMessage, loginAccount } from "@/lib/api";
import { saveSession } from "@/lib/auth";

/**
 * Sign-in form. Failure text is the backend's verbatim generic 401
 * ("invalid email or password") — the API deliberately does not say which
 * part failed (no account enumeration) and neither does this form.
 */
export default function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const next = params.get("next");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const auth = await loginAccount(email.trim(), password);
      saveSession({
        access_token: auth.access_token,
        expires_at: auth.expires_at,
        user: auth.user,
      });
      router.replace(next && next.startsWith("/") ? next : "/dashboard");
    } catch (err) {
      setError(errorMessage(err)); // verbatim generic message — by design
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="space-y-4" noValidate>
      {error ? (
        <p className="alert-error" role="alert">
          {error}
        </p>
      ) : null}
      <div>
        <label htmlFor="login-email" className="field-label">
          Email
        </label>
        <input
          id="login-email"
          type="email"
          required
          autoComplete="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="mt-1 w-full rounded-lg border border-stone-300 px-3 py-2 text-sm"
        />
      </div>
      <div>
        <label htmlFor="login-password" className="field-label">
          Password
        </label>
        <input
          id="login-password"
          type="password"
          required
          autoComplete="current-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="mt-1 w-full rounded-lg border border-stone-300 px-3 py-2 text-sm"
        />
      </div>
      <button type="submit" className="btn-primary w-full" disabled={busy || !email || !password}>
        {busy ? "Signing in…" : "Sign in"}
      </button>
    </form>
  );
}
