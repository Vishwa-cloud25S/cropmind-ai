/**
 * Phase 15 (FR-20) — bundled demo sample photos.
 *
 * Up to five real, individually-attributed leaf photos served as static assets.
 * Provenance is stated per entry (source URL + license + byte sha256 prefix) and
 * pinned by tests — a silently swapped image is a failing build, not a surprise.
 *
 * The set deliberately mixes DOMAINS so the demo shows the honest truth live:
 * in-domain photos (what the 0.9959 number describes) and field photos (what the
 * 0.2349 out-of-distribution shortfall describes — abstentions and low bands
 * included, never hidden).
 */

export interface DemoSample {
  id: string;
  /** static asset path under public/demo-samples/ */
  file: string;
  /** picker label — states crop, condition and domain honestly */
  label: string;
  /** provenance line: dataset, repository, license */
  provenance: string;
  /** first 12 hex chars of the file's sha256 (integrity pin) */
  sha256_12: string;
  /** expectation-setting note shown next to the picker — never marketing */
  honestyNote: string;
}

export const DEMO_SAMPLES: readonly DemoSample[] = [
  {
    id: "pv-tomato-early-blight",
    file: "pv-tomato-early-blight.jpg",
    label: "Tomato — Early blight (in-domain photo)",
    provenance: "PlantVillage (Mendeley v1), CC0 1.0 — via github.com/spMohanty/PlantVillage-Dataset",
    sha256_12: "29b79036b677",
    honestyNote:
      "Uniform-background dataset photo: this family is what the 0.9959 in-domain score describes — a confident answer is expected.",
  },
  {
    id: "pv-potato-late-blight",
    file: "pv-potato-late-blight.jpg",
    label: "Potato — Late blight (in-domain photo)",
    provenance: "PlantVillage (Mendeley v1), CC0 1.0 — via github.com/spMohanty/PlantVillage-Dataset",
    sha256_12: "96baa8bba4a2",
    honestyNote:
      "Uniform-background dataset photo: this family is what the 0.9959 in-domain score describes — a confident answer is expected.",
  },
  {
    id: "pd-tomato-early-blight-field",
    file: "pd-tomato-early-blight-field.jpg",
    label: "Tomato — Early blight (field photo)",
    provenance: "PlantDoc test set, CC BY 4.0 (Singh et al.) — github.com/pratikkayal/PlantDoc-Dataset",
    sha256_12: "7d9c5c694755",
    honestyNote:
      "Real field photo: this family is what the 0.2349 out-of-distribution shortfall describes — the model may abstain or land low. That honesty is the point of the demo.",
  },
  {
    id: "pd-potato-late-blight-field",
    file: "pd-potato-late-blight-field.jpg",
    label: "Potato — Late blight (field photo)",
    provenance: "PlantDoc test set, CC BY 4.0 (Singh et al.) — github.com/pratikkayal/PlantDoc-Dataset",
    sha256_12: "c53ad8d40c38",
    honestyNote:
      "Real field photo: this family is what the 0.2349 out-of-distribution shortfall describes — the model may abstain or land low. That honesty is the point of the demo.",
  },
] as const;

export function sampleAssetPath(entry: DemoSample): string {
  return `/demo-samples/${entry.file}`;
}
