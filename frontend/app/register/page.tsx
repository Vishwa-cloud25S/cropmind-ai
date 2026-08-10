import type { Metadata } from "next";
import { Suspense } from "react";

import RegisterForm from "@/components/RegisterForm";

export const metadata: Metadata = {
  title: "Create account",
  description: "Create a CropMind AI account — first account on a fresh deployment becomes ADMIN (documented bootstrap).",
};

export default function RegisterPage() {
  return (
    <div className="container-shell max-w-md py-16">
      <p className="eyebrow">Account</p>
      <h1 className="section-title">Create account</h1>
      <p className="section-lede">
        One account covers analyses, zones, simulations, reports and feedback. Password policy: at least 10
        characters, one letter and one digit (stated, not silently rejected).
      </p>
      <div className="card mt-8">
        <Suspense fallback={<p className="text-sm text-stone-500">Loading…</p>}>
          <RegisterForm />
        </Suspense>
      </div>
    </div>
  );
}
