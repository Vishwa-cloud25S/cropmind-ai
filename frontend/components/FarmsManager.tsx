"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";

import { ApiError, createFarm, createField, deleteFarm, deleteField, errorMessage, getFarm, getSupportedCrops, listFarms, updateFarm, updateField } from "@/lib/api";
import type { Farm, FarmDetail, FieldRecord } from "@/lib/types";

/** DI seams so component tests can run without the network. */
export interface FarmsDeps {
  listFarmsFn?: typeof listFarms;
  createFarmFn?: typeof createFarm;
  deleteFarmFn?: typeof deleteFarm;
  getFarmFn?: typeof getFarm;
  updateFarmFn?: typeof updateFarm;
  createFieldFn?: typeof createField;
  updateFieldFn?: typeof updateField;
  deleteFieldFn?: typeof deleteField;
  getSupportedCropsFn?: typeof getSupportedCrops;
}

/** 409-conflict bodies carry honest counts ({field_count} / {image_count, zone_count}) — surface them. */
function conflictMessage(err: unknown): string {
  if (err instanceof ApiError && err.status === 409 && err.detail && typeof err.detail === "object") {
    const body = err.detail as Record<string, unknown>;
    const detail = typeof body.detail === "string" ? body.detail : "Delete blocked";
    const counts = Object.entries(body)
      .filter(([key, value]) => key !== "detail" && typeof value === "number")
      .map(([key, value]) => `${key.replaceAll("_", " ")}: ${value}`)
      .join(" · ");
    return counts ? `${detail} (${counts})` : detail;
  }
  return errorMessage(err);
}

/* ── farm list + create + delete ───────────────────────────────────────────── */

export default function FarmsManager(props: FarmsDeps) {
  const listFarmsFn = props.listFarmsFn ?? listFarms;
  const createFarmFn = props.createFarmFn ?? createFarm;
  const deleteFarmFn = props.deleteFarmFn ?? deleteFarm;

  const [farms, setFarms] = useState<Farm[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [name, setName] = useState("");
  const [location, setLocation] = useState("");

  const refresh = useCallback(async () => {
    setError(null);
    try {
      setFarms((await listFarmsFn()).farms);
    } catch (err) {
      setError(errorMessage(err));
    }
  }, [listFarmsFn]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function submitFarm(event: React.FormEvent) {
    event.preventDefault();
    if (!name.trim()) return;
    setBusy(true);
    setError(null);
    try {
      await createFarmFn({ name: name.trim(), location: location.trim() || undefined });
      setName("");
      setLocation("");
      await refresh();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function removeFarm(farm: Farm) {
    setError(null);
    try {
      await deleteFarmFn(farm.id);
      await refresh();
    } catch (err) {
      setError(conflictMessage(err));
    }
  }

  return (
    <div className="space-y-6" data-testid="farms-manager">
      <form className="card" onSubmit={submitFarm} aria-label="Create a farm">
        <h2 className="text-lg font-bold text-stone-900">Create a farm</h2>
        <p className="mt-1 text-sm text-stone-600">
          Pre-authentication milestone: farms are shared on this deployment (owner assignment lands in Phase 10).
        </p>
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          <div>
            <label htmlFor="farm-name" className="field-label">
              Name
            </label>
            <input
              id="farm-name"
              className="input"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              maxLength={120}
              placeholder="e.g. Rectory Farm"
            />
          </div>
          <div>
            <label htmlFor="farm-location" className="field-label">
              Location (optional)
            </label>
            <input
              id="farm-location"
              className="input"
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              maxLength={200}
              placeholder="e.g. Kent, UK"
            />
          </div>
        </div>
        <button type="submit" className="btn-primary mt-4" disabled={busy || !name.trim()}>
          {busy ? "Creating…" : "Create farm"}
        </button>
      </form>

      {error ? (
        <p className="alert-error" role="alert">
          {error}
        </p>
      ) : null}

      <section className="card" aria-label="Your farms">
        <h2 className="text-lg font-bold text-stone-900">Farms on this deployment</h2>
        {farms === null && !error ? <p className="mt-2 text-sm text-stone-500">Loading…</p> : null}
        {farms && farms.length === 0 ? (
          <p className="alert-info mt-3" role="note">
            No farms yet — create one above, then add fields with crops.
          </p>
        ) : null}
        {farms && farms.length > 0 ? (
          <ul className="mt-4 divide-y divide-stone-200">
            {farms.map((farm) => (
              <li key={farm.id} className="flex flex-wrap items-center justify-between gap-3 py-3">
                <div>
                  <Link href={`/farms/${farm.id}`} className="font-semibold text-stone-900 hover:text-emerald-900">
                    {farm.name}
                  </Link>
                  <p className="text-sm text-stone-500">
                    {farm.location ?? "location not set"} · {farm.field_count} field{farm.field_count === 1 ? "" : "s"}
                  </p>
                </div>
                <div className="flex items-center gap-3">
                  <Link href={`/farms/${farm.id}`} className="link-cta">
                    Manage →
                  </Link>
                  <button type="button" className="btn-danger" onClick={() => removeFarm(farm)}>
                    Delete
                  </button>
                </div>
              </li>
            ))}
          </ul>
        ) : null}
      </section>
    </div>
  );
}

/* ── single farm: rename, delete, fields CRUD ──────────────────────────────── */

export function FarmDetailPanel({ farmId, ...props }: FarmsDeps & { farmId: string }) {
  const getFarmFn = props.getFarmFn ?? getFarm;
  const updateFarmFn = props.updateFarmFn ?? updateFarm;
  const deleteFarmFn = props.deleteFarmFn ?? deleteFarm;
  const createFieldFn = props.createFieldFn ?? createField;
  const updateFieldFn = props.updateFieldFn ?? updateField;
  const deleteFieldFn = props.deleteFieldFn ?? deleteField;
  const getSupportedCropsFn = props.getSupportedCropsFn ?? getSupportedCrops;

  const [detail, setDetail] = useState<FarmDetail | null>(null);
  const [crops, setCrops] = useState<{ crop_id: string; name: string }[]>([]);
  const [cropNote, setCropNote] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [missing, setMissing] = useState(false);
  const [busy, setBusy] = useState(false);

  const [renameValue, setRenameValue] = useState("");
  const [fieldName, setFieldName] = useState("");
  const [fieldCrop, setFieldCrop] = useState("");
  const [fieldArea, setFieldArea] = useState("");
  const [editingField, setEditingField] = useState<string | null>(null);
  const [editName, setEditName] = useState("");
  const [editCrop, setEditCrop] = useState("");
  const [editArea, setEditArea] = useState("");

  const refresh = useCallback(async () => {
    setError(null);
    try {
      const farmDetail = await getFarmFn(farmId);
      setDetail(farmDetail);
      setRenameValue((current) => current || farmDetail.farm.name);
      setMissing(false);
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        setMissing(true);
      } else {
        setError(errorMessage(err));
      }
    }
  }, [getFarmFn, farmId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    getSupportedCropsFn()
      .then((truth) =>
        setCrops(truth.crops.map((crop) => ({ crop_id: crop.crop_id, name: crop.name }))),
      )
      .catch(() => setCropNote("Could not load the supported-crop list right now — you can still create a field without a crop."));
  }, [getSupportedCropsFn]);

  function parseArea(raw: string): number | undefined {
    if (!raw.trim()) return undefined;
    const value = Number(raw);
    return Number.isFinite(value) ? value : undefined;
  }

  async function submitRename(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await updateFarmFn(farmId, { name: renameValue.trim() });
      await refresh();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function removeFarm() {
    setError(null);
    try {
      await deleteFarmFn(farmId);
      // With zero fields the delete succeeds; send the user back to the list.
      window.location.assign("/farms");
    } catch (err) {
      setError(conflictMessage(err));
    }
  }

  async function submitField(event: React.FormEvent) {
    event.preventDefault();
    if (!fieldName.trim()) return;
    setBusy(true);
    setError(null);
    try {
      await createFieldFn(farmId, {
        name: fieldName.trim(),
        crop_id: fieldCrop || undefined,
        area_ha: parseArea(fieldArea),
      });
      setFieldName("");
      setFieldCrop("");
      setFieldArea("");
      await refresh();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  function beginEdit(field: FieldRecord) {
    setEditingField(field.id);
    setEditName(field.name);
    setEditCrop(field.crop_id ?? "");
    setEditArea(field.area_ha?.toString() ?? "");
  }

  async function saveField(field: FieldRecord) {
    setBusy(true);
    setError(null);
    try {
      await updateFieldFn(field.id, {
        name: editName.trim(),
        crop_id: editCrop || undefined,
        area_ha: parseArea(editArea),
      });
      setEditingField(null);
      await refresh();
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function removeField(field: FieldRecord) {
    setError(null);
    try {
      await deleteFieldFn(field.id);
      await refresh();
    } catch (err) {
      setError(conflictMessage(err));
    }
  }

  if (missing) {
    return (
      <div className="card" role="alert">
        <p className="font-semibold text-stone-900">Farm not found</p>
        <p className="mt-1 text-sm text-stone-600">
          No farm with this id exists on this deployment.{" "}
          <Link href="/farms" className="link-cta">
            Back to farms
          </Link>
        </p>
      </div>
    );
  }

  if (!detail) {
    return error ? (
      <p className="alert-error" role="alert">
        {error}
      </p>
    ) : (
      <p className="text-sm text-stone-500">Loading farm…</p>
    );
  }

  return (
    <div className="space-y-6" data-testid="farm-detail">
      {error ? (
        <p className="alert-error" role="alert">
          {error}
        </p>
      ) : null}

      <form className="card" onSubmit={submitRename} aria-label="Edit farm">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div className="min-w-60 grow">
            <label htmlFor="rename-farm" className="field-label">
              Farm name
            </label>
            <input
              id="rename-farm"
              className="input"
              value={renameValue}
              onChange={(e) => setRenameValue(e.target.value)}
              required
              maxLength={120}
            />
            <p className="mt-1 text-sm text-stone-500">{detail.farm.location ?? "location not set"}</p>
          </div>
          <div className="flex gap-3">
            <button type="submit" className="btn-secondary" disabled={busy || !renameValue.trim()}>
              Save name
            </button>
            <button type="button" className="btn-danger" onClick={removeFarm}>
              Delete farm
            </button>
          </div>
        </div>
      </form>

      <form className="card" onSubmit={submitField} aria-label="Add a field">
        <h2 className="text-lg font-bold text-stone-900">Add a field</h2>
        <p className="mt-1 text-sm text-stone-600">
          Crops are limited to what the taxonomy actually supports — validated server-side, never free-typed.
        </p>
        {cropNote ? (
          <p className="alert-caution mt-2" role="note">
            {cropNote}
          </p>
        ) : null}
        <div className="mt-4 grid gap-3 sm:grid-cols-3">
          <div>
            <label htmlFor="field-name" className="field-label">
              Field name
            </label>
            <input
              id="field-name"
              className="input"
              value={fieldName}
              onChange={(e) => setFieldName(e.target.value)}
              required
              maxLength={120}
              placeholder="e.g. North paddock"
            />
          </div>
          <div>
            <label htmlFor="field-crop" className="field-label">
              Crop (optional)
            </label>
            <select id="field-crop" className="input" value={fieldCrop} onChange={(e) => setFieldCrop(e.target.value)}>
              <option value="">undecided</option>
              {crops.map((crop) => (
                <option key={crop.crop_id} value={crop.crop_id}>
                  {crop.name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="field-area" className="field-label">
              Area, hectares (optional)
            </label>
            <input
              id="field-area"
              className="input"
              inputMode="decimal"
              value={fieldArea}
              onChange={(e) => setFieldArea(e.target.value)}
              placeholder="e.g. 2.5"
            />
          </div>
        </div>
        <button type="submit" className="btn-primary mt-4" disabled={busy || !fieldName.trim()}>
          {busy ? "Saving…" : "Add field"}
        </button>
      </form>

      <section className="card" aria-label="Fields">
        <h2 className="text-lg font-bold text-stone-900">Fields</h2>
        {detail.fields.length === 0 ? (
          <p className="alert-info mt-3" role="note">
            No fields yet — analyses can be attached to fields once you add one.
          </p>
        ) : (
          <ul className="mt-4 divide-y divide-stone-200">
            {detail.fields.map((field) => (
              <li key={field.id} className="py-3">
                {editingField === field.id ? (
                  <div className="grid gap-3 sm:grid-cols-4">
                    <input
                      aria-label="Field name"
                      className="input"
                      value={editName}
                      onChange={(e) => setEditName(e.target.value)}
                      maxLength={120}
                    />
                    <select aria-label="Crop" className="input" value={editCrop} onChange={(e) => setEditCrop(e.target.value)}>
                      <option value="">undecided</option>
                      {crops.map((crop) => (
                        <option key={crop.crop_id} value={crop.crop_id}>
                          {crop.name}
                        </option>
                      ))}
                    </select>
                    <input
                      aria-label="Area in hectares"
                      className="input"
                      inputMode="decimal"
                      value={editArea}
                      onChange={(e) => setEditArea(e.target.value)}
                      placeholder="ha"
                    />
                    <div className="flex gap-2">
                      <button type="button" className="btn-primary" onClick={() => saveField(field)} disabled={busy || !editName.trim()}>
                        Save
                      </button>
                      <button type="button" className="btn-ghost" onClick={() => setEditingField(null)}>
                        Cancel
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <p className="font-semibold text-stone-900">{field.name}</p>
                      <p className="text-sm text-stone-500">
                        {field.crop_id ?? "crop undecided"}
                        {field.area_ha !== null ? ` · ${field.area_ha} ha` : ""}
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      <Link href={`/map?field=${field.id}`} className="link-cta">
                        Map →
                      </Link>
                      <button type="button" className="btn-secondary" onClick={() => beginEdit(field)}>
                        Edit
                      </button>
                      <button type="button" className="btn-danger" onClick={() => removeField(field)}>
                        Delete
                      </button>
                    </div>
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
