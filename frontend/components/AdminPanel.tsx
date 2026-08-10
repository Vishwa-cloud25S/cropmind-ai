"use client";

import { useCallback, useEffect, useState } from "react";

import {
  adminListAuditLogs,
  adminListFeedback,
  adminListUsers,
  adminOverview,
  errorMessage,
} from "@/lib/api";
import { getCachedUser, isSessionAlive, onAuthChanged } from "@/lib/auth";
import type { AdminUserRow, AuditLogRow, FeedbackAdminList, OverviewStats } from "@/lib/types";

/**
 * Admin surface v1 (FR-21 essentials): users + role changes, feedback triage,
 * audit tail, measured counts. Every number is read at request time from the
 * server — nothing mocked. Non-admins get the honest 403 message shown as-is.
 */
export default function AdminPanel({ changeRoleFn }: { changeRoleFn?: (userId: string, role: "FARMER" | "AGRONOMIST" | "ADMIN") => Promise<unknown> } = {}) {
  const [allowed, setAllowed] = useState<boolean | null>(null);
  const [users, setUsers] = useState<AdminUserRow[] | null>(null);
  const [overview, setOverview] = useState<OverviewStats | null>(null);
  const [feedback, setFeedback] = useState<FeedbackAdminList | null>(null);
  const [logs, setLogs] = useState<AuditLogRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [roleMsg, setRoleMsg] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [userList, ov, fb, audit] = await Promise.all([
        adminListUsers(),
        adminOverview(),
        adminListFeedback(50),
        adminListAuditLogs(60),
      ]);
      setUsers(userList.users);
      setOverview(ov.overview);
      setFeedback(fb);
      setLogs(audit.audit_logs);
      setAllowed(true);
    } catch (err) {
      setAllowed(false);
      setError(errorMessage(err)); // 403 reason, verbatim
    }
  }, []);

  useEffect(() => {
    if (!isSessionAlive()) {
      setAllowed(false);
      setError("sign in with an admin account to use this console");
      return;
    }
    const me = getCachedUser();
    if (me && me.role !== "ADMIN") {
      setAllowed(false);
      setError(`requires role ADMIN — your role is ${me.role}`);
      return;
    }
    void load();
  }, [load]);

  useEffect(() => onAuthChanged(() => void load()), [load]);

  async function onRole(userId: string, role: "FARMER" | "AGRONOMIST" | "ADMIN") {
    setRoleMsg(null);
    try {
      const change = changeRoleFn ?? (await import("@/lib/api")).adminChangeRole;
      const result = (await change(userId, role)) as { role_transition: string };
      setRoleMsg(`role updated: ${result.role_transition} (audited)`);
      await load();
    } catch (err) {
      setRoleMsg(errorMessage(err));
    }
  }

  if (allowed === false) {
    return (
      <div className="card" role="alert">
        <p className="font-semibold text-stone-900">Admin console — restricted</p>
        <p className="mt-1 text-sm text-stone-600">{error}</p>
      </div>
    );
  }
  if (!users || !overview) return <p className="text-sm text-stone-500">Loading admin console…</p>;

  return (
    <div className="space-y-6">
      {overview ? (
        <section className="grid grid-cols-2 gap-3 sm:grid-cols-4" aria-label="System overview">
          {(
            [
              ["Users", overview.users],
              ["Analyses", overview.analyses],
              ["Predictions (suspected)", overview.predictions_by_status.SUSPECTED ?? 0],
              ["Zones pending review", overview.zones_by_review_status.PENDING ?? 0],
              ["Reports", overview.reports],
              ["Feedback", overview.feedback],
              ["Simulations", overview.simulation_runs],
              ["Audit-trailing tokens revoked", overview.revoked_tokens],
            ] as const
          ).map(([label, value]) => (
            <div key={label} className="stat-card">
              <p className="field-label">{label}</p>
              <p className="mt-1 text-2xl font-bold text-stone-900">{value}</p>
            </div>
          ))}
        </section>
      ) : null}

      <section className="card" aria-label="Users">
        <h2 className="text-lg font-bold text-stone-900">Users</h2>
        {roleMsg ? (
          <p className="alert-info mt-2" role="status">
            {roleMsg}
          </p>
        ) : null}
        <div className="mt-3 overflow-x-auto">
          <table className="table-basic">
            <thead>
              <tr>
                <th scope="col">Email</th>
                <th scope="col" className="text-center">Role</th>
                <th scope="col" className="text-center">Farms</th>
                <th scope="col" className="text-right">Change role</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id}>
                  <td>
                    <span className="text-sm font-medium text-stone-900">{u.email}</span>
                    {u.bootstrap_note ? (
                      <span className="block text-xs text-stone-500">{u.bootstrap_note}</span>
                    ) : null}
                  </td>
                  <td className="text-center">
                    <span className="chip-info">{u.role}</span>
                  </td>
                  <td className="text-center text-sm">{u.farm_count}</td>
                  <td className="text-right">
                    <select
                      aria-label={`Change role for ${u.email}`}
                      className="rounded border border-stone-300 px-2 py-1 text-xs"
                      value={u.role}
                      onChange={(e) => void onRole(u.id, e.target.value as "FARMER" | "AGRONOMIST" | "ADMIN")}
                    >
                      <option value="FARMER">FARMER</option>
                      <option value="AGRONOMIST">AGRONOMIST</option>
                      <option value="ADMIN">ADMIN</option>
                    </select>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-2 text-xs text-stone-500">
          You cannot change your own role (the API blocks it: no-admins-left footgun). Every change is audited
          with the old → new transition.
        </p>
      </section>

      <section className="card" aria-label="Feedback triage">
        <h2 className="text-lg font-bold text-stone-900">Feedback</h2>
        {feedback && feedback.count > 0 ? (
          <>
            <p className="mt-1 text-xs text-stone-500">
              {feedback.total} recorded · yes {feedback.by_correctness.YES ?? 0} · no {feedback.by_correctness.NO ?? 0} ·
              not-sure {feedback.by_correctness.NOT_SURE ?? 0} · {feedback.note}
            </p>
            <ul className="mt-3 space-y-2 text-sm">
              {feedback.feedback.map((row) => (
                <li key={row.id} className="rounded-lg border border-stone-200 bg-stone-50 px-3 py-2">
                  <span className="font-semibold">{row.correctness.replace("_", " ")}</span>
                  {row.user_email ? <span className="text-stone-500"> · {row.user_email}</span> : null}
                  {row.actual_condition ? <span> · actual: {row.actual_condition}</span> : null}
                  {row.image_quality ? <span className="text-stone-500"> · quality {row.image_quality}</span> : null}
                  {row.notes ? <span className="block text-xs text-stone-600">{row.notes}</span> : null}
                </li>
              ))}
            </ul>
          </>
        ) : (
          <p className="mt-1 text-sm text-stone-600">No feedback recorded yet.</p>
        )}
      </section>

      <section className="card" aria-label="Audit trail">
        <h2 className="text-lg font-bold text-stone-900">Audit trail (latest)</h2>
        {logs && logs.length > 0 ? (
          <div className="mt-3 max-h-80 overflow-auto">
            <table className="table-basic">
              <thead>
                <tr>
                  <th scope="col">When (UTC)</th>
                  <th scope="col">Action</th>
                  <th scope="col">Entity</th>
                </tr>
              </thead>
              <tbody>
                {logs.map((row) => (
                  <tr key={row.id}>
                    <td className="whitespace-nowrap font-mono text-xs">{row.created_at}</td>
                    <td className="font-mono text-xs">{row.action}</td>
                    <td className="font-mono text-xs">
                      {row.entity}
                      {row.entity_id ? ` ${row.entity_id.slice(0, 8)}…` : ""}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="mt-1 text-sm text-stone-600">No audited events yet.</p>
        )}
      </section>
    </div>
  );
}
