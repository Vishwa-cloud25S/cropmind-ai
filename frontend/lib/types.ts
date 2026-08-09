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
  created_at: string | null;
}

export interface FarmDetail {
  farm: Farm;
  fields: FieldRecord[];
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
