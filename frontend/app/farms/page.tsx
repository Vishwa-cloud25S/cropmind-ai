import type { Metadata } from "next";

import FarmsManager from "@/components/FarmsManager";

export const metadata: Metadata = {
  title: "Farms",
  description: "Create and manage farms and fields; crops validated against the supported taxonomy.",
};

export default function FarmsPage() {
  return (
    <div className="container-shell max-w-4xl py-10">
      <p className="eyebrow">Farm structure</p>
      <h1 className="section-title">Farms</h1>
      <p className="section-lede">
        Farms group fields; fields carry the crop context analyses attach to. Delete is blocked — with counts
        shown — while dependent records exist.
      </p>
      <div className="mt-8">
        <FarmsManager />
      </div>
    </div>
  );
}
