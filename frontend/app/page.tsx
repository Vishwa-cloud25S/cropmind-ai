import Link from "next/link";

const PIPELINE = [
  "IMAGE",
  "DETECTION",
  "CONFIDENCE",
  "LOCALIZATION",
  "SEVERITY",
  "EXPLAINABILITY",
  "MAPPING",
  "ZONES",
  "SAVINGS*",
  "REVIEW",
  "REPORT",
];

const HOW_IT_WORKS = [
  {
    step: 1,
    title: "Capture",
    body: "Upload a smartphone photo, field image, or drone orthomosaic of a supported crop.",
  },
  {
    step: 2,
    title: "Detect",
    body: "The model returns a suspected condition with a confidence score and model version — never a claimed certainty.",
  },
  {
    step: 3,
    title: "Explain",
    body: "A Grad-CAM heatmap shows which regions contributed most to the prediction, with uncertainty recorded.",
  },
  {
    step: 4,
    title: "Localize & map",
    body: "Suspected regions become georeferenced zones layered onto your field on an OpenStreetMap map.",
  },
  {
    step: 5,
    title: "Target",
    body: "Precision intervention zones are generated. A human approves or rejects every zone — nothing is prescribed.",
  },
  {
    step: 6,
    title: "Report & learn",
    body: "Download a field report. Feedback (was it right? what was it actually?) builds a verified knowledge base over time.",
  },
];

const LIMITATIONS = [
  "Screening, not diagnosis — every result is a suspected condition with a confidence level.",
  "Severity is an estimated visual severity (affected-area percentage), not an agronomic measurement.",
  "Explainability highlights correlation, not proof of disease location or cause.",
  "Savings and environmental figures are simulations until field trials validate them.",
  "No pesticide product, brand, rate, or legal-approval advice is given — ever.",
  "Coverage is limited to the crops/conditions with licensed data and published evaluation.",
];

export default function LandingPage() {
  return (
    <>
      {/* ── Hero ─────────────────────────────────────────── */}
      <section className="border-b border-stone-200 bg-white">
        <div className="container-shell grid items-center gap-12 py-16 lg:grid-cols-2 lg:py-24">
          <div>
            <p className="badge">Open-source precision agriculture · MVP in development</p>
            <h1 className="mt-5 text-4xl font-extrabold tracking-tight text-stone-900 sm:text-5xl">
              See the problem before you spray the field.
            </h1>
            <p className="mt-5 max-w-xl text-lg leading-8 text-stone-600">
              CropMind AI uses computer vision and precision mapping to identify suspected crop
              health issues and help farmers target intervention areas instead of treating an
              entire field.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link href="/dashboard" className="btn-primary">
                Try the Demo
              </Link>
              <Link href="/#how-it-works" className="btn-secondary">
                How it works
              </Link>
            </div>
            <p className="mt-4 text-xs text-stone-500">
              Decision support — human verification required. Savings shown as simulations.
            </p>
          </div>

          {/* Conceptual UI mock — illustrative, clearly not a real screenshot */}
          <div className="relative" aria-hidden="true">
            <div className="card p-4">
              <div className="grid grid-cols-4 gap-1.5">
                {Array.from({ length: 12 }).map((_, i) => (
                  <div
                    key={i}
                    className={
                      "aspect-square rounded-md " +
                      (i === 6
                        ? "bg-emerald-700 ring-2 ring-dashed ring-amber-500 ring-offset-2"
                        : ["bg-emerald-900/90", "bg-emerald-800/80", "bg-moss-800/70", "bg-stone-300"][i % 4])
                    }
                  />
                ))}
              </div>
              <div className="mt-3 flex items-center justify-between rounded-lg bg-stone-100 px-3 py-2.5">
                <span className="text-xs font-semibold text-stone-700">
                  Suspected: Tomato · Early blight — 87%
                </span>
                <span className="badge-warn">review required</span>
              </div>
              <div className="mt-3 flex items-center gap-2 rounded-lg border border-dashed border-emerald-800/30 bg-emerald-50/60 px-3 py-2.5">
                <span className="h-3 w-3 rounded-full bg-emerald-700/70" />
                <span className="h-3 w-3 rounded-full bg-amber-500/70" />
                <span className="text-xs font-medium text-stone-600">
                  Intervention zones on field map · simulation
                </span>
              </div>
            </div>
            <p className="mt-2 text-center text-[11px] text-stone-400">
              Conceptual illustration of the analysis view
            </p>
          </div>
        </div>
      </section>

      {/* ── Problem ──────────────────────────────────────── */}
      <section id="product" className="container-shell py-16">
        <p className="eyebrow">The problem</p>
        <h2 className="section-title">Crop protection is often applied uniformly — because we can&apos;t see precisely.</h2>
        <div className="mt-10 grid gap-6 md:grid-cols-3">
          <div className="card">
            <h3 className="font-semibold text-stone-900">Blanket treatment</h3>
            <p className="mt-2 text-sm leading-6 text-stone-600">
              Without precise, timely information, whole fields are often sprayed when only a
              fraction may actually need attention — raising input costs and exposure.
            </p>
          </div>
          <div className="card">
            <h3 className="font-semibold text-stone-900">Scouting doesn&apos;t scale</h3>
            <p className="mt-2 text-sm leading-6 text-stone-600">
              Walking fields and inspecting leaves by eye is slow, skill-dependent, and hard to
              repeat consistently across large areas and tight decision windows.
            </p>
          </div>
          <div className="card">
            <h3 className="font-semibold text-stone-900">Missing evidence trail</h3>
            <p className="mt-2 text-sm leading-6 text-stone-600">
              Observations, imagery and treatment decisions are rarely connected in one place, so
              learning season over season stays anecdotal.
            </p>
          </div>
        </div>
      </section>

      {/* ── Solution / pipeline ──────────────────────────── */}
      <section className="border-y border-stone-200 bg-white">
        <div className="container-shell py-16">
          <p className="eyebrow">The solution</p>
          <h2 className="section-title">
            From image to intervention zones — with a human in the loop.
          </h2>
          <p className="section-lede">
            Not “AI that detects plant disease”. A reviewable workflow that converts imagery into
            geospatially localized zones a farmer or agronomist approves or rejects.
          </p>
          <div className="mt-8 flex flex-wrap items-center gap-2">
            {PIPELINE.map((token, i) => (
              <span key={token} className="flex items-center gap-2">
                <span className="pipeline-token">{token}</span>
                {i < PIPELINE.length - 1 && (
                  <span className="text-stone-400" aria-hidden="true">→</span>
                )}
              </span>
            ))}
          </div>
          <p className="mt-3 text-xs text-stone-500">* estimated input savings — model simulation, pending field validation</p>
        </div>
      </section>

      {/* ── How it works ─────────────────────────────────── */}
      <section id="how-it-works" className="container-shell py-16">
        <p className="eyebrow">How it works</p>
        <h2 className="section-title">Six steps, three minutes, zero certainty claims.</h2>
        <ol className="mt-10 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {HOW_IT_WORKS.map((item) => (
            <li key={item.step} className="card flex gap-4">
              <span className="num-chip">{item.step}</span>
              <div>
                <h3 className="font-semibold text-stone-900">{item.title}</h3>
                <p className="mt-1.5 text-sm leading-6 text-stone-600">{item.body}</p>
              </div>
            </li>
          ))}
        </ol>
      </section>

      {/* ── AI technology + mapping ──────────────────────── */}
      <section id="mapping" className="border-y border-stone-200 bg-white">
        <div className="container-shell grid gap-12 py-16 lg:grid-cols-2">
          <div>
            <p className="eyebrow">AI technology</p>
            <h2 className="section-title">Transparent models, honest confidence.</h2>
            <ul className="mt-6 space-y-3 text-sm leading-6 text-stone-600">
              <li className="flex gap-2"><span className="text-emerald-800" aria-hidden="true">▸</span> Open-source models trained on publicly licensed datasets (provenance documented).</li>
              <li className="flex gap-2"><span className="text-emerald-800" aria-hidden="true">▸</span> Every prediction stores confidence, uncertainty, model and dataset version.</li>
              <li className="flex gap-2"><span className="text-emerald-800" aria-hidden="true">▸</span> Confidence bands are configuration, tuned only on published evaluation.</li>
              <li className="flex gap-2"><span className="text-emerald-800" aria-hidden="true">▸</span> Grad-CAM visualizes what influenced the model — labelled as correlation.</li>
              <li className="flex gap-2"><span className="text-emerald-800" aria-hidden="true">▸</span> Metrics are measured and reported honestly — including out-of-domain results.</li>
            </ul>
            <Link href="/model-information" className="btn-secondary mt-6">
              Model information
            </Link>
          </div>
          <div>
            <p className="eyebrow">Precision mapping</p>
            <h2 className="section-title">Zones you can review, export, and act on.</h2>
            <ul className="mt-6 space-y-3 text-sm leading-6 text-stone-600">
              <li className="flex gap-2"><span className="text-emerald-800" aria-hidden="true">▸</span> Field boundaries and zones on Leaflet + OpenStreetMap — free, no API lock-in.</li>
              <li className="flex gap-2"><span className="text-emerald-800" aria-hidden="true">▸</span> approve / reject for every suggested intervention zone.</li>
              <li className="flex gap-2"><span className="text-emerald-800" aria-hidden="true">▸</span> GeoJSON + CSV exports labelled “precision intervention zone simulation”.</li>
              <li className="flex gap-2"><span className="text-emerald-800" aria-hidden="true">▸</span> Drone/sprayer integration via provider interfaces — simulated until certified hardware partners exist.</li>
            </ul>
            <Link href="/map" className="btn-secondary mt-6">
              Field mapping
            </Link>
          </div>
        </div>
      </section>

      {/* ── Environmental benefits (honest) ──────────────── */}
      <section className="container-shell py-16">
        <div className="card border-amber-600/20 bg-amber-50/50">
          <p className="eyebrow text-amber-700">Environmental potential — simulated, not proven</p>
          <h2 className="section-title">Less area treated could mean less input used. We say “could” on purpose.</h2>
          <p className="section-lede">
            Targeted intervention aims to reduce the treated fraction of a field. CropMind shows the
            estimated treated-area reduction as a <strong>model-based simulation</strong> — clearly
            separated from any field-validated result. We publish no environmental impact claims
            until pilot trials produce real evidence.
          </p>
        </div>
      </section>

      {/* ── Limitations ──────────────────────────────────── */}
      <section className="border-y border-stone-200 bg-white">
        <div className="container-shell py-16">
          <p className="eyebrow">Limitations</p>
          <h2 className="section-title">What CropMind does not do.</h2>
          <ul className="mt-8 grid gap-4 md:grid-cols-2">
            {LIMITATIONS.map((item) => (
              <li key={item} className="flex gap-3 rounded-lg border border-stone-200 bg-stone-50 p-4 text-sm leading-6 text-stone-700">
                <span className="mt-1 h-4 w-4 shrink-0 rounded-full border-2 border-amber-500" aria-hidden="true" />
                {item}
              </li>
            ))}
          </ul>
        </div>
      </section>

      {/* ── Roadmap + contact ────────────────────────────── */}
      <section className="container-shell grid gap-12 py-16 lg:grid-cols-2">
        <div>
          <p className="eyebrow">Roadmap</p>
          <h2 className="section-title">Milestones, measured honestly.</h2>
          <ol className="mt-8 space-y-4">
            {[
              { m: "M1 — Vertical slice", s: "Image → prediction + explainability + severity + PDF report, with published evaluation", phase: "Phases 2–4" },
              { m: "M2 — Product slice", s: "Auth, farms & fields, maps, zones, simulator, feedback, admin", phase: "Phases 5–10" },
              { m: "M3 — Presentable MVP", s: "Demo mode, deployment, full docs incl. model & data cards", phase: "Phases 11–15" },
              { m: "Beyond", s: "Pilot trials, verified dataset, drone adapters, UK commercial pilots", phase: "post-MVP" },
            ].map((item) => (
              <li key={item.m} className="card flex items-start justify-between gap-4 py-4">
                <div>
                  <p className="font-semibold text-stone-900">{item.m}</p>
                  <p className="mt-1 text-sm text-stone-600">{item.s}</p>
                </div>
                <span className="badge shrink-0">{item.phase}</span>
              </li>
            ))}
          </ol>
        </div>
        <div className="flex flex-col justify-center rounded-xl bg-emerald-900 p-8 text-emerald-50">
          <p className="eyebrow text-emerald-300">Contact</p>
          <h2 className="mt-2 text-2xl font-bold tracking-tight text-white">
            Pilots, agronomy partners, and honest feedback are welcome.
          </h2>
          <p className="mt-3 text-sm leading-6 text-emerald-100/90">
            CropMind is an early-stage open-source project being built in public. If you farm,
            advise farmers, or operate drone services — your scepticism is as valuable as your
            interest.
          </p>
          <div className="mt-6">
            <a
              href="https://github.com/Vishwa-cloud25S"
              target="_blank"
              rel="noreferrer"
              className="btn-secondary border-transparent bg-white text-emerald-900 hover:bg-emerald-50"
            >
              GitHub — Vishwa-cloud25S
            </a>
          </div>
        </div>
      </section>
    </>
  );
}
