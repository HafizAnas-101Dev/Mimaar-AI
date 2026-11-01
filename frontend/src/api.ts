import type { Edits, HistoryEntry, PriceListInfo, PriceTable, Result, RolePhoto, SpaceMode, WriterStatus } from "./types";

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init);
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    const detail = body?.detail;
    const message = typeof detail === "string" ? detail : Array.isArray(detail) ? detail.map((d) => d.msg).join("; ") : null;
    throw new Error(message ?? `Request failed (${res.status})`);
  }
  return body as T;
}

/** A single wall goes to /api/analyze; a room (any number of surface photos) to /api/analyze-room. */
export const analyze = (mode: SpaceMode, photos: RolePhoto[], fields: Record<string, string>) => {
  const form = new FormData();
  if (mode === "wall") {
    form.append("file", photos[0].file);
    form.append("role", "wall");
  } else {
    photos.forEach((p) => form.append("files", p.file));
    form.append("roles", photos.map((p) => p.role).join(","));
  }
  Object.entries(fields).forEach(([k, v]) => v && form.append(k, v));
  return request<Result>(mode === "wall" ? "/api/analyze" : "/api/analyze-room", { method: "POST", body: form });
};

/** Second half of a deferred analysis: the Muse model writes the report (can take minutes locally). */
export const finishReport = (id: string, retry = false) =>
  request<Result>(`/api/reason/${id}${retry ? "?retry=true" : ""}`, { method: "POST" });

/** Corrections recompute counts and cost from the original detections; empty edits undo them. */
export const editResult = (id: string, edits: Edits) =>
  request<Result>(`/api/edit/${id}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(edits) });

/** The same analysis with its report in another language; instant, then finishReport for the write-up. */
export const changeLanguage = (id: string, language: string) => {
  const form = new FormData();
  form.append("language", language);
  return request<Result>(`/api/language/${id}`, { method: "POST", body: form });
};

export const getHealth = () => request<{ mode: string; backend: string; reasoner: string; writer: WriterStatus }>("/api/health");

export const listHistory = () => request<HistoryEntry[]>("/api/history");
export const getHistory = (id: string) => request<Result>(`/api/history/${id}`);
export const deleteHistory = (id: string) => request<{ deleted: boolean }>(`/api/history/${id}`, { method: "DELETE" });
export const clearHistory = () => request<{ deleted: number }>("/api/history", { method: "DELETE" });
export const renameHistory = (id: string, title: string) =>
  request<{ renamed: boolean }>(`/api/history/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title }),
  });

export const getPrices = () => request<PriceTable>("/api/prices");
export const savePrices = (table: PriceTable) =>
  request<PriceTable>("/api/prices", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(table),
  });

export const listPriceLists = () => request<PriceListInfo[]>("/api/price-lists");
export const activatePriceList = (id: string) => request<PriceTable>(`/api/price-lists/${id}/activate`, { method: "POST" });
export const deletePriceList = (id: string) => request<{ deleted: boolean }>(`/api/price-lists/${id}`, { method: "DELETE" });

export const listSamples = () => request<string[]>("/api/samples");
export async function loadSample(name: string): Promise<File> {
  const res = await fetch(`/api/samples/${encodeURIComponent(name)}`);
  return new File([await res.blob()], name, { type: "image/jpeg" });
}
