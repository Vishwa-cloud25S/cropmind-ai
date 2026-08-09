import Link from "next/link";

const NAV = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/analyze", label: "Analyze" },
  { href: "/farms", label: "Farms" },
  { href: "/map", label: "Map" },
  { href: "/simulate", label: "Simulate" },
  { href: "/reports", label: "Reports" },
  { href: "/analyses", label: "History" },
];

export default function SiteHeader() {
  return (
    <header className="sticky top-0 z-40 border-b border-stone-200 bg-white/90 backdrop-blur">
      <div className="container-shell flex h-16 items-center justify-between gap-4">
        <Link href="/" className="flex items-center gap-2.5" aria-label="CropMind AI home">
          <svg viewBox="0 0 64 64" className="h-8 w-8" aria-hidden="true">
            <rect width="64" height="64" rx="14" fill="#14211B" />
            <path
              d="M32 13c-8 6-12.5 11.8-12.5 18.7C19.5 38.8 25 46 32 46s12.5-7.2 12.5-14.3C44.5 24.8 40 19 32 13z"
              fill="#4CBB6A"
            />
            <path
              d="M32 22v21M26.5 29.5l5.5-3 5.5 3M25.5 36.5l6.5-3.4 6.5 3.4"
              stroke="#0E1A13"
              strokeWidth="2.3"
              strokeLinecap="round"
              strokeLinejoin="round"
              fill="none"
            />
          </svg>
          <span className="text-base font-bold tracking-tight text-stone-900">
            CropMind <span className="text-emerald-800">AI</span>
          </span>
        </Link>

        <nav aria-label="Primary" className="hidden items-center gap-6 md:flex">
          {NAV.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="text-sm font-medium text-stone-600 transition hover:text-emerald-900"
            >
              {item.label}
            </Link>
          ))}
        </nav>

        <div className="hidden items-center gap-3 md:flex">
          <Link href="/login" className="text-sm font-semibold text-stone-700 hover:text-emerald-900">
            Sign in
          </Link>
          <Link href="/dashboard" className="btn-primary">
            Try the Demo
          </Link>
        </div>

        <details className="group relative md:hidden">
          <summary
            className="flex h-10 w-10 cursor-pointer list-none items-center justify-center rounded-lg border border-stone-300"
            aria-label="Open menu"
          >
            <span className="space-y-1.5" aria-hidden="true">
              <span className="block h-0.5 w-5 bg-stone-700" />
              <span className="block h-0.5 w-5 bg-stone-700" />
              <span className="block h-0.5 w-5 bg-stone-700" />
            </span>
          </summary>
          <div className="absolute right-0 mt-2 w-56 rounded-xl border border-stone-200 bg-white p-3 shadow-lg">
            {NAV.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className="block rounded-lg px-3 py-2 text-sm font-medium text-stone-700 hover:bg-stone-100"
              >
                {item.label}
              </Link>
            ))}
            <Link href="/dashboard" className="btn-primary mt-2 w-full">
              Try the Demo
            </Link>
          </div>
        </details>
      </div>
    </header>
  );
}
