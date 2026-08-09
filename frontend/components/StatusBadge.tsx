import type { AnalysisState, PredictionState } from "@/lib/types";

/** Colour is never the only signal — every chip carries its label as text. */

const BAND_META: Record<string, { cls: string; label: string; hint: string }> = {
  HIGH: { cls: "chip-high", label: "HIGH confidence", hint: "≥ high band threshold" },
  MEDIUM: { cls: "chip-medium", label: "MEDIUM confidence", hint: "≥ medium band threshold" },
  LOW: { cls: "chip-low", label: "LOW confidence", hint: "needs caution" },
};

export function BandChip({ band }: { band: "HIGH" | "MEDIUM" | "LOW" | null }) {
  if (!band) {
    return <span className="chip-muted">INCONCLUSIVE — below LOW band</span>;
  }
  const meta = BAND_META[band];
  return <span className={meta.cls} title={meta.hint}>{meta.label}</span>;
}

const PREDICTION_META: Record<PredictionState, { cls: string; label: string }> = {
  SUSPECTED: { cls: "chip-info", label: "SUSPECTED — verify before acting" },
  INCONCLUSIVE: { cls: "chip-muted", label: "INCONCLUSIVE — retake photo" },
};

export function PredictionStatusChip({ status }: { status: PredictionState }) {
  const meta = PREDICTION_META[status];
  return <span className={meta.cls}>{meta.label}</span>;
}

const ANALYSIS_META: Record<AnalysisState | string, { cls: string; label: string }> = {
  QUEUED: { cls: "chip-muted", label: "QUEUED" },
  PROCESSING: { cls: "chip-info", label: "PROCESSING" },
  COMPLETED: { cls: "chip-high", label: "COMPLETED" },
  FAILED: { cls: "chip-low", label: "FAILED" },
};

export function AnalysisStatusChip({ status, demo }: { status: AnalysisState; demo?: boolean }) {
  const meta = ANALYSIS_META[status] ?? { cls: "chip-muted", label: status };
  return (
    <span className="inline-flex items-center gap-2">
      <span className={meta.cls}>{meta.label}</span>
      {demo ? <span className="chip-muted" title="This analysis ran against the clearly-flagged demo sample model">demo image</span> : null}
    </span>
  );
}

export function DemoBadge({ demo }: { demo: boolean }) {
  if (!demo) return null;
  return <span className="chip-low" title="Produced by the synthetic sample model — plumbing demo, never a crop-performance claim">DEMO MODEL</span>;
}
