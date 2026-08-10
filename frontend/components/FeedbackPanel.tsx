"use client";

import { useCallback, useEffect, useState } from "react";

import { errorMessage, listFeedback, submitFeedback } from "@/lib/api";
import type { FeedbackItem } from "@/lib/types";

export interface FeedbackPanelDeps {
  submitFn?: typeof submitFeedback;
  listFn?: typeof listFeedback;
}

const CORRECTNESS = [
  { value: "YES", label: "Yes — correct" },
  { value: "NO", label: "No — wrong" },
  { value: "NOT_SURE", label: "Not sure" },
] as const;

const QUALITY = [
  { value: "GOOD", label: "Good" },
  { value: "BLURRY", label: "Blurry" },
  { value: "BAD_LIGHTING", label: "Bad lighting" },
  { value: "NOT_A_LEAF", label: "Not a leaf" },
] as const;

/**
 * Feedback capture (FR-18): was the suspected finding correct? Verdicts are
 * per-account and audited, and the stated destination is the data strategy —
 * no automatic retraining (the note says so on the record and here).
 */
export default function FeedbackPanel({ analysisId, ...props }: FeedbackPanelDeps & { analysisId: string }) {
  const submit = props.submitFn ?? submitFeedback;
  const list = props.listFn ?? listFeedback;

  const [correctness, setCorrectness] = useState<"YES" | "NO" | "NOT_SURE" | null>(null);
  const [actualCondition, setActualCondition] = useState("");
  const [quality, setQuality] = useState("");
  const [notes, setNotes] = useState("");
  const [existing, setExisting] = useState<FeedbackItem[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [recorded, setRecorded] = useState<string | null>(null); // backend note, verbatim

  const refresh = useCallback(async () => {
    try {
      const result = await list(analysisId);
      setExisting(result.feedback);
    } catch {
      setExisting([]); // listing failure must not block submitting
    }
  }, [analysisId, list]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!correctness) return;
    setBusy(true);
    setError(null);
    try {
      const result = await submit(analysisId, {
        correctness,
        actual_condition: actualCondition.trim() || null,
        notes: notes.trim() || null,
        image_quality: (quality || null) as "GOOD" | "BLURRY" | "BAD_LIGHTING" | "NOT_A_LEAF" | null,
      });
      setRecorded(result.note);
      setCorrectness(null);
      setActualCondition("");
      setQuality("");
      setNotes("");
      await refresh();
    } catch (err) {
      setError(errorMessage(err)); // verbatim backend reason (401 sign-in, 409 not completed, …)
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="card" aria-label="Prediction feedback" data-testid="feedback-panel">
      <h2 className="text-lg font-bold text-stone-900">Was this correct?</h2>
      <p className="mt-1 text-sm text-stone-600">
        Your verdict is stored against your account and reviewed by an agronomist/admin — it informs the data
        strategy. It does <strong>not</strong> retrain anything automatically.
      </p>

      {existing && existing.length > 0 ? (
        <ul className="mt-3 space-y-1 text-xs text-stone-600">
          {existing.map((row) => (
            <li key={row.id} className="rounded border border-stone-200 bg-stone-50 px-2 py-1">
              recorded {row.correctness.replace("_", " ")}
              {row.actual_condition ? ` — actual: ${row.actual_condition}` : ""}
              {row.created_at ? ` · ${new Date(row.created_at).toLocaleString()}` : ""}
            </li>
          ))}
        </ul>
      ) : null}

      {recorded ? (
        <p className="alert-info mt-3" role="status">
          {recorded}
        </p>
      ) : null}

      <form onSubmit={onSubmit} className="mt-4 space-y-3">
        {error ? (
          <p className="alert-error" role="alert">
            {error}
          </p>
        ) : null}
        <div className="flex flex-wrap gap-2" role="radiogroup" aria-label="Correctness">
          {CORRECTNESS.map((opt) => (
            <label
              key={opt.value}
              className={`cursor-pointer rounded-lg border px-3 py-2 text-sm font-medium ${
                correctness === opt.value
                  ? "border-emerald-700 bg-emerald-50 text-emerald-900"
                  : "border-stone-300 text-stone-700 hover:bg-stone-50"
              }`}
            >
              <input
                type="radio"
                name="correctness"
                value={opt.value}
                className="sr-only"
                checked={correctness === opt.value}
                onChange={() => setCorrectness(opt.value)}
              />
              {opt.label}
            </label>
          ))}
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          <div>
            <label htmlFor="fb-condition" className="field-label">
              Actual condition (if known)
            </label>
            <input
              id="fb-condition"
              type="text"
              maxLength={120}
              value={actualCondition}
              onChange={(e) => setActualCondition(e.target.value)}
              placeholder="e.g. healthy — it was dust"
              className="mt-1 w-full rounded-lg border border-stone-300 px-3 py-2 text-sm"
            />
          </div>
          <div>
            <label htmlFor="fb-quality" className="field-label">
              Image quality
            </label>
            <select
              id="fb-quality"
              value={quality}
              onChange={(e) => setQuality(e.target.value)}
              className="mt-1 w-full rounded-lg border border-stone-300 px-3 py-2 text-sm"
            >
              <option value="">— not rated —</option>
              {QUALITY.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>
        </div>
        <div>
          <label htmlFor="fb-notes" className="field-label">
            Notes (optional)
          </label>
          <textarea
            id="fb-notes"
            rows={2}
            maxLength={2000}
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            className="mt-1 w-full rounded-lg border border-stone-300 px-3 py-2 text-sm"
          />
        </div>
        <button type="submit" className="btn-primary" disabled={!correctness || busy}>
          {busy ? "Recording…" : "Record verdict"}
        </button>
      </form>
    </section>
  );
}
