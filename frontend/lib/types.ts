/** API payload types — mirrors the backend Phase 5/6 contract (docs/04). */

export interface ImageRecord {
  id: string;
  field_id: string | null;
  sha256: string;
  width: number;
  height: number;
  byte_size: number;
  captured_at: string | null;
  exif: Record<string, unknown> | null;
  source_type: string;
  created_at: string | null;
}

export interface ImageUploadResponse {
  image: ImageRecord & { deduplicated: boolean };
}

export interface AnalysisCreateResponse {
  analysis_id: string;
  job_id: string;
  status: string;
  poll: string;
  note: string;
}

export interface AnalysisJobStatus {
  id: string;
  status: "PENDING" | "RUNNING" | "COMPLETED" | "FAILED" | string;
  attempts: number;
  max_attempts: number;
}

export type AnalysisState = "QUEUED" | "PROCESSING" | "COMPLETED" | "FAILED";

export interface AnalysisStatus {
  analysis_id: string;
  image_id: string;
  status: AnalysisState;
  demo: boolean;
  created_at: string | null;
  started_at: string | null;
  completed_at: string | null;
  error: string | null;
  job?: AnalysisJobStatus;
}

export interface AnalysisList {
  count: number;
  analyses: AnalysisStatus[];
}

export interface RegionGeometry {
  type: "Polygon";
  coordinate_space: string;
  coordinates: number[][][];
}

export interface PredictionRegion {
  geometry: RegionGeometry;
  area_px: number | null;
  confidence: number | null;
}

export interface ModelIdentity {
  name: string;
  version: string;
  dataset_version: string | null;
  threshold_version: string | null;
  demo: boolean;
}

export type PredictionState = "SUSPECTED" | "INCONCLUSIVE";

export interface Prediction {
  prediction_id: string;
  analysis_id: string;
  status: PredictionState;
  phrasing: string;
  crop: string;
  condition: { disease_id: string; name: string };
  confidence: number;
  band: "HIGH" | "MEDIUM" | "LOW" | null;
  uncertainty: number;
  estimated_visual_severity: number | null;
  severity_label: string | null;
  latency_ms: number;
  demo: boolean;
  model: ModelIdentity;
  regions: PredictionRegion[];
  gradcam_available: boolean;
  created_at: string | null;
  analysis_demo_requested: boolean | null;
  client_notice: string;
  explainability_caveat: string;
  raw: Record<string, unknown>;
}

export interface PredictionList {
  count: number;
  predictions: Prediction[];
  client_notice: string;
}

export interface Farm {
  id: string;
  name: string;
  location: string | null;
  field_count: number;
  created_at: string | null;
}

export interface FarmList {
  count: number;
  farms: Farm[];
}

export interface FieldRecord {
  id: string;
  farm_id: string;
  name: string;
  crop_id: string | null;
  area_ha: number | null;
  boundary_geojson: { type: "Polygon"; coordinates: number[][][] } | null;
  created_at: string | null;
}

export interface FarmDetail {
  farm: Farm;
  fields: FieldRecord[];
}

// ── Phase 7: intervention zones + map ─────────────────────────────────────────

export type RiskLevel = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
export type ReviewStatus = "PENDING" | "APPROVED" | "REJECTED";

export interface InterventionZone {
  id: string;
  analysis_id: string;
  field_id: string | null;
  image_id: string | null;
  geometry: RegionGeometry; // evidence-space polygon (coordinate_space inside)
  condition: string;
  confidence: number;
  severity: number | null;
  risk_level: RiskLevel;
  risk_basis: string;
  review_priority: number; // 1 = review first
  review_priority_note: string;
  review_status: ReviewStatus;
  review_note: string | null;
  reviewed_at: string | null;
  georeference_source: "none";
  est_area_ha: number | null;
  area_note: string | null;
  simulation_label: string;
  created_at: string | null;
  review_transition?: string; // present in the PATCH response
}

export interface ZoneList {
  count: number;
  zones: InterventionZone[];
  simulation_label: string;
}

export interface ZoneGenerateResponse {
  count: number;
  zones: InterventionZone[];
  note: string;
  simulation_label: string;
}

export interface FieldMapAnalysis {
  analysis_id: string;
  image_id: string;
  status: AnalysisState;
  demo: boolean;
  created_at: string | null;
  prediction: {
    status: PredictionState;
    phrasing: string;
    band: "HIGH" | "MEDIUM" | "LOW" | null;
    confidence: number;
    demo: boolean;
  } | null;
}

export interface DecisionSupport {
  risk_counts: Record<RiskLevel, number>;
  review_counts: Record<ReviewStatus, number>;
  pending_zone_count: number;
  first_priority_zone_ids: string[];
  note: string;
  simulation_label: string;
}

export interface FieldMapData {
  field: FieldRecord & { farm_name: string | null };
  analyses: FieldMapAnalysis[];
  zones: InterventionZone[];
  decision_support: DecisionSupport;
}

export interface ConfidenceBands {
  low: number;
  medium: number;
  high: number;
}

export interface ModelInfo {
  model: Record<string, unknown>;
  confidence_bands: ConfidenceBands;
  uncertainty_method: string | null;
  severity_method: string | null;
  updated: string | null;
  registry_note: string;
  client_notice: string;
}

export interface ConditionInfo {
  disease_id: string;
  name: string;
  dataset_source: string | null;
  supported_by_model: boolean;
  confidence_threshold: number | null;
}

export interface CropInfo {
  crop_id: string;
  name: string;
  status: string;
  conditions: ConditionInfo[];
}

export interface SupportedCrops {
  taxonomy_version: string;
  updated: string | null;
  model_available: boolean;
  note: string | null;
  crop_count: number;
  crops: CropInfo[];
  disclaimer: string;
}
