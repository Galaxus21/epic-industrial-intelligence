/**
 * AI Operations Brain — API Client
 * Typed fetch helpers for all backend endpoints.
 * The streaming query is handled via fetch + ReadableStream.
 */
import type {
  Equipment, GraphData, Document, DocumentDetail, ComplianceStatus, ComplianceAIAnalysis,
  TimelineEvent, AgentEvent, SavedChecklist, SavedWorkOrder, GeneratedDoc,
} from "./types";

// Server components run inside Docker → use INTERNAL_API_URL (service name).
// Client components run in the browser → use empty string so requests go through
// the Next.js rewrite proxy (/api/:path* → backend:8000).
const isServer = typeof window === "undefined";
const BASE = isServer
  ? (process.env.INTERNAL_API_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000")
  : "";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`GET ${path} → ${res.status}`);
  return res.json() as Promise<T>;
}

// ─── Project / Plant hierarchy ────────────────────────────────────────────────

export interface HierarchyEquipment {
  id: string; name: string; type: string;
  status: string; criticality: string; health_score: number | null;
}
export interface HierarchyPlant {
  id: string; name: string; code: string;
  status: string; equipment: HierarchyEquipment[];
}
export interface HierarchyProject {
  id: string; name: string; code: string;
  status: string; plants: HierarchyPlant[];
}
export interface ProjectHierarchy {
  projects: HierarchyProject[];
  unassigned_equipment: HierarchyEquipment[];
}

export const getProjectHierarchy = () =>
  get<ProjectHierarchy>("/api/v1/pm/hierarchy");
export const listProjects = () =>
  get<Array<{ id: string; name: string; code: string; status: string; plant_ids: string[] }>>("/api/v1/pm/projects");
export const listPlants = (projectId?: string) =>
  get<Array<{ id: string; name: string; code: string; status: string; equipment_ids: string[]; project_id: string | null }>>(
    `/api/v1/pm/plants${projectId ? `?project_id=${projectId}` : ""}`
  );

// ─── Equipment ────────────────────────────────────────────────────────────────

export const listEquipment = () => get<Equipment[]>("/api/v1/equipment");
export const getEquipment = (id: string) => get<Equipment>(`/api/v1/equipment/${id}`);
export const getEquipmentBrain = (id: string) => get<Record<string, unknown>>(`/api/v1/equipment/${id}/brain`);
export const getEquipmentTimeline = (id: string) =>
  get<{ equipment_id: string; events: TimelineEvent[] }>(`/api/v1/equipment/${id}/timeline`);
export const getEquipmentSensors = (id: string) =>
  get<{ equipment_id: string; sensors: Record<string, { ts: string; value: number }[]> }>(`/api/v1/equipment/${id}/sensors`);
export const getEquipmentSubgraph = (id: string) => get<GraphData>(`/api/v1/equipment/${id}/subgraph`);

// ─── Knowledge Graph ──────────────────────────────────────────────────────────

export const getFullGraph = () => get<GraphData>("/api/v1/knowledge-graph");

// ─── Documents ────────────────────────────────────────────────────────────────

export const listDocuments = () => get<Document[]>("/api/v1/documents");
export const getDocument = (id: string) => get<DocumentDetail>(`/api/v1/documents/${id}`);
export const listDocumentDrawings = () =>
  get<{ id: string; name: string; type: string; equipment_ids: string[]; date: string }[]>(
    "/api/v1/documents/drawings-list"
  );

export async function uploadDocument(file: File, equipmentId = ""): Promise<{ doc_id: string; status: string }> {
  const form = new FormData();
  form.append("file", file);
  form.append("equipment_id", equipmentId);
  const res = await fetch(`${BASE}/api/v1/documents/upload`, { method: "POST", body: form });
  if (!res.ok) throw new Error(`Upload failed → ${res.status}`);
  return res.json();
}

export async function checkDuplicateDocument(
  filename: string,
  hash: string,
): Promise<{ matches: Array<{ id: string; name: string; type: string; date: string; match_reason: string }> }> {
  try {
    const res = await fetch(
      `${BASE}/api/v1/documents/check-duplicate?filename=${encodeURIComponent(filename)}&hash=${encodeURIComponent(hash)}`
    );
    if (!res.ok) return { matches: [] };
    return res.json();
  } catch {
    return { matches: [] };
  }
}
// ─── Compliance ───────────────────────────────────────────────────────────────

export const listCompliance = () => get<ComplianceStatus[]>("/api/v1/compliance");
export const getEquipmentCompliance = (id: string) => get<ComplianceStatus>(`/api/v1/compliance/${id}`);
export const getComplianceAIAnalysis = () => get<ComplianceAIAnalysis>("/api/v1/compliance/analyze");
// Write helpers (previously no write path existed)
export const upsertCompliance = (equipmentId: string, body: object) =>
  post<ComplianceStatus>(`/api/v1/compliance/${equipmentId}`, body);
export const patchCompliance = (equipmentId: string, body: { overall_score?: number; status?: string }) =>
  patch<ComplianceStatus>(`/api/v1/compliance/${equipmentId}`, body);
export const resolveComplianceIssue = (
  equipmentId: string,
  body: { item: string; resolved_by?: string; resolution_note?: string },
) => post<{ equipment_id: string; resolved_issue: string; new_score: number; new_status: string; open_issues: number }>(
  `/api/v1/compliance/${equipmentId}/resolve-issue`, body,
);

// ─── Spare Parts ──────────────────────────────────────────────────────────────

export type SparePart = {
  id: string; name: string; part_number: string | null;
  equipment_ids: string[]; quantity_on_hand: number; reorder_point: number;
  lead_time_days: number | null; location: string | null;
  unit_cost_usd: number | null; status: string;
};
export const listSpareParts = (equipmentId?: string) =>
  get<SparePart[]>(`/api/v1/spare-parts${equipmentId ? `?equipment_id=${equipmentId}` : ""}`);
export const getSparePart = (id: string) => get<SparePart>(`/api/v1/spare-parts/${id}`);
export const createSparePart = (body: Partial<SparePart>) =>
  post<SparePart>("/api/v1/spare-parts", body);
export const updateSparePart = (id: string, body: Partial<SparePart>) =>
  patch<SparePart>(`/api/v1/spare-parts/${id}`, body);
export const deleteSparePart = (id: string) => del(`/api/v1/spare-parts/${id}`);
export const issueSparePartStock = (
  id: string,
  body: { quantity: number; issued_to?: string; work_order_id?: string; notes?: string },
) => post<{ id: string; quantity_issued: number; quantity_remaining: number; status: string }>(
  `/api/v1/spare-parts/${id}/issue`, body,
);

// ─── Maintenance Records ──────────────────────────────────────────────────────

export interface MaintenanceRecord {
  id: string;
  equipment_id: string;
  type: string;
  description: string;
  status: string;
  date: string | null;
  scheduled_date: string | null;
  technician: string | null;
  findings: string | null;
  overdue_days: number | null;
  source?: string;
  ai_extracted?: boolean;
}

export const listMaintenanceRecords = (params?: { equipment_id?: string; status?: string; type?: string }) => {
  const qs = new URLSearchParams();
  if (params?.equipment_id) qs.set("equipment_id", params.equipment_id);
  if (params?.status) qs.set("status", params.status);
  if (params?.type) qs.set("type", params.type);
  const q = qs.toString();
  return get<MaintenanceRecord[]>(`/api/v1/maintenance${q ? `?${q}` : ""}`);
};
export const getMaintenanceRecord = (id: string) => get<MaintenanceRecord>(`/api/v1/maintenance/${id}`);
export const createMaintenanceRecord = (body: Partial<MaintenanceRecord>) =>
  post<MaintenanceRecord>("/api/v1/maintenance", body);
export const updateMaintenanceRecord = (id: string, body: Partial<MaintenanceRecord>) =>
  patch<MaintenanceRecord>(`/api/v1/maintenance/${id}`, body);

// ─── Work Orders & Checklists ─────────────────────────────────────────────────

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`POST ${path} → ${res.status}`);
  return res.json() as Promise<T>;
}

async function patch<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`PATCH ${path} → ${res.status}`);
  return res.json() as Promise<T>;
}

async function del(path: string): Promise<void> {
  const res = await fetch(`${BASE}${path}`, { method: "DELETE" });
  if (!res.ok && res.status !== 204) throw new Error(`DELETE ${path} → ${res.status}`);
}

export const listChecklists = (equipmentId?: string) =>
  get<SavedChecklist[]>(`/api/v1/ops/checklists${equipmentId ? `?equipment_id=${equipmentId}` : ""}`);
export const getChecklist = (id: string) => get<SavedChecklist>(`/api/v1/ops/checklists/${id}`);
export const createChecklist = (body: object) => post<SavedChecklist>("/api/v1/ops/checklists", body);
export const updateChecklistItem = (id: string, body: object) => patch<SavedChecklist>(`/api/v1/ops/checklists/${id}/item`, body);
export const completeChecklist = (id: string, body: object) => post<SavedChecklist>(`/api/v1/ops/checklists/${id}/complete`, body);
export const updateChecklist = (id: string, body: object) => patch<SavedChecklist>(`/api/v1/ops/checklists/${id}`, body);
export const deleteChecklist = (id: string) => del(`/api/v1/ops/checklists/${id}`);

export const listWorkOrders = (equipmentId?: string) =>
  get<SavedWorkOrder[]>(`/api/v1/ops/work-orders${equipmentId ? `?equipment_id=${equipmentId}` : ""}`);
export const getWorkOrder = (id: string) => get<SavedWorkOrder>(`/api/v1/ops/work-orders/${id}`);
export const createWorkOrder = (body: object) => post<SavedWorkOrder>("/api/v1/ops/work-orders", body);
export const updateWorkOrderStep = (id: string, body: object) => patch<SavedWorkOrder>(`/api/v1/ops/work-orders/${id}/step`, body);
export const completeWorkOrder = (id: string, body: object) => post<SavedWorkOrder>(`/api/v1/ops/work-orders/${id}/complete`, body);
export const updateWorkOrder = (id: string, body: object) => patch<SavedWorkOrder>(`/api/v1/ops/work-orders/${id}`, body);
export const deleteWorkOrder = (id: string) => del(`/api/v1/ops/work-orders/${id}`);

export type OpsProposedChanges = {
  description?: string;
  risk_level?: string;
  add_items?: string[];
  toggle_items?: Array<{ index: number; checked: boolean }>;
  toggle_steps?: Array<{ step_index: number; checked: boolean }>;
  add_steps?: Array<{
    phase: string; title: string; description: string;
    safety_note?: string | null; expected_duration_minutes?: number;
  }>;
};
export type OpsChatResponse = { answer: string; proposed_changes: OpsProposedChanges | null };

export const chatWithWorkOrder = (
  id: string, body: { message: string; history: Array<{ role: string; content: string }> }
) => post<OpsChatResponse>(`/api/v1/ops/work-orders/${id}/chat`, body);
export const chatWithChecklist = (
  id: string, body: { message: string; history: Array<{ role: string; content: string }> }
) => post<OpsChatResponse>(`/api/v1/ops/checklists/${id}/chat`, body);
export const addChecklistItems = (id: string, items: string[]) =>
  post<SavedChecklist>(`/api/v1/ops/checklists/${id}/items/add`, { items });
export const addWorkOrderSteps = (id: string, steps: object[]) =>
  post<SavedWorkOrder>(`/api/v1/ops/work-orders/${id}/steps/add`, { steps });

export const deleteDocument = (id: string) => del(`/api/v1/documents/${id}`);
export const updateDocument = (id: string, body: { name: string }) =>
  patch<{ id: string; name: string }>(`/api/v1/documents/${id}`, body);

// ─── Root Cause Analysis ──────────────────────────────────────────────────────

export const getRCAEvents = () => get<unknown[]>("/api/v1/rca/events");
export const analyzeRootCause = (body: { symptom: string; equipment_id?: string; severity?: string }) =>
  post<unknown>("/api/v1/rca/analyze", body);

// ─── Plant Digital Twin ───────────────────────────────────────────────────────

export const getPlantTree = () => get<unknown>("/api/v1/plant/tree");
export const getPlantAreas = () => get<unknown>("/api/v1/plant/areas");
export const getPlantStatus = () => get<unknown>("/api/v1/plant/status");

// ─── Safety / PTW ─────────────────────────────────────────────────────────────

export const getActivePermits = () => get<unknown>("/api/v1/safety/permits");
export const checkSafetyConflict = (body: { equipment_id: string; action: string; planned_start?: string }) =>
  post<unknown>("/api/v1/safety/check-conflict", body);
export const getHazopNotes = (equipmentId: string) =>
  get<unknown>(`/api/v1/safety/hazop/${equipmentId}`);

// ─── Smart Forms ──────────────────────────────────────────────────────────────

export const getFormTemplates = () => get<unknown[]>("/api/v1/forms/templates");
export const generateForm = (body: { description: string; equipment_id?: string }) =>
  post<unknown>("/api/v1/forms/generate", body);
export const submitForm = (body: { form_type: string; equipment_id?: string; field_values: Record<string, string> }) =>
  post<unknown>("/api/v1/forms/submit", body);

export async function uploadFormImage(file: File): Promise<{ url: string; filename: string }> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${BASE}/api/v1/forms/upload-image`, { method: "POST", body: form });
  if (!res.ok) throw new Error(`Image upload failed → ${res.status}`);
  return res.json();
}

// ─── Sensors ─────────────────────────────────────────────────────────────────

export const listAllSensors = () => get<unknown[]>("/api/v1/sensors");
export const getEquipmentSensorDashboard = (id: string) => get<unknown>(`/api/v1/sensors/${id}`);
export const getSingleSensor = (id: string, key: string) => get<unknown>(`/api/v1/sensors/${id}/${key}`);

// ─── Audit ────────────────────────────────────────────────────────────────────

export const getAuditLog = (params?: { object_type?: string; equipment_id?: string; action?: string; days?: number; limit?: number; offset?: number }) => {
  const qs = new URLSearchParams();
  if (params?.object_type)  qs.set("object_type",  params.object_type);
  if (params?.equipment_id) qs.set("equipment_id", params.equipment_id);
  if (params?.action)       qs.set("action",        params.action);
  if (params?.days)         qs.set("days",           String(params.days));
  if (params?.limit)        qs.set("limit",          String(params.limit));
  if (params?.offset)       qs.set("offset",         String(params.offset));
  return get<unknown>(`/api/v1/audit${qs.toString() ? "?" + qs.toString() : ""}`);
};
export const getObjectHistory = (objectType: string, objectId: string) =>
  get<unknown>(`/api/v1/audit/${objectType}/${objectId}`);
export const getRelationMap = (equipmentId: string) =>
  get<unknown>(`/api/v1/audit/relations/${equipmentId}`);

// ─── Reports ──────────────────────────────────────────────────────────────────

export const getReportOverview    = () => get<unknown>("/api/v1/reports/overview");
export const getReportEquipment   = () => get<unknown>("/api/v1/reports/equipment");
export const getReportMaintenance = () => get<unknown>("/api/v1/reports/maintenance");
export const getReportIncidents   = () => get<unknown>("/api/v1/reports/incidents");
export const getReportWorkOrders  = () => get<unknown>("/api/v1/reports/work-orders");
export const getReportSafety      = () => get<unknown>("/api/v1/reports/safety");

// Direct live feeds (bypass the pre-aggregated reports, pull raw rows)
export const listIncidentReports = (params?: { status?: string; severity?: string }) => {
  const qs = new URLSearchParams();
  if (params?.status)   qs.set("status",   params.status);
  if (params?.severity) qs.set("severity", params.severity);
  return get<unknown[]>(`/api/v1/incidents${qs.toString() ? "?" + qs.toString() : ""}`);
};
export const listPermits = (params?: { status?: string; permit_type?: string }) => {
  const qs = new URLSearchParams();
  if (params?.status)       qs.set("status",       params.status);
  if (params?.permit_type)  qs.set("permit_type",  params.permit_type);
  return get<unknown[]>(`/api/v1/permits${qs.toString() ? "?" + qs.toString() : ""}`);
};

// ─── Custom Dashboards ────────────────────────────────────────────────────────

export const listDashboards    = () => get<unknown[]>("/api/v1/dashboards");
export const getDashboard      = (id: string) => get<unknown>(`/api/v1/dashboards/${id}`);
export const getWidgetCatalogue = () => get<unknown[]>("/api/v1/dashboards/widgets");
export const createDashboard   = (body: object) => post<unknown>("/api/v1/dashboards", body);
export const updateDashboard   = (id: string, body: object) => patch<unknown>(`/api/v1/dashboards/${id}`, body);
export const deleteDashboard   = (id: string) => del(`/api/v1/dashboards/${id}`);

// AI-assisted document creation — streams SSE events then returns the generated doc
export async function* generateDocument(
  docType: string,
  equipmentId: string,
  description: string,
  extraFields: Record<string, string> = {},
): AsyncGenerator<{ step: string; message?: string; document?: GeneratedDoc }, void, unknown> {
  const res = await fetch(`${BASE}/api/v1/documents/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      doc_type: docType,
      equipment_id: equipmentId,
      description,
      extra_fields: extraFields,
    }),
  });
  if (!res.ok || !res.body) throw new Error(`Generate failed → ${res.status}`);

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n\n");
    buffer = lines.pop() ?? "";
    for (const line of lines) {
      if (!line.startsWith("data: ")) continue;
      const payload = line.slice(6).trim();
      if (payload === "[DONE]") return;
      yield JSON.parse(payload);
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
  equipmentId: string,
  query: string,
  history: Array<{ role: string; content: string }> = [],
  plantId?: string,
  projectId?: string,
): AsyncGenerator<AgentEvent, void, unknown> {
  const res = await fetch(`${BASE}/api/v1/agents/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      equipment_id: equipmentId, query, history,
      plant_id: plantId ?? null,
      project_id: projectId ?? null,
    }),
  });

  if (!res.ok || !res.body) throw new Error(`Query failed → ${res.status}`);

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n\n");
    buffer = lines.pop() ?? "";

    for (const line of lines) {
      if (!line.startsWith("data: ")) continue;
      const payload = line.slice(6).trim();
      if (payload === "[DONE]") return;
      yield JSON.parse(payload) as AgentEvent;
    }
  }
}

// ─── Engineering Drawings ─────────────────────────────────────────────────────

export interface EngDrawing {
  id: string;
  drawing_number: string;
  title: string;
  revision: string;
  drawing_type: string;
  discipline: string | null;
  description: string | null;
  tags: string[];
  project_id: string | null;
  plant_id: string | null;
  original_filename: string;
  file_format: string;
  file_size: number | null;
  status: string;
  extraction_status: string;
  extraction_error: string | null;
  has_svg: boolean;
  analytics: DrawingAnalytics | null;
  analytics_updated_at: string | null;
  created_by: string | null;
  created_at: string;
  updated_at: string;
}

export interface DrawingAnalytics {
  incident_count: number;
  open_incident_count: number;
  high_severity_incidents: number;
  last_incident_date: string | null;
  active_ptw_count: number;
  total_ptw_count: number;
  open_wo_count: number;
  open_inspection_count: number;
  risk_score: number;
  computed_at: string;
}

export interface ProjectTree {
  id: string;
  code: string;
  name: string;
  plants: { id: string; code: string; name: string; drawing_count: number }[];
}

export const listEngDrawings = (projectId?: string, plantId?: string) => {
  const params = new URLSearchParams();
  if (plantId)   params.set("plant_id",   plantId);
  else if (projectId) params.set("project_id", projectId);
  const qs = params.toString();
  return get<EngDrawing[]>(`/api/v1/drawings${qs ? `?${qs}` : ""}`);
};

export const getEngDrawing    = (id: string) => get<EngDrawing>(`/api/v1/drawings/${id}`);
export const getDrawingsTree  = ()           => get<ProjectTree[]>("/api/v1/drawings/projects/tree");
export const getDrawingAnalytics = (id: string) => get<DrawingAnalytics>(`/api/v1/drawings/${id}/analytics`);
export const deleteEngDrawing = (id: string) => del(`/api/v1/drawings/${id}`);
export const reExtractDrawing = (id: string) => post<{ message: string; drawing_id: string }>(
  `/api/v1/drawings/${id}/extract`, {}
);

export async function updateEngDrawing(
  id: string,
  body: Partial<Pick<EngDrawing, "title" | "drawing_number" | "revision" | "drawing_type" | "discipline" | "description" | "tags" | "project_id" | "plant_id">>,
): Promise<EngDrawing> {
  return patch<EngDrawing>(`/api/v1/drawings/${id}`, body);
}

export async function uploadEngDrawing(
  file: File,
  meta: {
    drawing_number: string;
    title: string;
    revision?: string;
    drawing_type?: string;
    discipline?: string;
    description?: string;
    tags?: string;
    project_id?: string;
    plant_id?: string;
    created_by?: string;
  },
): Promise<EngDrawing> {
  const form = new FormData();
  form.append("file", file);
  form.append("drawing_number", meta.drawing_number);
  form.append("title", meta.title);
  if (meta.revision)      form.append("revision",      meta.revision);
  if (meta.drawing_type)  form.append("drawing_type",  meta.drawing_type);
  if (meta.discipline)    form.append("discipline",    meta.discipline);
  if (meta.description)   form.append("description",   meta.description);
  if (meta.tags)          form.append("tags",          meta.tags);
  if (meta.project_id)    form.append("project_id",    meta.project_id);
  if (meta.plant_id)      form.append("plant_id",      meta.plant_id);
  if (meta.created_by)    form.append("created_by",    meta.created_by);
  const res = await fetch(`${BASE}/api/v1/drawings/upload`, { method: "POST", body: form });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail ?? `Upload failed → ${res.status}`);
  }
  return res.json();
}
