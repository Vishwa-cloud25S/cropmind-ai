import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "About",
  description:
    "Who builds CropMind AI, why it exists, and the honesty rules the product is held to — everything verifiable in the public repository.",
};

const REPO = "https://github.com/Vishwa-cloud25S/cropmind-ai";

const PRINCIPLES = [
  {
    heading: "Suspected, never certain",
    body: "Every verdict is phrased 'Suspected {crop} - {condition} - {x}% confidence'. Below the LOW confidence band the system abstains (INCONCLUSIVE) instead of dressing up a guess.",
  },
  {
    heading: "Bad numbers get published too",
    body: "The model card quotes in-domain and out-of-distribution evaluation results together, always — including the 0.2349 PlantDoc field OOD shortfall. Marketing may not quote one without the other.",
  },
  {
    heading: "No chemical advice, anywhere",
    body: "No pesticide product, brand or dosage guidance exists in the product. Intervention zones are simulations pending human review, and reports say so on their face.",
  },
  {
    heading: "Demo means demo",
    body: "Synthetic sample-model output and simulation features are flagged in the database, the API, the UI and downloaded PDFs. A silently upgraded claim is treated as a bug — please report it.",
  },
];

export default function AboutPage() {
  return (
    <div className="container-shell max-w-4xl py-10">
      <p className="eyebrow">About</p>
      <h1 className="section-title">One founder, building in the open.</h1>
      <p className="section-lede">
        CropMind AI is designed, built and documented by <strong>Vishwa Odduri</strong>, an independent solo
        founder. Every part of it — code, model configuration, evaluation results, deployment logs and business
        documents — lives in the public repository for anyone to inspect.
      </p>

      <section className="mt-10 space-y-4">
        <h2 className="text-lg font-semibold text-stone-900">Why it exists</h2>
        <p className="text-sm leading-7 text-stone-600">
          Crop protection is often applied uniformly across a whole field because growers cannot see precisely
          where the problem is. CropMind AI turns leaf imagery into explainable, reviewable intervention zones —
          with confidence, uncertainty and abstention shown honestly, so a person stays in charge of every
          decision.
        </p>
        <p className="text-sm leading-7 text-stone-600">
          The project is developed openly from India and is being prepared as part of a UK Innovator Founder
          visa endorsement journey — the business plan, financial model and evidence framework are public in the
          repository under <code>business/</code>.
        </p>
      </section>

      <section className="mt-10">
        <h2 className="text-lg font-semibold text-stone-900">The rules this product is held to</h2>
        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          {PRINCIPLES.map((principle) => (
            <article key={principle.heading} className="card">
              <h3 className="text-sm font-bold text-stone-900">{principle.heading}</h3>
              <p className="mt-2 text-sm leading-6 text-stone-600">{principle.body}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="mt-10 space-y-3">
        <h2 className="text-lg font-semibold text-stone-900">Verify everything</h2>
        <ul className="space-y-2 text-sm text-stone-600">
          <li>
            <a href={REPO} target="_blank" rel="noreferrer" className="font-medium text-emerald-900 underline">
              Source code, docs and business package (GitHub)
            </a>{" "}
            — the repository is the single source of truth; files win over any claim.
          </li>
          <li>
            Model card, evaluation reports and deployment log are linked from the repository README — including
            failed deploys, recorded verbatim and never erased.
          </li>
          <li>
            Questions, issues and corrections:{" "}
            <a
              href={`${REPO}/issues`}
              target="_blank"
              rel="noreferrer"
              className="font-medium text-emerald-900 underline"
            >
              open a GitHub issue
            </a>
            .
          </li>
        </ul>
      </section>
    </div>
  );
}
