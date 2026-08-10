import type { Metadata } from "next";

import SettingsPanel from "@/components/SettingsPanel";

export const metadata: Metadata = {
  title: "Settings",
  description: "Your CropMind AI account: session truth, role, and pointers to the live model configuration.",
};

export default function SettingsPage() {
  return (
    <div className="container-shell max-w-3xl py-10">
      <p className="eyebrow">Account</p>
      <h1 className="section-title">Settings</h1>
      <p className="section-lede">
        What your session actually is — account, role, token expiry — plus honest pointers to where model
        thresholds and farm defaults live (no shadow configuration here).
      </p>
      <div className="mt-8">
        <SettingsPanel />
      </div>
    </div>
  );
}
