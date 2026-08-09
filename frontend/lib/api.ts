/**
 * Typed API client (browser-side only — every call happens in the user's browser
 * against NEXT_PUBLIC_API_URL, never at SSR/build time inside a container).
 */

import type {
  AnalysisCreateResponse,
  AnalysisList,
  AnalysisStatus,
  Farm,
  FarmDetail,
  FarmList,
  FieldRecord,
  ImageUploadResponse,
  ModelInfo,
  Prediction,
  PredictionList,
  SupportedCrops,
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
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      cache: "no-store",
      ...init,
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
  body: { name?: string; crop_id?: string; area_ha?: number },
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
