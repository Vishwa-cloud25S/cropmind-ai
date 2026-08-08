import type { Metadata } from "next";
import type { ReactNode } from "react";

import "./globals.css";
import SiteFooter from "@/components/SiteFooter";
import SiteHeader from "@/components/SiteHeader";

export const metadata: Metadata = {
  title: {
    default: "CropMind AI — see the problem before you spray the field",
    template: "%s · CropMind AI",
  },
  description:
    "Open-source precision agriculture: computer vision turns crop-health imagery into explainable, geospatially localized intervention zones. Decision support, never a certain diagnosis.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-stone-50 text-stone-900 antialiased">
        <a href="#content" className="skip-link">
          Skip to content
        </a>
        <SiteHeader />
        <main id="content">{children}</main>
        <SiteFooter />
      </body>
    </html>
  );
}
