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
import { isSessionAlive } from "@/lib/auth";
import { DEMO_SAMPLES, sampleAssetPath } from "@/lib/demo-samples";
import type { DemoSample } from "@/lib/demo-samples";
import type { AnalysisState, AnalysisStatus, Farm, FieldRecord, ImageRecord } from "@/lib/types";
import { AnalysisStatusChip } from "@/components/StatusBadge";
import AuthedImage from "@/components/AuthedImage";

const MAX_BYTES = 25 * 1024 * 1024; // mirrors the backend default; server still enforces its own
const ACCEPT_ATTR = "image/jpeg,image/png,image/webp,image/tiff";

/** Re-encode a bundled sample JPEG in-browser (fresh bytes, same photo). Used ONLY to
 * satisfy the deployment's global content-dedupe (HTTP 409) for FR-20 sample picks:
 * every visitor receives byte-identical static assets, so after the first upload the
 * dedupe honestly refuses repeats. A retake mirrors re-taking the photo. User's own
 * photos are NEVER re-encoded — this fires only when the file came from the bundle. */
async function reencodeJpeg(source: File): Promise<File> {
  const bitmap = await createImageBitmap(source);
  const canvas = document.createElement("canvas");
  canvas.width = bitmap.width;
  canvas.height = bitmap.height;
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("in-browser re-encode unavailable");
  ctx.drawImage(bitmap, 0, 0);
  bitmap.close();
  // Slight per-attempt freshness: identical browsers would otherwise re-encode to the
  // exact same bytes as another visitor's retake and collide with cross-account dedupe
  // (409, honestly surfaced). A ms-jittered quality keeps each retake genuinely unique
  // bytes — the JPEG-equivalent of retaking the photo.
  const quality = 0.93 - (Date.now() % 7) * 0.003;
  const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/jpeg", quality));
  if (!blob) throw new Error("in-browser re-encode failed");
  const stem = source.name.replace(/\.jpe?g$/i, "");
  return new File([blob], `${stem}-retake.jpg`, { type: "image/jpeg" });
}

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
  const [retakeNotice, setRetakeNotice] = useState<string | null>(null);
  const retakeTriedRef = useRef(false); // dedupe-409 ⇒ exactly one bundled-sample retake attempt
  // Phase 15 (FR-20): bundled, individually-labelled sample photos for visitors
  // who have no photo at hand — provenance + honesty note travel with the pick.
  const [selectedSampleId, setSelectedSampleId] = useState<string>("");
  const [sampleBusy, setSampleBusy] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);
  const [upload, setUpload] = useState<UploadOk | null>(null);
  const [analysis, setAnalysis] = useState<AnalysisStatus | null>(null);
  const [signedIn, setSignedIn] = useState(true); // assumed true until mount-probed (avoids SSR/CSR mismatch)
  const [busy, setBusy] = useState(false);
  const [warmingNotice, setWarmingNotice] = useState<string | null>(null); // transient wake-up, NOT a failure
  const transientPollMisses = useRef(0);

  const [farms, setFarms] = useState<Farm[] | null>(null);
  const [farmId, setFarmId] = useState<string>("");
  const [fields, setFields] = useState<FieldRecord[]>([]);
  const [fieldId, setFieldId] = useState<string>("");

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const stoppedRef = useRef(false); // latched: in-flight responses may never overwrite a terminal state
  // Serial polls only: if the previous request is still in flight (a waking host can
  // hold a connection for tens of seconds), skip the tick instead of stacking
  // overlapping requests that race each other — a later success could otherwise
  // clear the honest wake-up notice while an earlier result is still landing.
  const pollInFlightRef = useRef<string | null>(null);
  // The analysis currently allowed to write state; responses from a superseded run
  // (e.g. a retry started while an old poll was still out) are dropped, never applied.
  const pollingForRef = useRef<string | null>(null);
  const stopPolling = useCallback(() => {
    stoppedRef.current = true;
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = null;
  }, []);

  useEffect(() => stopPolling, [stopPolling]);

  // Farms for the optional field picker (progressive disclosure, never fabricated).
  useEffect(() => {
    setSignedIn(isSessionAlive()); // client-only session probe
  }, []);

  // FR-20 honesty: anonymous demo visitors have no account — fetching /farms would
  // 401 and the shared wrapper redirects that to /login, killing the no-account flow.
  // Skip the picker when no session exists; the upload still works (flagged demo).
  useEffect(() => {
    let cancelled = false;
    if (!isSessionAlive()) {
      setFarms(null);
      return () => {
        cancelled = true;
      };
    }
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
    setRetakeNotice(null);
    retakeTriedRef.current = false; // a fresh pick re-arms the single dedupe retake
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

  /** Fetch a bundled sample photo and put it through the EXACT same upload path as a
   * hand-picked file — no shortcut plumbing, no special-cased results. */
  async function pickSample(id: string) {
    setSelectedSampleId(id);
    const entry = DEMO_SAMPLES.find((sample) => sample.id === id);
    if (!entry) return;
    setSampleBusy(true);
    setFileError(null);
    try {
      const response = await fetch(sampleAssetPath(entry));
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const blob = await response.blob();
      pickFile(new File([blob], entry.file, { type: blob.type || "image/jpeg" }));
    } catch (err) {
      setSelectedSampleId("");
      setFileError(
        `Could not load the bundled sample (${err instanceof Error ? err.message : "network error"}) — pick your own file instead; the wizard works the same either way.`,
      );
    } finally {
      setSampleBusy(false);
    }
  }

  const selectedSample: DemoSample | null = DEMO_SAMPLES.find((sample) => sample.id === selectedSampleId) ?? null;

  async function doUpload() {
    if (!file) return;
    setBusy(true);
    setServerError(null);
    setRetakeNotice(null);
    // Phase 10 honesty: without a session the only path is the flagged demo one.
    const demo = !isSessionAlive(); // handler-time probe (client-only) — always accurate
    try {
      const response = await uploadImageFn(file, { fieldId: fieldId || undefined, demo });
      setUpload({ image: { ...response.image }, deduplicated: response.image.deduplicated });
      setStep("uploaded");
    } catch (err) {
      // FR-20 unblock: the bundled samples are byte-identical for every visitor, so
      // after the first-ever upload the global content-dedupe honestly 409s. For a
      // bundled pick ONLY (never a user's own photo) retry once with a fresh
      // in-browser re-encoded retake — and say so on screen.
      const isDedupe = err instanceof ApiError && err.status === 409;
      if (isDedupe && selectedSampleId && !retakeTriedRef.current) {
        retakeTriedRef.current = true;
        try {
          const fresh = await reencodeJpeg(file);
          const response = await uploadImageFn(fresh, { fieldId: fieldId || undefined, demo });
          setRetakeNotice(
            "The sample's exact bytes were already stored on this deployment (global " +
              "content-dedupe doing its job), so a fresh re-encoded retake of the same " +
              "labelled photo was uploaded. Your own photos are never re-encoded.",
          );
          setUpload({ image: { ...response.image }, deduplicated: response.image.deduplicated });
          setStep("uploaded");
        } catch (err2) {
          setServerError(errorMessage(err2));
        }
      } else {
        setServerError(errorMessage(err));
      }
    } finally {
      setBusy(false);
    }
  }

  const poll = useCallback(
    async (analysisId: string) => {
      if (stoppedRef.current || pollInFlightRef.current !== null) return; // serial: skip the tick, never stack overlapping polls
      pollInFlightRef.current = analysisId;
      try {
        const status = await getAnalysisFn(analysisId);
        if (stoppedRef.current || pollingForRef.current !== analysisId) return; // late response: terminal latched or run superseded
        transientPollMisses.current = 0;
        setWarmingNotice(null);
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
        // Network/edge-restart blips are NOT analysis failures: the row lives on the
        // server and the poll must keep going. Only repeated failures give up, and
        // they say so honestly instead of mislabelling the analysis as FAILED.
        const transient = err instanceof ApiError && (err.status === 0 || err.status >= 500);
        if (transient && transientPollMisses.current < 6) {
          transientPollMisses.current += 1;
          setWarmingNotice(
            "the demo API is waking up or restarting — still holding your analysis; retrying automatically",
          );
          return;
        }
        stopPolling();
        setServerError(errorMessage(err));
        setStep("failed");
      } finally {
        // Release the serial slot only if a fresh run has not already taken it over —
        // a superseded run's late landing must not open the gate mid-flight.
        if (pollInFlightRef.current === analysisId) pollInFlightRef.current = null;
      }
    },
    [getAnalysisFn, stopPolling],
  );

  async function runAnalysis() {
    if (!upload) return;
    setBusy(true);
    setServerError(null);
    try {
      const demo = !isSessionAlive(); // handler-time probe (client-only) — always accurate
      const response = await createAnalysisFn(upload.image.id, {
        fieldId: upload.image.field_id ?? (fieldId || undefined),
        demo,
      });
      setAnalysis({
        analysis_id: response.analysis_id,
        image_id: upload.image.id,
        status: "QUEUED",
        demo,
        created_at: null,
        started_at: null,
        completed_at: null,
        error: null,
      });
      setStep("running");
      stopPolling();
      stoppedRef.current = false; // a fresh run re-arms the latch stopPolling just set
      transientPollMisses.current = 0;
      pollingForRef.current = response.analysis_id; // only this run may write polling state now
      pollInFlightRef.current = null; // hand the serial-poll slot to the fresh run
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
    setSelectedSampleId("");
    setServerError(null);
    setWarmingNotice(null);
    setRetakeNotice(null);
    retakeTriedRef.current = false;
    transientPollMisses.current = 0;
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
            onChange={(event) => {
              setSelectedSampleId("");
              pickFile(event.target.files?.[0] ?? null);
            }}
            disabled={busy || running}
          />
          {fileError ? <p className="alert-error mt-2" role="alert">{fileError}</p> : null}
          {file ? (
            <p className="mt-2 text-xs text-stone-500">
              Selected: {file.name} · {(file.size / 1024).toFixed(0)} KB
            </p>
          ) : null}
        </div>
        <div className="mt-3">
          <label htmlFor="sample-select" className="field-label">
            No photo at hand? Use a bundled sample (labelled with provenance)
          </label>
          <select
            id="sample-select"
            className="input"
            value={selectedSampleId}
            onChange={(event) => void pickSample(event.target.value)}
            disabled={busy || running || sampleBusy}
            data-testid="sample-select"
          >
            <option value="">choose a sample photo…</option>
            {DEMO_SAMPLES.map((sample) => (
              <option key={sample.id} value={sample.id}>
                {sample.label}
              </option>
            ))}
          </select>
          {sampleBusy ? <p className="mt-1 text-xs text-stone-500">loading the sample photo…</p> : null}
          {selectedSample ? (
            <p className="mt-1 text-xs leading-5 text-stone-500" data-testid="sample-provenance">
              {selectedSample.provenance}. {selectedSample.honestyNote}
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
        {!signedIn ? (
          <p className="alert-info mt-4" role="note">
            No account signed in — this run uses the <strong>flagged demo path</strong> (results labelled demo;
            the live model identity is always shown on the landing page&apos;s Model truth panel).{" "}
            <Link href="/login?next=/analyze" className="link-cta">
              Sign in
            </Link>{" "}
            for a private workspace with farm/field linking.
          </p>
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
          {retakeNotice ? (
            <p className="alert-caution mt-2" role="note" data-testid="retake-notice">
              {retakeNotice}
            </p>
          ) : null}
          {upload.deduplicated ? (
            <p className="alert-info mt-2" role="note">
              Identical content was already uploaded before — we reused the existing record (no duplicate stored).
            </p>
          ) : null}
          <div className="mt-3 flex flex-wrap items-center gap-4">
            {/* Server-side re-encode thumbnail; EXIF orientation normalized at upload.
                 Owner-scoped route — bytes must come through the authenticated fetch. */}
            <AuthedImage
              url={imageDownloadUrl(upload.image.id, true)}
              alt="Thumbnail of the stored upload"
              className="h-20 w-20 rounded-lg border border-stone-200 object-cover"
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
          {warmingNotice ? (
            <p className="alert-caution mt-2" role="note">
              {warmingNotice}
            </p>
          ) : null}
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
