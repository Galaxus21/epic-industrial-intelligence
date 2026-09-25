/**
 * EPIC — API Client
 * Typed fetch helpers for all backend endpoints.
 * The streaming query is handled via fetch + ReadableStream.
 */
import type {
  Equipment, GraphData, Document, DocumentDetail,
  TimelineEvent, AgentEvent, SavedWorkOrder, GeneratedDoc, MaintenanceRecord,
} from "./types";

export type { MaintenanceRecord } from "./types";

// Server components run inside Docker → use INTERNAL_API_URL (service name).
// Client components run in the browser → use empty string so requests go through
// the Next.js rewrite proxy (/api/:path* → backend:8000).
const isServer = typeof window === "undefined";
const BASE = isServer
  ? (process.env.INTERNAL_API_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000")
  : "";

const SESSION_COOKIE_NAME = "epicSession";

export interface RequestOptions {
  signal?: AbortSignal;
  timeoutMs?: number;
}

const maxPlainErrorChars = 300;

// A local Ollama model can take minutes for one reply: the backend waits up to 180 s per attempt, twice
// (backend/app/services/providers/ollamaProvider.py). next.config.mjs keeps its proxy timeout above this.
export const modelReplyTimeoutMs = 6 * 60 * 1000;

export const forbiddenMessage = "Your role cannot do this";

/** A failed HTTP call: the server's message plus the status, so a caller can tell 403 from 500. */
export class ApiError extends Error {
  constructor(message: string, readonly status: number) {
    super(message);
    this.name = "ApiError";
  }
}

/**
 * Extract backend error detail (string or FastAPI validation error array)
 * into a descriptive, user-actionable ApiError.
 */
export async function extractError(res: Response, fallbackPrefix: string): Promise<ApiError> {
  const detail = await readErrorDetail(res);
  return new ApiError(detail ?? `${fallbackPrefix} → ${res.status}${res.statusText ? " " + res.statusText : ""}`, res.status);
}

/** The text to show for a failed action: one fixed sentence for 403, otherwise the server's message. */
export function errorText(err: unknown, fallback: string): string {
  if (err instanceof ApiError && err.status === 403) return forbiddenMessage;
  if (err instanceof Error && err.message) return err.message;
  return fallback;
}

async function readErrorDetail(res: Response): Promise<string | null> {
  const text = await res.text().catch(() => "");
  if (!text) return null;
  try {
    const json = JSON.parse(text) as Record<string, unknown> | null;
    if (!json || typeof json !== "object") return null;
    const detail = json.detail ?? json.message ?? json.error;
    if (typeof detail === "string" && detail.trim()) return detail.trim();
    if (Array.isArray(detail)) return formatValidationErrors(detail);
    return null;
  } catch {
    const isPlainText = text.length < maxPlainErrorChars && !text.includes("<html") && !text.includes("<!DOCTYPE");
    return isPlainText ? text.trim() : null;
  }
}

function formatValidationErrors(detail: unknown[]): string | null {
  const msgs = detail.map((d: unknown) => {
    if (typeof d === "string") return d;
    if (d && typeof d === "object") {
      const item = d as Record<string, unknown>;
      const locArr = Array.isArray(item.loc) ? item.loc.filter(l => l !== "body") : [];
      const loc = locArr.join(".");
      const msg = typeof item.msg === "string" ? item.msg : JSON.stringify(item);
      return loc ? `${loc}: ${msg}` : msg;
    }
    return String(d);
  }).filter(Boolean);
  return msgs.length > 0 ? msgs.join("; ") : null;
}

/**
 * Attaches a default 30-second timeout (AbortSignal.timeout(30000))
 * combined with user-supplied signal if provided.
 */
export function getRequestSignal(userSignal?: AbortSignal, timeoutMs = 30000): { signal: AbortSignal; cleanup: () => void } {
  if (userSignal?.aborted) {
    return { signal: userSignal, cleanup: () => {} };
  }

  const hasTimeout = typeof AbortSignal !== "undefined" && typeof AbortSignal.timeout === "function";
  const hasAny = typeof AbortSignal !== "undefined" && typeof AbortSignal.any === "function";

  if (hasTimeout) {
    const timeoutSignal = AbortSignal.timeout(timeoutMs);
    if (!userSignal) {
      return { signal: timeoutSignal, cleanup: () => {} };
    }
    if (hasAny) {
      return { signal: AbortSignal.any([timeoutSignal, userSignal]), cleanup: () => {} };
    }
  }

  const controller = new AbortController();
  const timer = setTimeout(() => {
    controller.abort(new DOMException("The operation timed out.", "TimeoutError"));
  }, timeoutMs);

  let onAbort: (() => void) | null = null;
  if (userSignal) {
    onAbort = () => {
      clearTimeout(timer);
      controller.abort(userSignal.reason);
    };
    userSignal.addEventListener("abort", onAbort, { once: true });
  }

  return {
    signal: controller.signal,
    cleanup: () => {
      clearTimeout(timer);
      if (userSignal && onAbort) {
        userSignal.removeEventListener("abort", onAbort);
      }
    },
  };
}

async function _authHeaders(): Promise<Record<string, string>> {
  if (isServer) {
    try {
      const nextHeaders = "next/headers";
      const { cookies } = await import(/* webpackIgnore: true */ nextHeaders);
      const session = cookies().get(SESSION_COOKIE_NAME);
      if (session?.value) {
        return { Cookie: `${SESSION_COOKIE_NAME}=${session.value}` };
      }
    } catch {
      // In non-request context or static build phase
    }
    return {};
  }
  // Browser automatically includes HttpOnly cookie on same-origin proxy
  return {};
}

export async function get<T>(path: string, options?: RequestOptions): Promise<T> {
  const { signal, cleanup } = getRequestSignal(options?.signal, options?.timeoutMs);
  try {
    const res = await fetch(`${BASE}${path}`, {
      cache: "no-store",
      headers: { ...(await _authHeaders()) },
      signal,
    });
    if (!res.ok) throw await extractError(res, `GET ${path}`);
    return (await res.json()) as T;
  } finally {
    cleanup();
  }
}

// ─── Auth ────────────────────────────────────────────────────────────────────

export async function login(employeeId: string, password?: string, options?: RequestOptions): Promise<{ token?: string; user: unknown }> {
  const { signal, cleanup } = getRequestSignal(options?.signal, options?.timeoutMs);
  try {
    const res = await fetch(`${BASE}/api/v1/users/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ employee_id: employeeId, password: password || null }),
      signal,
    });
    if (!res.ok) {
      throw await extractError(res, "Login failed");
    }
    const data = await res.json();
    // HttpOnly cookie 'epicSession' is set directly by backend via Set-Cookie header.
    return data;
  } finally {
    cleanup();
  }
}

export async function logout(options?: RequestOptions): Promise<void> {
  const { signal, cleanup } = getRequestSignal(options?.signal, options?.timeoutMs);
  try {
    await fetch(`${BASE}/api/v1/users/logout`, {
      method: "POST",
      headers: { ...(await _authHeaders()) },
      signal,
    });
  } catch {
    // Ignore offline errors on logout
  } finally {
    cleanup();
  }
}

// ─── Equipment ────────────────────────────────────────────────────────────────

export const listEquipment = (options?: RequestOptions) => get<Equipment[]>("/api/v1/equipment", options);
export const getEquipment = (id: string, options?: RequestOptions) => get<Equipment>(`/api/v1/equipment/${id}`, options);
export const getEquipmentBrain = (id: string, options?: RequestOptions) => get<Record<string, unknown>>(`/api/v1/equipment/${id}/brain`, options);
export const getEquipmentTimeline = (id: string) =>
  get<{ equipment_id: string; events: TimelineEvent[] }>(`/api/v1/equipment/${id}/timeline`);
export const getEquipmentSensors = (id: string) =>
  get<{ equipment_id: string; sensors: Record<string, { ts: string; value: number }[]> }>(`/api/v1/equipment/${id}/sensors`);

// ─── Knowledge Graph ──────────────────────────────────────────────────────────

export const getFullGraph = () => get<GraphData>("/api/v1/knowledge-graph");
export const traverseGraph = (equipmentId: string, depth = 2) =>
  get<GraphData>(`/api/v1/knowledge-graph/${equipmentId}/traverse?depth=${depth}`);

// ─── Documents ────────────────────────────────────────────────────────────────

export const listDocuments = () => get<Document[]>("/api/v1/documents");
export const getDocument = (id: string) => get<DocumentDetail>(`/api/v1/documents/${encodeURIComponent(id)}`);

export async function uploadDocument(file: File, equipmentId = "", options?: RequestOptions): Promise<{ doc_id: string; status: string }> {
  const { signal, cleanup } = getRequestSignal(options?.signal, options?.timeoutMs);
  try {
    const form = new FormData();
    form.append("file", file);
    form.append("equipment_id", equipmentId);
    const res = await fetch(`${BASE}/api/v1/documents/upload`, {
      method: "POST",
      headers: { ...(await _authHeaders()) },
      body: form,
      signal,
    });
    if (!res.ok) throw await extractError(res, "Upload failed");
    return res.json();
  } finally {
    cleanup();
  }
}

export async function checkDuplicateDocument(
  filename: string,
  hash: string,
  options?: RequestOptions,
): Promise<{ matches: Array<{ id: string; name: string; type: string; date: string; match_reason: string }> }> {
  return get(`/api/v1/documents/check-duplicate?filename=${encodeURIComponent(filename)}&hash=${encodeURIComponent(hash)}`, options);
}

// ─── Maintenance Records ──────────────────────────────────────────────────────

export const listMaintenanceRecords = (params?: { equipment_id?: string; status?: string; type?: string }, options?: RequestOptions) => {
  const qs = new URLSearchParams();
  if (params?.equipment_id) qs.set("equipment_id", params.equipment_id);
  if (params?.status) qs.set("status", params.status);
  if (params?.type) qs.set("type", params.type);
  const q = qs.toString();
  return get<MaintenanceRecord[]>(`/api/v1/maintenance${q ? `?${q}` : ""}`, options);
};

// ─── Work Orders ─────────────────────────────────────────────────────────────

export async function post<T>(path: string, body: unknown, options?: RequestOptions): Promise<T> {
  const { signal, cleanup } = getRequestSignal(options?.signal, options?.timeoutMs);
  try {
    const res = await fetch(`${BASE}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...(await _authHeaders()) },
      body: JSON.stringify(body),
      signal,
    });
    if (!res.ok) throw await extractError(res, `POST ${path}`);
    return (await res.json()) as T;
  } finally {
    cleanup();
  }
}

export async function patch<T>(path: string, body: unknown, options?: RequestOptions): Promise<T> {
  const { signal, cleanup } = getRequestSignal(options?.signal, options?.timeoutMs);
  try {
    const res = await fetch(`${BASE}${path}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json", ...(await _authHeaders()) },
      body: JSON.stringify(body),
      signal,
    });
    if (!res.ok) throw await extractError(res, `PATCH ${path}`);
    return (await res.json()) as T;
  } finally {
    cleanup();
  }
}

export async function del(path: string, options?: RequestOptions): Promise<void> {
  const { signal, cleanup } = getRequestSignal(options?.signal, options?.timeoutMs);
  try {
    const res = await fetch(`${BASE}${path}`, {
      method: "DELETE",
      headers: { ...(await _authHeaders()) },
      signal,
    });
    if (!res.ok && res.status !== 204) throw await extractError(res, `DELETE ${path}`);
  } finally {
    cleanup();
  }
}

export const listWorkOrders = (equipmentId?: string) =>
  get<SavedWorkOrder[]>(`/api/v1/ops/work-orders${equipmentId ? `?equipment_id=${equipmentId}` : ""}`);
export const createWorkOrder = (body: object) => post<SavedWorkOrder>("/api/v1/ops/work-orders", body);
export const updateWorkOrderStep = (id: string, body: object) => patch<SavedWorkOrder>(`/api/v1/ops/work-orders/${id}/step`, body);
export const completeWorkOrder = (id: string, body: object) => post<SavedWorkOrder>(`/api/v1/ops/work-orders/${id}/complete`, body);
export const updateWorkOrder = (id: string, body: object) => patch<SavedWorkOrder>(`/api/v1/ops/work-orders/${id}`, body);
export const deleteWorkOrder = (id: string) => del(`/api/v1/ops/work-orders/${id}`);

export type OpsProposedChanges = {
  description?: string;
  risk_level?: string;
  toggle_steps?: Array<{ step_index: number; checked: boolean }>;
  add_steps?: Array<{
    phase: string; title: string; description: string;
    safety_note?: string | null; expected_duration_minutes?: number;
  }>;
};
export type OpsChatResponse = {
  answer: string;
  proposed_changes: OpsProposedChanges | null;
  withheld_changes?: string[];
};

export const chatWithWorkOrder = (
  id: string, body: { message: string; history: Array<{ role: string; content: string }> }
) => post<OpsChatResponse>(`/api/v1/ops/work-orders/${id}/chat`, body, { timeoutMs: modelReplyTimeoutMs });
export const addWorkOrderSteps = (id: string, steps: object[]) =>
  post<SavedWorkOrder>(`/api/v1/ops/work-orders/${id}/steps/add`, { steps });

export const deleteDocument = (id: string) => del(`/api/v1/documents/${id}`);


// ─── Sensors ─────────────────────────────────────────────────────────────────

export const getEquipmentSensorDashboard = (id: string) => get<unknown>(`/api/v1/sensors/${id}`);


// AI-assisted document creation — streams SSE events then returns the generated doc
export async function* generateDocument(
  docType: string,
  equipmentId: string,
  description: string,
  extraFields: Record<string, string> = {},
  signal?: AbortSignal,
): AsyncGenerator<{ step: string; message?: string; document?: GeneratedDoc }, void, unknown> {
  const res = await fetch(`${BASE}/api/v1/documents/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(await _authHeaders()) },
    body: JSON.stringify({
      doc_type: docType,
      equipment_id: equipmentId,
      description,
      extra_fields: extraFields,
    }),
    signal,
  });
  if (!res.ok || !res.body) throw await extractError(res, "Generate failed");

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  const onAbort = () => {
    reader.cancel().catch(() => {});
  };

  if (signal) {
    if (signal.aborted) {
      await reader.cancel().catch(() => {});
      return;
    }
    signal.addEventListener("abort", onAbort, { once: true });
  }

  try {
    while (true) {
      if (signal?.aborted) {
        await reader.cancel().catch(() => {});
        return;
      }
      const { done, value } = await reader.read();
      if (done) break;
      try {
        buffer += decoder.decode(value, { stream: true });
      } catch {
        continue;
      }
      const lines = buffer.split("\n\n");
      buffer = lines.pop() ?? "";
      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        const payload = line.slice(6).trim();
        if (payload === "[DONE]") return;
        try {
          yield JSON.parse(payload);
        } catch {
          console.warn("Ignored malformed SSE chunk in generateDocument:", payload);
        }
      }
    }
  } catch (err: unknown) {
    if (signal?.aborted) {
      return;
    }
    throw err;
  } finally {
    if (signal) {
      signal.removeEventListener("abort", onAbort);
    }
    try {
      reader.releaseLock();
    } catch {
      // ignore
    }
  }
}

export const saveGeneratedDocument = (body: {
  doc_type: string;
  equipment_id: string;
  title: string;
  sections: Record<string, string>;
  entities: Record<string, unknown>;
}) => post<{ id: string; name: string; type: string; status: string; date: string }>(
  "/api/v1/documents/save-generated",
  body,
);

// ─── Streaming Agent Query ────────────────────────────────────────────────────

export async function* streamAgentQuery(
  equipmentId: string | null | undefined,
  query: string,
  history: Array<{ role: string; content: string }> = [],
  signal?: AbortSignal,
): AsyncGenerator<AgentEvent, void, unknown> {
  const res = await fetch(`${BASE}/api/v1/agents/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(await _authHeaders()) },
    body: JSON.stringify({
      equipment_id: equipmentId || null, query, history,
    }),
    signal,
  });

  if (!res.ok || !res.body) throw await extractError(res, "Query failed");

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  const onAbort = () => {
    reader.cancel().catch(() => {});
  };

  if (signal) {
    if (signal.aborted) {
      await reader.cancel().catch(() => {});
      return;
    }
    signal.addEventListener("abort", onAbort, { once: true });
  }

  let receivedDone = false;
  try {
    while (true) {
      if (signal?.aborted) {
        await reader.cancel().catch(() => {});
        return;
      }
      const { done, value } = await reader.read();
      if (done) break;

      try {
        buffer += decoder.decode(value, { stream: true });
      } catch {
        continue;
      }

      const lines = buffer.split("\n\n");
      buffer = lines.pop() ?? "";

      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        const payload = line.slice(6).trim();
        if (payload === "[DONE]") {
          receivedDone = true;
          return;
        }
        try {
          yield JSON.parse(payload) as AgentEvent;
        } catch {
          // Safe try-catch wrapper around SSE stream parsing:
          // ignore or log malformed chunks/events without crashing the stream
          console.warn("Ignored malformed SSE chunk in streamAgentQuery:", payload);
        }
      }
    }
  } catch (err: unknown) {
    if (signal?.aborted) {
      return;
    }
    throw err;
  } finally {
    if (signal) {
      signal.removeEventListener("abort", onAbort);
    }
    try {
      reader.releaseLock();
    } catch {
      // ignore
    }
  }

  if (!receivedDone && !signal?.aborted) {
    throw new Error("Stream ended unexpectedly without [DONE] signal");
  }
}
