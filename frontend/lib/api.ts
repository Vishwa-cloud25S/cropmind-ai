/**
 * Typed API client (browser-side only — every call happens in the user's browser
 * against NEXT_PUBLIC_API_URL, never at SSR/build time inside a container).
 */

import { getToken, handleUnauthorized, isSessionAlive } from "@/lib/auth";
import type {
  AdminUserList,
  AnalysisCreateResponse,
  AnalysisList,
  AnalysisReportView,
  AnalysisStatus,
  AuditLogList,
  AuthUser,
  AuthResponse,
  Farm,
  FarmDetail,
  FarmList,
  FeedbackCreate,
  FeedbackAdminList,
  FeedbackItem,
  FeedbackList,
  FieldMapData,
  FieldRecord,
  ImageUploadResponse,
  InterventionZone,
  MeResponse,
  ModelInfo,
  OverviewStats,
  Prediction,
  PredictionList,
  ReportList,
  ReportPayload,
  SimulationList,
  SimulationRunDetail,
  SupportedCrops,
  ZoneGenerateResponse,
  ZoneList,
} from "@/lib/types";

export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/** Client-visible API failure. `detail` is the backend's honesty payload verbatim. */
export class ApiError extends Error {
  status: number;
  detail: unknown;

  constructor(status: number, detail: unknown) {
    super(typeof detail === "string" ? detail : `API error ${status}`);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  // Session token rides on every call when present (Phase 10); the API is the
  // real enforcement boundary — this header only saves a round-trip.
  const token = getToken();
  const headers: Record<string, string> = {
    ...(init?.headers as Record<string, string> | undefined),
    ...(token && isSessionAlive() ? { Authorization: `Bearer ${token}` } : {}),
  };
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      cache: "no-store",
      ...init,
      headers,
    });
  } catch (cause) {
    // Network-level failure (API down / unreachable): never invent a status.
    throw new ApiError(0, {
      detail: "cannot reach the CropMind API — is the backend running?",
      base: API_BASE,
      cause: cause instanceof Error ? cause.message : String(cause),
    });
  }
  if (!response.ok) {
    let detail: unknown = response.statusText;
    try {
      const body = await response.json();
      detail = body?.detail ?? body;
    } catch {
      /* non-JSON error body — keep statusText */
    }
    // A dead session anywhere ⇒ clear + route to /login with a return path.
    // /auth/* 401s (wrong password etc.) are form errors, not session death.
    if (response.status === 401 && !path.startsWith("/auth/")) {
      handleUnauthorized();
    }
    throw new ApiError(response.status, detail);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

function qs(params: Record<string, string | number | boolean | undefined>): string {
  const entries = Object.entries(params).filter(([, v]) => v !== undefined);
  return entries.length
    ? "?" + entries.map(([k, v]) => `${k}=${encodeURIComponent(String(v))}`).join("&")
    : "";
}

// ── images + analyses ─────────────────────────────────────────────────────────

export function uploadImage(
  file: File,
  opts: { fieldId?: string; demo?: boolean } = {},
): Promise<ImageUploadResponse> {
  const form = new FormData();
  form.append("file", file);
  return request<ImageUploadResponse>(`/images${qs({ field_id: opts.fieldId, demo: opts.demo })}`, {
    method: "POST",
    body: form,
  });
}

export function createAnalysis(
  imageId: string,
  opts: { fieldId?: string; demo?: boolean } = {},
): Promise<AnalysisCreateResponse> {
  return request<AnalysisCreateResponse>("/analyses", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ image_id: imageId, field_id: opts.fieldId ?? null, demo: opts.demo ?? false }),
  });
}

export function getAnalysis(analysisId: string): Promise<AnalysisStatus> {
  return request<AnalysisStatus>(`/analyses/${analysisId}`);
}

export function listAnalyses(
  opts: { limit?: number; offset?: number; status?: string } = {},
): Promise<AnalysisList> {
  return request<AnalysisList>(`/analyses${qs({ limit: opts.limit, offset: opts.offset, status: opts.status })}`);
}

export function getPredictionForAnalysis(analysisId: string): Promise<Prediction> {
  return request<Prediction>(`/analyses/${analysisId}/prediction`);
}

export function listPredictions(limit = 5): Promise<PredictionList> {
  return request<PredictionList>(`/predictions${qs({ limit })}`);
}

export const imageDownloadUrl = (imageId: string, thumb = false) =>
  `${API_BASE}/images/${imageId}/download${thumb ? "?thumb=true" : ""}`;

export const gradcamUrl = (analysisId: string) => `${API_BASE}/analyses/${analysisId}/gradcam`;

// ── farms & fields ────────────────────────────────────────────────────────────

export function listFarms(): Promise<FarmList> {
  return request<FarmList>("/farms");
}

export function createFarm(body: { name: string; location?: string }): Promise<{ farm: Farm }> {
  return request<{ farm: Farm }>("/farms", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function getFarm(farmId: string): Promise<FarmDetail> {
  return request<FarmDetail>(`/farms/${farmId}`);
}

export function updateFarm(farmId: string, body: { name?: string; location?: string }): Promise<{ farm: Farm }> {
  return request<{ farm: Farm }>(`/farms/${farmId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function deleteFarm(farmId: string): Promise<void> {
  return request<void>(`/farms/${farmId}`, { method: "DELETE" });
}

export function createField(
  farmId: string,
  body: { name: string; crop_id?: string; area_ha?: number },
): Promise<{ field: FieldRecord }> {
  return request<{ field: FieldRecord }>(`/farms/${farmId}/fields`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function updateField(
  fieldId: string,
  body: {
    name?: string;
    crop_id?: string;
    area_ha?: number;
    boundary_geojson?: { type: "Polygon"; coordinates: number[][][] };
  },
): Promise<{ field: FieldRecord }> {
  return request<{ field: FieldRecord }>(`/fields/${fieldId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function deleteField(fieldId: string): Promise<void> {
  return request<void>(`/fields/${fieldId}`, { method: "DELETE" });
}

// ── intervention zones + map (Phase 7) ────────────────────────────────────────

export function generateZones(analysisId: string): Promise<ZoneGenerateResponse> {
  return request<ZoneGenerateResponse>(`/analyses/${analysisId}/intervention-zones`, { method: "POST" });
}

export function listZones(
  opts: { fieldId?: string; reviewStatus?: string; limit?: number; offset?: number } = {},
): Promise<ZoneList> {
  return request<ZoneList>(
    `/intervention-zones${qs({ field_id: opts.fieldId, review_status: opts.reviewStatus, limit: opts.limit, offset: opts.offset })}`,
  );
}

export function reviewZone(
  zoneId: string,
  body: { review_status: "APPROVED" | "REJECTED"; review_note?: string },
): Promise<{ zone: InterventionZone }> {
  return request<{ zone: InterventionZone }>(`/intervention-zones/${zoneId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export const zoneExportUrl = (opts: { fieldId?: string; format: "geojson" | "csv" }) =>
  `${API_BASE}/intervention-zones/export${qs({ field_id: opts.fieldId, format: opts.format })}`;

export function getFieldMapData(fieldId: string): Promise<FieldMapData> {
  return request<FieldMapData>(`/fields/${fieldId}/map-data`);
}

// ── simulation (Phase 8) ──────────────────────────────────────────────────────

export function runSprayPlan(body: {
  field_id: string;
  treatment_polygons: { type: "Polygon"; coordinates: number[][][] }[];
  spray_width_m: number;
  speed_mps: number;
  declared_rate_l_per_ha: number;
  turn_overhead_s: number;
}): Promise<{ simulation: SimulationRunDetail }> {
  return request<{ simulation: SimulationRunDetail }>("/simulations/spray-plan", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function listSimulations(opts: { fieldId?: string; limit?: number } = {}): Promise<SimulationList> {
  return request<SimulationList>(`/simulations${qs({ field_id: opts.fieldId, limit: opts.limit ?? 20 })}`);
}

export function getSimulation(simulationId: string): Promise<{ simulation: SimulationRunDetail }> {
  return request<{ simulation: SimulationRunDetail }>(`/simulations/${simulationId}`);
}

export const simulationRouteUrl = (simulationId: string) =>
  `${API_BASE}/simulations/${simulationId}/route.geojson`;

// ── model truth ───────────────────────────────────────────────────────────────

export function getModelInfo(): Promise<ModelInfo> {
  return request<ModelInfo>("/model-info");
}

export function getSupportedCrops(): Promise<SupportedCrops> {
  return request<SupportedCrops>("/supported-crops");
}

export function getReadiness(): Promise<{ status: string; database: string }> {
  return request<{ status: string; database: string }>("/health/ready");
}

// ── Phase 10: auth, feedback, admin ───────────────────────────────────────────

export function registerAccount(email: string, password: string): Promise<AuthResponse> {
  return request<AuthResponse>("/auth/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
}

export function loginAccount(email: string, password: string): Promise<AuthResponse> {
  return request<AuthResponse>("/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
}

/** Best-effort server-side revocation; the caller clears local state regardless. */
export function logoutAccount(): Promise<{ detail: string }> {
  return request<{ detail: string }>("/auth/logout", { method: "POST" });
}

export function getMe(): Promise<MeResponse> {
  return request<MeResponse>("/auth/me");
}

export function submitFeedback(analysisId: string, body: FeedbackCreate): Promise<{ feedback: FeedbackItem; note: string }> {
  return request<{ feedback: FeedbackItem; note: string }>(`/analyses/${analysisId}/feedback`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function listFeedback(analysisId: string): Promise<FeedbackList> {
  return request<FeedbackList>(`/analyses/${analysisId}/feedback`);
}

export function adminListUsers(): Promise<AdminUserList> {
  return request<AdminUserList>("/admin/users");
}

export function adminChangeRole(userId: string, role: "FARMER" | "AGRONOMIST" | "ADMIN"): Promise<{ user: AuthUser; role_transition: string }> {
  return request<{ user: AuthUser; role_transition: string }>(`/admin/users/${userId}/role`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ role }),
  });
}

export function adminListFeedback(limit = 50): Promise<FeedbackAdminList> {
  return request<FeedbackAdminList>(`/admin/feedback${qs({ limit })}`);
}

export function adminListAuditLogs(limit = 100): Promise<AuditLogList> {
  return request<AuditLogList>(`/admin/audit-logs${qs({ limit })}`);
}

export function adminOverview(): Promise<{ overview: OverviewStats; note: string }> {
  return request<{ overview: OverviewStats; note: string }>("/admin/overview");
}

// ── Phase 9: PDF field reports ────────────────────────────────────────────────

/** Report state for the analysis view — 200 always for a known analysis (READY | GENERATE + why). */
export function getAnalysisReportView(analysisId: string): Promise<AnalysisReportView> {
  return request<AnalysisReportView>(`/analyses/${analysisId}/report`);
}

/** Explicit generation/regeneration (201). 409 detail carries the verbatim honesty reason. */
export function generateReport(analysisId: string): Promise<{ report: ReportPayload; note: string }> {
  return request<{ report: ReportPayload; note: string }>(`/analyses/${analysisId}/report`, {
    method: "POST",
  });
}

export function listReports(opts: { limit?: number; offset?: number } = {}): Promise<ReportList> {
  return request<ReportList>(`/reports${qs({ limit: opts.limit, offset: opts.offset })}`);
}

export function getReport(reportId: string): Promise<{ report: ReportPayload }> {
  return request<{ report: ReportPayload }>(`/reports/${reportId}`);
}

/** Direct PDF artifact URL (browser navigates/downloads; filename carries the human report ID). */
export const reportDownloadUrl = (reportId: string) => `${API_BASE}/reports/${reportId}/download`;

/** Extracts the most useful human-facing line from an ApiError for display. */
export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (typeof error.detail === "string") return error.detail;
    if (error.detail && typeof error.detail === "object" && "detail" in (error.detail as Record<string, unknown>)) {
      const inner = (error.detail as Record<string, unknown>).detail;
      if (typeof inner === "string") return inner;
    }
    if (Array.isArray(error.detail)) return "Invalid input — please review the highlighted fields.";
    return `Request failed (HTTP ${error.status || "network"})`;
  }
  return error instanceof Error ? error.message : "Unexpected error";
}
