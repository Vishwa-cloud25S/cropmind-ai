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

// ── Phase 8: simulation ───────────────────────────────────────────────────────

export interface RouteFeature {
  type: "Feature";
  geometry: { type: "LineString"; coordinates: number[][] };
  properties: { spray_on: boolean; length_m: number };
}

export interface SprayResults {
  field_area_ha: number;
  treated_area_ha: number;
  untreated_area_ha: number;
  treated_fraction: number;
  swath_count: number;
  spray_on_length_m: number;
  route_length_m: number;
  est_time_s: number;
  blanket_volume_l: number;
  precision_volume_l: number;
  savings_volume_l: number;
  savings_pct: number;
  route_geojson: { type: "FeatureCollection"; simulation: string; features: RouteFeature[] };
  simulation_label: string;
  assumptions: string[];
  provider_receipt: { provider: string; mission_id: string; status: string; note: string };
  engine: { package: string; version: string };
  honesty_notice: string;
}

export interface SprayPlanParams {
  field_id: string;
  boundary_geojson: { type: "Polygon"; coordinates: number[][][] };
  treatment_polygons: { type: "Polygon"; coordinates: number[][][] }[];
  spray_width_m: number;
  speed_mps: number;
  declared_rate_l_per_ha: number;
  turn_overhead_s: number;
}

export interface SimulationRunDetail {
  simulation_id: string;
  run_kind: "SPRAY_PLAN";
  field_id: string;
  mission_id: string | null;
  created_at: string | null;
  simulation_label: string;
  saved_inputs_echo: boolean;
  params: SprayPlanParams;
  results: SprayResults;
}

export interface SimulationSummary {
  simulation_id: string;
  run_kind: "SPRAY_PLAN";
  field_id: string;
  created_at: string | null;
  simulation_label: string;
  key_results: {
    treated_fraction: number;
    savings_pct: number;
    savings_volume_l: number;
    swath_count: number;
  };
}

export interface SimulationList {
  count: number;
  simulations: SimulationSummary[];
  note: string;
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

// ── Phase 9: PDF field reports (FR-19) ────────────────────────────────────────

export interface ReportZoneFact {
  id: string;
  risk_level: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
  condition: string;
  confidence: number;
  severity: number | null;
  review_status: "PENDING" | "APPROVED" | "REJECTED";
  review_note: string | null;
  reviewed_at: string | null;
  coordinate_space: string;
  georeference_source: string;
}

/** Everything printed on the PDF — a snapshot of stored state (files win). */
export interface ReportBasis {
  analysis_id: string;
  analysis_status: string;
  demo: boolean;
  generated_at_utc: string;
  prediction: {
    phrasing: string;
    status: PredictionState;
    crop: string;
    condition: string;
    condition_name: string;
    confidence: number;
    band: "HIGH" | "MEDIUM" | "LOW" | null;
    uncertainty: number;
    severity: number | null;
    severity_label: string;
    latency_ms: number;
    limitation_notice: string;
    explainability_caveat: string;
  };
  model: { name: string; version: string; dataset_version: string | null; demo: boolean | null };
  image: {
    id: string;
    captured_at: string | null;
    width: number;
    height: number;
    source_type: string;
    sha256_12: string;
  };
  field: { farm: string | null; name: string; crop_id: string | null; area_ha: number | null } | null;
  zones: ReportZoneFact[];
  zone_review_totals: Record<"PENDING" | "APPROVED" | "REJECTED", number>;
}

export interface ReportKeyFacts {
  analysis_status: string;
  prediction_status: string | null;
  prediction_phrasing: string | null;
  zones_total: number;
  zone_review_totals: Record<"PENDING" | "APPROVED" | "REJECTED", number>;
}

export interface ReportPayload {
  id: string;
  report_id: string; // human-facing, e.g. CMA-20260809-AB12CD
  analysis_id: string;
  generated_at: string | null;
  demo: boolean;
  generator: { name: string; feature: string; version: string };
  download_url: string;
  hint: string;
  basis?: ReportBasis; // present on full payloads
  key_facts?: ReportKeyFacts; // present on list summaries
}

/**
 * Analysis-scoped report state: READY carries the full payload; GENERATE means
 * none exists yet (with a verbatim honesty reason in `why`) — never a 404 flow.
 */
export interface AnalysisReportView {
  status: "READY" | "GENERATE";
  report: ReportPayload | null;
  why: string | null;
}

export interface ReportList {
  count: number;
  total: number;
  reports: ReportPayload[];
  note: string;
}

// ── Phase 10: auth, feedback, admin ───────────────────────────────────────────

export interface AuthUser {
  id: string;
  email: string;
  role: "FARMER" | "AGRONOMIST" | "ADMIN";
  created_at: string | null;
}

export interface AuthResponse {
  access_token: string;
  token_type: "bearer";
  expires_at: string;
  expires_in_s: number;
  user: AuthUser;
  role_note?: string;
}

export interface MeResponse {
  user: AuthUser;
  session: { expires_at: string; issuer: string; revocation: string };
}

export interface FeedbackCreate {
  correctness: "YES" | "NO" | "NOT_SURE";
  actual_condition?: string | null;
  notes?: string | null;
  image_quality?: "GOOD" | "BLURRY" | "BAD_LIGHTING" | "NOT_A_LEAF" | null;
}

export interface FeedbackItem {
  id: string;
  analysis_id: string;
  user_id: string | null;
  correctness: "YES" | "NO" | "NOT_SURE";
  actual_condition: string | null;
  notes: string | null;
  image_quality: string | null;
  created_at: string | null;
  user_email?: string | null; // reviewer surface only (admin/agronomist)
}

export interface FeedbackList {
  count: number;
  feedback: FeedbackItem[];
}

export interface FeedbackAdminList extends FeedbackList {
  total: number;
  by_correctness: Record<string, number>;
  note: string;
}

export interface AdminUserRow extends AuthUser {
  farm_count: number;
  bootstrap_note: string | null;
}

export interface AdminUserList {
  count: number;
  users: AdminUserRow[];
}

export interface AuditLogRow {
  id: string;
  action: string;
  entity: string;
  entity_id: string | null;
  user_id: string | null;
  ip: string | null;
  request_id: string | null;
  created_at: string | null;
}

export interface AuditLogList {
  count: number;
  audit_logs: AuditLogRow[];
}

export interface OverviewStats {
  users: number;
  farms: number;
  fields: number;
  images: number;
  analyses: number;
  analyses_by_status: Record<string, number>;
  predictions_by_status: Record<string, number>;
  zones_by_review_status: Record<string, number>;
  reports: number;
  feedback: number;
  simulation_runs: number;
  model_versions: number;
  dataset_sources: number;
  revoked_tokens: number;
}
