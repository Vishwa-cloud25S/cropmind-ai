import type { Metadata } from "next";
import dynamic from "next/dynamic";

// Leaflet inside the drawer/route views needs a real browser layout.
const SpraySimulator = dynamic(() => import("@/components/SpraySimulator"), {
  ssr: false,
  loading: () => <p className="text-sm text-stone-500">Loading the simulator…</p>,
});

export const metadata: Metadata = {
  title: "Spray simulator",
  description:
    "Labelled precision input-application simulation: mark treatment areas on your drawn boundary, get route, volumes and savings — SIMULATION only.",
};

export default function SimulatePage() {
  return (
    <div className="container-shell max-w-5xl py-10">
      <p className="eyebrow">SIMULATION — clearly labelled</p>
      <h1 className="section-title">Precision spray simulator</h1>
      <p className="section-lede">
        Draw what to treat on your field boundary, declare your own rate, and see the boustrophedon route,
        treated vs untreated area, input volumes and savings — every figure a planning SIMULATION, stored
        reproducibly. No product, chemical or dosage guidance exists here.
      </p>
      <div className="mt-8">
        <SpraySimulator />
      </div>
    </div>
  );
}
