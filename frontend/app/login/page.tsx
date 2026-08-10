import type { Metadata } from "next";
import { Suspense } from "react";

import LoginForm from "@/components/LoginForm";

export const metadata: Metadata = {
  title: "Sign in",
  description: "Sign in to CropMind AI — JWT session, server-side revocation on sign-out.",
};

export default function LoginPage() {
  return (
    <div className="container-shell max-w-md py-16">
      <p className="eyebrow">Account</p>
      <h1 className="section-title">Sign in</h1>
      <p className="section-lede">
        Your workspace: uploads, analyses, zones, simulations and reports. Sessions are 12-hour JWTs and
        sign-out revokes the token server-side — not just in your browser.
      </p>
      <div className="card mt-8">
        <Suspense fallback={<p className="text-sm text-stone-500">Loading…</p>}>
          <LoginForm />
        </Suspense>
      </div>
      <p className="mt-4 text-sm text-stone-600">
        No account yet?{" "}
        <a href="/register" className="link-cta">
          Create one
        </a>{" "}
        — the first account on a fresh deployment becomes ADMIN (documented bootstrap).
      </p>
    </div>
  );
}
