import { notFound } from "next/navigation";

/**
 * Route stubs for the full product surface (spec §29). Each entry states which
 * phase delivers the page and what it will contain — nothing here is a mock of
 * working functionality. Static routes added later override this catch-all.
 */

type Stub = {
  title: string;
  phase: string;
  lede: string;
  bullets: string[];
};

type InfoPage = {
  title: string;
  kind: "info";
  intro: string;
  sections: { heading: string; body: string }[];
};

const STUBS: Record<string, Stub> = {
  login: {
    title: "Sign in",
    phase: "Phase 10 · Authentication",
    lede: "JWT sign-in with hashed passwords and protected routes.",
    bullets: ["Email + password authentication", "Session management with short-lived tokens", "Role-aware routing (Farmer / Agronomist / Admin)"],
  },
  register: {
    title: "Create account",
    phase: "Phase 10 · Authentication",
    lede: "Account creation for farmers, agronomists and admins.",
    bullets: ["Self-serve signup", "bcrypt password hashing", "Terms acceptance recorded in audit log"],
  },
  dashboard: {
    title: "Farm dashboard",
    phase: "Phase 6 · Frontend core + Phase 15 · Demo mode",
    lede: "The evaluator's entry point. Demo mode will run here without an account.",
    bullets: [
      "Cards: total fields, images analysed, detected issues, high-risk zones",
      "Estimated treated-area reduction (labelled simulation)",
      "Historical field health + recent analyses with charts",
      "Demo mode: 3–5 bundled sample images end-to-end",
    ],
  },
  farms: {
    title: "Farms",
    phase: "Phase 6 · Frontend core",
    lede: "Farm and field management.",
    bullets: ["Create / edit / delete farms", "Field list with crop, area, last analysis status", "Quick links to map and history"],
  },
  fields: {
    title: "Field",
    phase: "Phases 6–7",
    lede: "Single-field view with boundary and analysis history.",
    bullets: ["Draw/edit boundary on OpenStreetMap", "Upload imagery, run analysis", "Historical observations timeline"],
  },
  analysis: {
    title: "Analysis",
    phase: "Phases 3–6",
    lede: "One analysis, completely traceable.",
    bullets: [
      "Suspected condition + confidence band + uncertainty",
      "Grad-CAM overlay with the honest caveat",
      "Estimated visual severity (labelled as such)",
      "Model + dataset version shown; feedback: YES / NO / NOT SURE",
    ],
  },
  upload: {
    title: "Upload imagery",
    phase: "Phase 5 · Backend core",
    lede: "Single and batch uploads: smartphone, field camera, drone orthomosaic.",
    bullets: [
      "JPEG / PNG / TIFF validation with size limits",
      "Thumbnail + metadata (EXIF/GeoTIFF) extraction",
      "Tiling pipeline for large orthomosaics (no giant browser loads)",
      "Processing status: PENDING → PROCESSING → COMPLETED / FAILED",
    ],
  },
  map: {
    title: "Field map",
    phase: "Phase 7 · Geospatial mapping",
    lede: "Leaflet + OpenStreetMap. No Google Maps APIs.",
    bullets: [
      "Field boundary, detection regions, intervention zones as toggleable layers",
      "Select a zone → approve / reject",
      "Export GeoJSON / CSV labelled 'precision intervention zone simulation'",
      "Historical observations per field",
    ],
  },
  history: {
    title: "Analysis history",
    phase: "Phase 6",
    lede: "Every analysis persisted and comparable.",
    bullets: ["Filter by field, crop, condition, confidence", "Field health trend over time", "Field-to-field comparison"],
  },
  reports: {
    title: "Field reports",
    phase: "Phase 9",
    lede: "Downloadable PDF reports with everything needed for review.",
    bullets: [
      "Crop, field, date, image, condition, confidence, severity, zones",
      "Model version + important limitations + human review status",
      "Unique report ID for traceability",
    ],
  },
  settings: {
    title: "Settings",
    phase: "Phase 10",
    lede: "Account, farm defaults and transparency knobs.",
    bullets: ["Profile + role", "Farm defaults (units, area)", "View active confidence thresholds (from model.yaml)"],
  },
};

const INFO: Record<string, InfoPage> = {
  "model-information": {
    title: "Model information",
    kind: "info",
    intro:
      "Current status: NOT TRAINED (Phase 1). This page mirrors ml/configs/model.yaml and docs; it will show live registry data (via /model-info) once the backend core lands.",
    sections: [
      { heading: "Baseline (planned, Phase 3)", body: "Transfer-learned MobileNetV3-Small (torchvision, BSD license) trained on a 4-crop PlantVillage subset: Tomato, Potato, Corn, Apple — 21 condition classes. A permissively licensed detector (torchvision Faster R-CNN or YOLOX) follows for field imagery, trained on PlantDoc (CC BY 4.0)." },
      { heading: "Confidence bands (from ml/configs/model.yaml)", body: "High ≥ 0.60 · Medium ≥ 0.45 · Low ≥ 0.25 · below that: 'inconclusive — retake photo / agronomist review advised'. Bands are configuration, tuned only with published evaluation evidence." },
      { heading: "Uncertainty & explainability", body: "Each prediction reports predictive-entropy uncertainty and a Grad-CAM overlay. Highlighted regions show areas that contributed strongly to a prediction — they are not a guarantee of disease location and not causal proof." },
      { heading: "Evaluation policy", body: "Metrics are generated by the evaluation pipeline into reports/model_evaluation/ and published in docs/06-model-card.md — including out-of-domain results on PlantDoc field imagery. Poor results get reported, not hidden." },
      { heading: "Versioning", body: "Every prediction will record model name, model version, dataset version and threshold version, enabling reproducibility and honest audits." },
    ],
  },
  about: {
    title: "About CropMind AI",
    kind: "info",
    intro: "An open-source precision-agriculture MVP built like a company, not a demo.",
    sections: [
      { heading: "What we believe", body: "Precision protection beats blanket spraying — but only if the farmer can see, question, and overrule what the software suggests. Trust is a feature." },
      { heading: "How we build", body: "Open source first; publicly licensed data with documented provenance; honest metrics; simulations labelled as simulations; no fabricated claims about accuracy, customers, or impact." },
      { heading: "Founder", body: "[Founder bio to be completed in endorsement/founder-profile.md — built by an engineer with a computer-science background and data-engineering experience.]" },
    ],
  },
};

const LEGAL: Record<string, InfoPage> = {
  privacy: {
    title: "Privacy (development draft)",
    kind: "info",
    intro:
      "Draft for the development deployment. A formal policy will follow a proper legal review before any production use — we do not claim GDPR compliance.",
    sections: [
      { heading: "What is collected", body: "Accounts (when auth lands): email + password hash. Uploaded images, analysis results, feedback, and audit events (logins, uploads, zone reviews). Demo mode: no account data; sample imagery only." },
      { heading: "Why", body: "To provide the service: run analyses, show history, generate reports. A future, separately-consented programme may let users opt into images being used to improve models — it is not enabled now." },
      { heading: "Storage", body: "Local deployments: your own disk and Postgres. Hosted deployments will name the providers (acting as processors) at deploy time." },
      { heading: "Retention & deletion", body: "You can request deletion of your account and uploaded data. A formal retention schedule will be published before production." },
      { heading: "Contact", body: "Privacy questions: open an issue on the project GitHub." },
    ],
  },
  terms: {
    title: "Terms (development draft)",
    kind: "info",
    intro:
      "Draft terms for the development deployment. To be reviewed professionally before any commercial offering.",
    sections: [
      { heading: "The service", body: "CropMind AI provides decision-support screening: probabilistic indications of suspected crop-health conditions, visualized explainability, and precision-intervention simulations." },
      { heading: "Not professional advice", body: "Outputs are not definitive diagnoses, agronomic recommendations, or pesticide advice. No product, brand, dose, or legal-approval guidance is provided. Verify with a qualified agronomist before any field action." },
      { heading: "Simulations", body: "Treated-area, cost and environmental figures are model-based simulations unless explicitly labelled as field-validated. They are planning illustrations, not guarantees." },
      { heading: "No warranty", body: "Experimental software provided 'as is'. Use at your own risk; liability limited to the extent permitted by law." },
    ],
  },
};

function StubView({ stub }: { stub: Stub }) {
  return (
    <div className="container-shell max-w-3xl py-16">
      <p className="badge">{stub.phase}</p>
      <h1 className="section-title">{stub.title}</h1>
      <p className="section-lede">{stub.lede}</p>
      <div className="card mt-8">
        <p className="text-sm font-semibold text-stone-900">Landing here in the roadmap:</p>
        <ul className="mt-3 space-y-2.5 text-sm leading-6 text-stone-600">
          {stub.bullets.map((b) => (
            <li key={b} className="flex gap-2">
              <span aria-hidden="true" className="text-emerald-800">▸</span>
              {b}
            </li>
          ))}
        </ul>
      </div>
      <p className="mt-6 text-xs text-stone-500">
        This is an intentional placeholder on the public build plan (docs/14-roadmap.md) — not a
        mock of working functionality.
      </p>
    </div>
  );
}

function InfoView({ page }: { page: InfoPage }) {
  return (
    <div className="container-shell max-w-3xl py-16">
      <h1 className="section-title">{page.title}</h1>
      <p className="section-lede">{page.intro}</p>
      <div className="mt-10 space-y-8">
        {page.sections.map((s) => (
          <section key={s.heading}>
            <h2 className="text-lg font-semibold text-stone-900">{s.heading}</h2>
            <p className="mt-2 text-sm leading-7 text-stone-600">{s.body}</p>
          </section>
        ))}
      </div>
    </div>
  );
}

export default function PlaceholderRoute({ params }: { params: { slug: string[] } }) {
  const key = params.slug[0];
  const stub = STUBS[key];
  if (stub) return <StubView stub={stub} />;
  const page = INFO[key] ?? LEGAL[key];
  if (page) return <InfoView page={page} />;
  notFound();
}
