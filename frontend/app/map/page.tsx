import type { Metadata } from "next";
import dynamic from "next/dynamic";

// Leaflet needs a real browser layout — the whole view is client-rendered.
const MapView = dynamic(() => import("@/components/MapView"), {
  ssr: false,
  loading: () => <p className="text-sm text-stone-500">Loading the map…</p>,
});

export const metadata: Metadata = {
  title: "Field map",
  description:
    "Leaflet + OpenStreetMap field boundaries, intervention-zone review and evidence overlays — zones stay in honest image space.",
};

export default function FieldMapPage({ searchParams }: { searchParams: { field?: string } }) {
  return (
    <div className="container-shell max-w-5xl py-10">
      <p className="eyebrow">Precision intervention simulation</p>
      <h1 className="section-title">Field map</h1>
      <p className="section-lede">
        Draw the boundary (real GPS geography you provide), review generated zones, approve or reject. Zones are
        honest simulations in image space until a georeferenced imagery source exists — the map will never invent
        a location.
      </p>
      <div className="mt-8">
        <MapView initialFieldId={searchParams.field} />
      </div>
    </div>
  );
}
