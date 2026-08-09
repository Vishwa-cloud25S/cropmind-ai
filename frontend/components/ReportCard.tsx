import { reportDownloadUrl } from "@/lib/api";
import type { ReportPayload } from "@/lib/types";
import { DemoBadge, PredictionStatusChip } from "@/components/StatusBadge";

/**
 * The READY report surfaced in the UI — pure presentational (vitest-friendly).
 * Renders the stored build basis verbatim: Suspected phrasing, review ledger,
 * demo flag. The PDF download is the artifact of record (files win); this card
 * is its honest preview, never a re-derivation.
 */
export default function ReportCard({ report }: { report: ReportPayload }) {
  const basis = report.basis;
  const href = reportDownloadUrl(report.id);
  return (
    <article aria-labelledby="report-heading" className="card space-y-4" data-testid="report-card">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="eyebrow">PDF field report</p>
          <h3 id="report-heading" className="mt-1 font-mono text-lg font-bold text-stone-900">
            {report.report_id}
          </h3>
          <p className="mt-1 text-xs text-stone-500">
            {report.generated_at ? `generated ${new Date(report.generated_at).toLocaleString()}` : "generation time pending"}
            {` · ${report.generator.name} ${report.generator.feature} v${report.generator.version}`}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {basis ? <PredictionStatusChip status={basis.prediction.status} /> : null}
          <DemoBadge demo={report.demo} />
        </div>
      </div>

      {basis ? (
        <>
          <p className="rounded-lg border border-stone-200 bg-stone-50 px-3 py-2 text-sm font-semibold text-stone-900">
            {basis.prediction.phrasing}
          </p>

          <dl className="grid gap-3 text-sm sm:grid-cols-3">
            <div className="stat-card">
              <dt className="field-label">Crop / condition</dt>
              <dd className="mt-1 font-semibold capitalize text-stone-900">
                {basis.prediction.status === "INCONCLUSIVE" ? "— (abstained)" : basis.prediction.crop}
              </dd>
              <dd className="text-xs text-stone-600">
                {basis.prediction.status === "INCONCLUSIVE" ? "below confidence threshold" : basis.prediction.condition_name}
              </dd>
            </div>
            <div className="stat-card">
              <dt className="field-label">Model</dt>
              <dd className="mt-1 font-semibold text-stone-900">
                {basis.model.name} · v{basis.model.version}
              </dd>
              <dd className="text-xs text-stone-600">dataset {basis.model.dataset_version ?? "not recorded"}</dd>
            </div>
            <div className="stat-card">
              <dt className="field-label">Zone review ledger</dt>
              <dd className="mt-1 font-semibold text-stone-900">
                {basis.zone_review_totals.PENDING} pending · {basis.zone_review_totals.APPROVED} approved ·{" "}
                {basis.zone_review_totals.REJECTED} rejected
              </dd>
              <dd className="text-xs text-stone-600">
                {basis.zones.length === 0 ? "no zones — abstention by design" : `${basis.zones.length} zone(s) on the report`}
              </dd>
            </div>
          </dl>

          {basis.field === null ? (
            <p className="text-xs text-stone-500">Printed as analysed without a field link — stated on the report, not invented.</p>
          ) : (
            <p className="text-xs text-stone-600">
              Field: <span className="font-semibold">{basis.field.name}</span>
              {basis.field.farm ? ` (${basis.field.farm})` : ""}
            </p>
          )}
        </>
      ) : null}

      <div className="flex flex-wrap items-center gap-3">
        <a href={href} className="btn-primary" download>
          Download PDF report
        </a>
        <p className="text-xs leading-5 text-stone-500">
          Decision support only — suspected finding, human review status included; no product or dosage content.
        </p>
      </div>
    </article>
  );
}
