"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";

import {
  ApiError,
  createAnalysis,
  errorMessage,
  getFarm,
  imageDownloadUrl,
  listFarms,
  uploadImage,
} from "@/lib/api";
import { getAnalysis } from "@/lib/api";
import type { AnalysisState, AnalysisStatus, Farm, FieldRecord, ImageRecord } from "@/lib/types";
import { AnalysisStatusChip } from "@/components/StatusBadge";

const MAX_BYTES = 25 * 1024 * 1024; // mirrors the backend default; server still enforces its own
const ACCEPT_ATTR = "image/jpeg,image/png,image/webp,image/tiff";

type Step = "choose" | "uploaded" | "running" | "complete" | "failed";

interface UploadOk {
  image: ImageRecord;
  deduplicated: boolean;
}

/** For testability, the network layer is injected; production passes the real client. */
export interface WizardDeps {
  uploadImageFn?: typeof uploadImage;
  createAnalysisFn?: typeof createAnalysis;
  getAnalysisFn?: typeof getAnalysis;
  listFarmsFn?: typeof listFarms;
  getFarmFn?: typeof getFarm;
  pollMs?: number;
}

export default function AnalyzeWizard(props: WizardDeps) {
  const uploadImageFn = props.uploadImageFn ?? uploadImage;
  const createAnalysisFn = props.createAnalysisFn ?? createAnalysis;
  const getAnalysisFn = props.getAnalysisFn ?? getAnalysis;
  const listFarmsFn = props.listFarmsFn ?? listFarms;
  const getFarmFn = props.getFarmFn ?? getFarm;
  const pollMs = props.pollMs ?? 2000;

  const [step, setStep] = useState<Step>("choose");
  const [file, setFile] = useState<File | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const [serverError, setServerError] = useState<string | null>(null);
  const [upload, setUpload] = useState<UploadOk | null>(null);
  const [analysis, setAnalysis] = useState<AnalysisStatus | null>(null);
  const [busy, setBusy] = useState(false);

  const [farms, setFarms] = useState<Farm[] | null>(null);
  const [farmId, setFarmId] = useState<string>("");
  const [fields, setFields] = useState<FieldRecord[]>([]);
  const [fieldId, setFieldId] = useState<string>("");

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const stopPolling = useCallback(() => {
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = null;
  }, []);

  useEffect(() => stopPolling, [stopPolling]);

  // Farms for the optional field picker (progressive disclosure, never fabricated).
  useEffect(() => {
    let cancelled = false;
    listFarmsFn()
      .then((list) => {
        if (!cancelled) setFarms(list.farms);
      })
      .catch(() => {
        if (!cancelled) setFarms([]); // farms optional — upload works without
      });
    return () => {
      cancelled = true;
    };
  }, [listFarmsFn]);

  useEffect(() => {
    if (!farmId) {
      setFields([]);
      setFieldId("");
      return;
    }
    let cancelled = false;
    getFarmFn(farmId)
      .then((detail) => {
        if (!cancelled) setFields(detail.fields);
      })
      .catch(() => {
        if (!cancelled) setFields([]);
      });
    return () => {
      cancelled = true;
    };
  }, [farmId, getFarmFn]);

  function pickFile(candidate: File | null) {
    setServerError(null);
    setFileError(null);
    if (!candidate) {
      setFile(null);
      return;
    }
    if (candidate.size > MAX_BYTES) {
      setFile(null);
      setFileError(
        `That file is ${(candidate.size / 1024 / 1024).toFixed(1)} MB — the limit is 25 MB. The server verifies content by magic bytes, so renaming it will not change the result.`,
      );
      return;
    }
    setFile(candidate);
  }

  async function doUpload() {
    if (!file) return;
    setBusy(true);
    setServerError(null);
    try {
      const response = await uploadImageFn(file, { fieldId: fieldId || undefined });
      setUpload({ image: { ...response.image }, deduplicated: response.image.deduplicated });
      setStep("uploaded");
    } catch (err) {
      setServerError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  const poll = useCallback(
    async (analysisId: string) => {
      try {
        const status = await getAnalysisFn(analysisId);
        setAnalysis(status);
        if (status.status === "COMPLETED") {
          stopPolling();
          setStep("complete");
        } else if (status.status === "FAILED") {
          stopPolling();
          setServerError(status.error ?? "analysis failed without a recorded error");
          setStep("failed");
        }
      } catch (err) {
        if (err instanceof ApiError && err.status === 404) return; // transient race: row not visible yet
        stopPolling();
        setServerError(errorMessage(err));
        setStep("failed");
      }
    },
    [getAnalysisFn, stopPolling],
  );

  async function runAnalysis() {
    if (!upload) return;
    setBusy(true);
    setServerError(null);
    try {
      const response = await createAnalysisFn(upload.image.id, { fieldId: upload.image.field_id ?? (fieldId || undefined) });
      setAnalysis({
        analysis_id: response.analysis_id,
        image_id: upload.image.id,
        status: "QUEUED",
        demo: false,
        created_at: null,
        started_at: null,
        completed_at: null,
        error: null,
      });
      setStep("running");
      stopPolling();
      void poll(response.analysis_id);
      pollRef.current = setInterval(() => void poll(response.analysis_id), pollMs);
    } catch (err) {
      setServerError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  function reset() {
    stopPolling();
    setStep("choose");
    setFile(null);
    setFileError(null);
    setServerError(null);
    setUpload(null);
    setAnalysis(null);
    setBusy(false);
  }

  const running = step === "running";
  const statusText: Record<AnalysisState | "idle", string> = {
    idle: "Waiting",
    QUEUED: "Queued — the worker picks this up in a few seconds",
    PROCESSING: "Processing — the model is running on your image",
    COMPLETED: "Completed",
    FAILED: "Failed",
  };

  return (
    <div className="card space-y-5" data-testid="analyze-wizard">
      <div>
        <p className="eyebrow">Step 1 of 3</p>
        <h2 className="text-lg font-bold text-stone-900">Choose a photo</h2>
        <p className="mt-1 text-sm leading-6 text-stone-600">
          One affected leaf, close-up, in good light works best. JPEG, PNG, WebP or TIFF, up to 25 MB —
          the server identifies content by its <em>bytes</em>, so renamed files are caught honestly.
        </p>
        <div className="mt-3">
          <label htmlFor="image-file" className="field-label">Image file</label>
          <input
            id="image-file"
            name="image-file"
            type="file"
            accept={ACCEPT_ATTR}
            className="input file:mr-4 file:rounded-md file:border-0 file:bg-emerald-50 file:px-3 file:py-1.5 file:text-sm file:font-semibold file:text-emerald-800"
            onChange={(event) => pickFile(event.target.files?.[0] ?? null)}
            disabled={busy || running}
          />
          {fileError ? <p className="alert-error mt-2" role="alert">{fileError}</p> : null}
          {file ? (
            <p className="mt-2 text-xs text-stone-500">
              Selected: {file.name} · {(file.size / 1024).toFixed(0)} KB
            </p>
          ) : null}
        </div>
        {farms !== null && farms.length > 0 ? (
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            <div>
              <label htmlFor="farm-select" className="field-label">Farm (optional)</label>
              <select id="farm-select" className="input" value={farmId} onChange={(e) => setFarmId(e.target.value)} disabled={busy || running}>
                <option value="">no farm</option>
                {farms.map((farm) => (
                  <option key={farm.id} value={farm.id}>{farm.name}</option>
                ))}
              </select>
            </div>
            <div>
              <label htmlFor="field-select" className="field-label">Field (optional)</label>
              <select
                id="field-select"
                className="input"
                value={fieldId}
                onChange={(e) => setFieldId(e.target.value)}
                disabled={busy || running || !farmId}
              >
                <option value="">{farmId ? "whole farm / no field" : "pick a farm first"}</option>
                {fields.map((field) => (
                  <option key={field.id} value={field.id}>
                    {field.name}{field.crop_id ? ` (${field.crop_id})` : ""}
                  </option>
                ))}
              </select>
            </div>
          </div>
        ) : null}
        <div className="mt-4 flex gap-3">
          <button type="button" className="btn-primary" onClick={doUpload} disabled={!file || busy || running || step !== "choose"}>
            {busy && step === "choose" ? "Uploading…" : "Upload"}
          </button>
          {step !== "choose" ? (
            <button type="button" className="btn-ghost" onClick={reset}>Start over</button>
          ) : null}
        </div>
      </div>

      {upload ? (
        <div className="rounded-lg border border-stone-200 p-4">
          <p className="eyebrow">Step 2 of 3</p>
          <h2 className="text-lg font-bold text-stone-900">Stored copy</h2>
          {upload.deduplicated ? (
            <p className="alert-info mt-2" role="note">
              Identical content was already uploaded before — we reused the existing record (no duplicate stored).
            </p>
          ) : null}
          <div className="mt-3 flex flex-wrap items-center gap-4">
            {/* Server-side re-encode thumbnail; EXIF orientation normalized at upload */}
            {/* eslint-disable-next-line @next/next/no-img-element -- dynamic API image URL */}
            <img
              src={imageDownloadUrl(upload.image.id, true)}
              alt="Thumbnail of the stored upload"
              className="h-20 w-20 rounded-lg border border-stone-200 object-cover"
              width={80}
              height={80}
            />
            <dl className="text-sm text-stone-700">
              <dt className="field-label inline">Dimensions</dt>{" "}
              <dd className="inline">{upload.image.width} × {upload.image.height}</dd>
              <span aria-hidden="true"> · </span>
              <dt className="field-label inline">Bytes stored</dt>{" "}
              <dd className="inline">{upload.image.byte_size.toLocaleString()}</dd>
            </dl>
          </div>
          <div className="mt-4 flex gap-3">
            <button type="button" className="btn-primary" onClick={runAnalysis} disabled={busy || running || step !== "uploaded"}>
              {busy && step === "uploaded" ? "Starting…" : "Run analysis"}
            </button>
          </div>
        </div>
      ) : null}

      {analysis ? (
        <div aria-live="polite" role="status" className="rounded-lg border border-stone-200 p-4">
          <p className="eyebrow">Step 3 of 3</p>
          <h2 className="text-lg font-bold text-stone-900">Analysis status</h2>
          <div className="mt-2 flex items-center gap-3">
            <AnalysisStatusChip status={analysis.status} demo={analysis.demo} />
            <span className="text-sm text-stone-600">{statusText[analysis.status] ?? analysis.status}</span>
            {analysis.job ? (
              <span className="text-xs text-stone-500">
                attempt {analysis.job.attempts} of {analysis.job.max_attempts}
              </span>
            ) : null}
          </div>
          {step === "complete" ? (
            <div className="alert-info mt-3" role="note">
              Ready.{" "}
              <Link href={`/analyses/${analysis.analysis_id}`} className="link-cta">
                View the full analysis → phrasing, confidence band, Grad-CAM and model identity
              </Link>
            </div>
          ) : null}
        </div>
      ) : null}

      {serverError ? (
        <p className="alert-error" role="alert">
          {serverError}
          {step === "failed" && upload ? (
            <>
              {" "}
              <button type="button" className="font-semibold underline" onClick={runAnalysis}>
                Try again
              </button>
            </>
          ) : null}
        </p>
      ) : null}
    </div>
  );
}
