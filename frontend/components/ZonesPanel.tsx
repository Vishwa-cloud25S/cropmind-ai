"use client";

import { useState } from "react";
import Link from "next/link";

import { errorMessage, reviewZone, zoneExportUrl } from "@/lib/api";
import type { DecisionSupport, InterventionZone, ReviewStatus, RiskLevel } from "@/lib/types";

export interface ZonesDeps {
  reviewZoneFn?: typeof reviewZone;
  onChanged?: () => void; // parent re-reads from the API after any review transition
}

const RISK_META: Record<RiskLevel, { cls: string; label: string }> = {
  LOW: { cls: "chip-muted", label: "LOW risk" },
  MEDIUM: { cls: "chip-info", label: "MEDIUM risk" },
  HIGH: { cls: "chip-medium", label: "HIGH risk" },
  CRITICAL: { cls: "chip-critical", label: "CRITICAL risk" },
};

const REVIEW_META: Record<ReviewStatus, { cls: string; label: string }> = {
  PENDING: { cls: "chip-medium", label: "PENDING review" },
  APPROVED: { cls: "chip-high", label: "APPROVED" },
  REJECTED: { cls: "chip-critical", label: "REJECTED" },
};

/** Confidence-band chips reused from the analysis views for the count strip. */
const RISK_ORDER: RiskLevel[] = ["CRITICAL", "HIGH", "MEDIUM", "LOW"];

/**
 * Zone review + export surface. Zones are simulations in evidence space — the
 * panel states that structurally: every zone carries its georeference badge, its
 * area note, and the simulation label; exports link to labelled downloads.
 */
export default function ZonesPanel({
  zones,
  decisionSupport,
  fieldId,
  ...props
}: ZonesDeps & { zones: InterventionZone[]; decisionSupport: DecisionSupport | null; fieldId: string }) {
  const reviewZoneFn = props.reviewZoneFn ?? reviewZone;
  const onChanged = props.onChanged;

  const [error, setError] = useState<string | null>(null);
  const [busyZone, setBusyZone] = useState<string | null>(null);

  async function review(zone: InterventionZone, status: "APPROVED" | "REJECTED") {
    setBusyZone(zone.id);
    setError(null);
    try {
      await reviewZoneFn(zone.id, { review_status: status });
      onChanged?.();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusyZone(null);
    }
  }

  return (
    <div className="space-y-5" data-testid="zones-panel">
      {decisionSupport ? (
        <section className="card" aria-label="Decision support">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-lg font-bold text-stone-900">Decision support</h2>
            <span className="chip-muted">{decisionSupport.pending_zone_count} pending review</span>
          </div>
          <div className="mt-3 flex flex-wrap gap-2" aria-label="Zones by risk level">
            {RISK_ORDER.map((level) => (
              <span key={level} className={RISK_META[level].cls}>
                {RISK_META[level].label}: {decisionSupport.risk_counts[level] ?? 0}
              </span>
            ))}
          </div>
          <p className="mt-3 text-xs leading-5 text-stone-500">{decisionSupport.note}</p>
          {decisionSupport.first_priority_zone_ids.length > 0 ? (
            <p className="alert-caution mt-3" role="note">
              Review first: the highest-priority pending zones are highlighted below (priority 1 = CRITICAL rule).
            </p>
          ) : null}
        </section>
      ) : null}

      <section className="card" aria-label="Intervention zones">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-lg font-bold text-stone-900">Intervention zones ({zones.length})</h2>
          <div className="flex items-center gap-2">
            <a className="btn-secondary" href={zoneExportUrl({ fieldId, format: "geojson" })} download>
              Export GeoJSON
            </a>
            <a className="btn-secondary" href={zoneExportUrl({ fieldId, format: "csv" })} download>
              Export CSV
            </a>
          </div>
        </div>
        <p className="mt-1 text-xs leading-5 text-stone-500">
          Downloads are labelled <em>precision intervention zone simulation</em> in filename and body — decision
          support pending human review, never verified field positions.
        </p>

        {error ? (
          <p className="alert-error mt-3" role="alert">
            {error}
          </p>
        ) : null}

        {zones.length === 0 ? (
          <p className="alert-info mt-4" role="note">
            No zones yet. Zones are generated per completed SUSPECTED analysis — the system abstains on
            INCONCLUSIVE analyses, so there is honestly nothing to map from those.
          </p>
        ) : (
          <ul className="mt-4 space-y-3">
            {zones.map((zone) => {
              const firstPriority = decisionSupport?.first_priority_zone_ids.includes(zone.id) ?? false;
              return (
                <li
                  key={zone.id}
                  className={`rounded-lg border px-4 py-3 ${firstPriority ? "border-red-300 bg-red-50/40" : "border-stone-200 bg-stone-50"}`}
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <span className={RISK_META[zone.risk_level].cls}>{RISK_META[zone.risk_level].label}</span>
                    <span className="chip-muted" title={zone.risk_basis}>
                      priority {zone.review_priority} — {zone.review_priority_note}
                    </span>
                    <span className={REVIEW_META[zone.review_status].cls}>{REVIEW_META[zone.review_status].label}</span>
                    {firstPriority ? <span className="chip-critical">review first</span> : null}
                  </div>
                  <p className="mt-2 text-sm font-semibold text-stone-900">
                    {zone.condition} · {(zone.confidence * 100).toFixed(0)}% confidence
                    {zone.severity !== null ? ` · visual severity ${(zone.severity * 100).toFixed(0)}% (proxy)` : ""}
                  </p>
                  <p className="mt-1 text-xs leading-5 text-stone-500">
                    {zone.simulation_label} · georeference: <strong>{zone.georeference_source}</strong> (
                    {zone.geometry.coordinate_space}){zone.area_note ? ` · ${zone.area_note}` : ""}
                  </p>
                  {zone.review_status !== "PENDING" && zone.reviewed_at ? (
                    <p className="mt-1 text-xs text-stone-500">
                      reviewed {new Date(zone.reviewed_at).toLocaleString()}
                      {zone.review_note ? ` — ${zone.review_note}` : ""}
                    </p>
                  ) : null}
                  <div className="mt-3 flex flex-wrap items-center gap-2">
                    <button
                      type="button"
                      className="btn-primary"
                      disabled={busyZone === zone.id}
                      onClick={() => review(zone, "APPROVED")}
                    >
                      Approve
                    </button>
                    <button
                      type="button"
                      className="btn-danger"
                      disabled={busyZone === zone.id}
                      onClick={() => review(zone, "REJECTED")}
                    >
                      Reject
                    </button>
                    <Link href={`/analyses/${zone.analysis_id}`} className="link-cta">
                      Source analysis →
                    </Link>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </section>
    </div>
  );
}
