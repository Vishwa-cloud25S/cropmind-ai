import Link from "next/link";

export default function SiteFooter() {
  return (
    <footer className="border-t border-stone-200 bg-white">
      <div className="container-shell grid gap-10 py-12 sm:grid-cols-2 lg:grid-cols-4">
        <div>
          <p className="text-sm font-bold text-stone-900">
            CropMind <span className="text-emerald-800">AI</span>
          </p>
          <p className="mt-3 text-sm leading-6 text-stone-600">
            Computer vision and precision mapping that turn crop-health imagery into
            explainable, geospatially localized intervention zones.
          </p>
          <p className="badge mt-4">Open-source MVP · in development</p>
        </div>
        <div>
          <p className="text-sm font-semibold text-stone-900">Product</p>
          <ul className="mt-3 space-y-2 text-sm text-stone-600">
            <li><Link href="/analyze" className="hover:text-emerald-900">Image analysis</Link></li>
            <li><Link href="/map" className="hover:text-emerald-900">Field mapping</Link></li>
            <li><Link href="/reports" className="hover:text-emerald-900">Field reports</Link></li>
            <li><Link href="/dashboard" className="hover:text-emerald-900">Farm dashboard</Link></li>
          </ul>
        </div>
        <div>
          <p className="text-sm font-semibold text-stone-900">Resources</p>
          <ul className="mt-3 space-y-2 text-sm text-stone-600">
            <li><Link href="/model-information" className="hover:text-emerald-900">Model information</Link></li>
            <li>
              <a
                href="https://github.com/Vishwa-cloud25S"
                target="_blank"
                rel="noreferrer"
                className="hover:text-emerald-900"
              >
                Source code (GitHub)
              </a>
            </li>
            <li>
              <a href="http://localhost:8000/docs" className="hover:text-emerald-900">
                API documentation (local)
              </a>
            </li>
          </ul>
        </div>
        <div>
          <p className="text-sm font-semibold text-stone-900">Legal &amp; trust</p>
          <ul className="mt-3 space-y-2 text-sm text-stone-600">
            <li><Link href="/privacy" className="hover:text-emerald-900">Privacy</Link></li>
            <li><Link href="/terms" className="hover:text-emerald-900">Terms</Link></li>
          </ul>
          <p className="mt-4 text-xs leading-5 text-stone-500">
            Decision support only — not agronomic advice, not a certain diagnosis, no chemical
            dosing. Sample/demo imagery is labelled as such.
          </p>
        </div>
      </div>
      <div className="border-t border-stone-100">
        <div className="container-shell flex flex-col gap-1 py-4 text-xs text-stone-500 sm:flex-row sm:items-center sm:justify-between">
          <span>Built with open-source software and publicly licensed datasets.</span>
          <span>Prototypes and simulations are labelled honestly — no fabricated claims.</span>
        </div>
      </div>
    </footer>
  );
}
