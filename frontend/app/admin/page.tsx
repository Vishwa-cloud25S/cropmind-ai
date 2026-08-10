import type { Metadata } from "next";

import AdminPanel from "@/components/AdminPanel";

export const metadata: Metadata = {
  title: "Admin console",
  description: "ADMIN-only console: users + roles, feedback triage, audit trail, measured system counts.",
};

export default function AdminPage() {
  return (
    <div className="container-shell max-w-5xl py-10">
      <p className="eyebrow">ADMIN role required</p>
      <h1 className="section-title">Admin console</h1>
      <p className="section-lede">
        Live counts and records from the database — users and roles, prediction feedback for the data strategy,
        and the security audit trail. Enforced server-side; this page only renders what the API allows.
      </p>
      <div className="mt-8">
        <AdminPanel />
      </div>
    </div>
  );
}
