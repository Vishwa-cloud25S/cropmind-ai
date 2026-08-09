import type { Metadata } from "next";

import { FarmDetailPanel } from "@/components/FarmsManager";

export const metadata: Metadata = {
  title: "Farm",
  description: "Farm detail: rename, delete and manage fields with taxonomy-validated crops.",
};

export default function FarmPage({ params }: { params: { id: string } }) {
  return (
    <div className="container-shell max-w-4xl py-10">
      <FarmDetailPanel farmId={params.id} />
    </div>
  );
}
