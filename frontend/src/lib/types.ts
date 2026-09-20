/**
 * AI Operations Brain — Shared TypeScript Types
 * Domain types for equipment, agents, knowledge graph, and API responses.
 */

// ─── Equipment ────────────────────────────────────────────────────────────────

export interface SensorReading {
  value: number;
  unit: string;
  normal: number;
  alarm?: number;
  trip?: number;
}

export interface Equipment {
  id: string;
  name: string;
  type: string;
  location: string;
  health_score: number | null;
  failure_probability: number | null;
  compliance_score: number | null;
  maintenance_due_days: number | null;
  criticality: string;
  status: string;
  manufacturer?: string;
  model?: string;
  installed_date?: string;
  technicians?: string[];
  current_readings?: Record<string, SensorReading>;
  downstream_equipment?: string[];
  // Auto-discovery metadata (present only on dynamically discovered equipment)
  _discovered?: boolean;
  _source_documents?: string[];
  _manually_registered?: boolean;
}

// ─── Incidents & Maintenance ──────────────────────────────────────────────────

export interface Incident {
  id: string;
  equipment_id: string;
  date: string;
  title: string;
  severity: "Critical" | "High" | "Medium" | "Low";
  symptom: string;
  root_cause?: string;
  action_taken?: string;
  lessons_learned?: string;
  downtime_hours?: number;
  cost_usd?: number;
  technician?: string;
}

export interface MaintenanceRecord {
  id: string;
  equipment_id: string;
  type: string;
  description: string;
  status: "Completed" | "Overdue" | "Scheduled" | string;
  date: string | null;
  scheduled_date?: string | null;
  technician?: string | null;
  findings?: string | null;
  overdue_days?: number | null;
  vibration_de?: number;
}

// ─── Timeline ─────────────────────────────────────────────────────────────────

export interface TimelineEvent {
  date: string;
  type: "installation" | "incident" | "maintenance";
  title: string;
  description: string;
  severity: "info" | "success" | "warning" | "medium" | "high" | "critical";
  detail?: Record<string, unknown>;
}

// ─── Agent Query & Response ───────────────────────────────────────────────────

export interface AgentEvent {
  agent: AgentId;
  status: "active" | "done";
  message: string;
  data?: unknown;
}

export type AgentId =
  | "equipment_brain"
  | "maintenance_advisor"
  | "compliance_agent"
  | "lessons_learned"
  | "document_intelligence"
  | "synthesizer";

export type QuerySourceType =
  | "uploaded_doc"
  | "knowledge_base"
  | "incident_history"
  | "maintenance_record"
  | "ai_inference"
  | "feedback";

export interface QuerySource {
  document: string;
  doc_id: string | null;
  source_type: QuerySourceType;
  section: string;
  confidence: number;
  excerpt?: string;
}

export type WorkOrderPhase = "Preparation" | "Isolation" | "Execution" | "Verification" | "Restart";

export interface WorkOrderStep {
  step: number;
  phase: WorkOrderPhase;
  title: string;
  description: string;
  safety_note: string | null;
  expected_duration_minutes: number;
}

export interface WorkOrder {
  type: string;
  description: string;
  estimated_duration_hours: number;
  required_technicians: number;
  spare_parts: string[];
  safety_precautions: string[];
  procedure_steps: WorkOrderStep[];
}

export interface SynthesisResult {
  response_type?: "chat" | "analysis";
  message?: string;                    // only present when response_type === "chat"
  risk_level: "Critical" | "High" | "Medium" | "Low";
  risk_summary: string;
  probable_causes: { cause: string; probability: number; evidence: string }[];
  immediate_actions: { priority: number; action: string; timeframe: string; owner: string }[];
  inspection_checklist: string[];
  similar_incidents: { incident_id: string; date: string; similarity_score: number; lesson: string }[];
  compliance_issues: { regulation: string; issue: string; severity: string }[];
  affected_downstream: string[];
  required_permits: string[];
  predicted_failure_window: string;
  work_order?: WorkOrder | null;
  sources: QuerySource[];
  explanation: string;
  degraded?: boolean;
  ai_available?: boolean;
  source?: string;
  degraded_reason?: string;
}

// ─── Chat / Query session turn ────────────────────────────────────────────────

export type SessionTurn = {
  id: string;
  equipmentId: string;
  query: string;
  agentEvents: AgentEvent[];
  synthesis: SynthesisResult | null;
  elapsed: number | null;
  isRunning: boolean;
};

// ─── Saved Work Orders & Checklists ──────────────────────────────────────────

export type OpsStatus = "open" | "in_progress" | "completed";

export interface ChecklistItem {
  text: string;
  checked: boolean;
  notes: string;
}

export interface SavedChecklist {
  id: string;
  equipment_id: string;
  query_text: string;
  risk_level: string | null;
  status: OpsStatus;
  items: ChecklistItem[];
  outcome_notes: string | null;
  completed_at: string | null;
  created_at: string;
}

export interface SavedWorkOrderStep {
  step: number;
  phase: string;
  title: string;
  description: string;
  safety_note: string | null;
  expected_duration_minutes: number;
  checked: boolean;
  actual_notes: string;
}

export interface SavedWorkOrder {
  id: string;
  equipment_id: string;
  query_text: string;
  risk_level: string | null;
  wo_type: string;
  description: string;
  estimated_duration_hours: number;
  required_technicians: number;
  status: OpsStatus;
  steps: SavedWorkOrderStep[];
  spare_parts: string[];
  safety_precautions: string[];
  required_permits: string[];
  solution_worked: boolean | null;
  is_partial?: boolean | null;
  extra_steps_taken: string | null;
  outcome_notes: string | null;
  completed_by: string | null;
  actual_duration_hours: number | null;
  completed_at: string | null;
  created_at: string;
}

// ─── Knowledge Graph ──────────────────────────────────────────────────────────

export interface GraphNode {
  id: string;
  name: string;
  type: string;
  val: number;
  x?: number;
  y?: number;
}

export interface GraphLink {
  source: string;
  target: string;
  label: string;
}

export interface GraphData {
  nodes: GraphNode[];
  links: GraphLink[];
}

// ─── Documents ────────────────────────────────────────────────────────────────

export interface Document {
  id: string;
  name: string;
  type: string;
  equipment_ids: string[];
  status: "processed" | "processing" | "failed";
  date: string;
}

export interface DocumentEntities {
  equipment_ids: string[];
  incident_ids: string[];
  people: string[];
  regulations: string[];
  symptoms: string[];
  measurements: string[];
  document_type: string;
  summary: string;
}

// ─── AI Document Generation ───────────────────────────────────────────────────

export type DocumentCreateType =
  | "maintenance_record"
  | "inspection_report"
  | "operating_instruction"
  | "incident_report";

export interface GeneratedDoc {
  title: string;
  doc_type: DocumentCreateType;
  sections: Record<string, string>;
  entities: DocumentEntities;
  ai_generated?: boolean;
}

export interface DocumentDetail extends Document {
  entities: DocumentEntities | null;
  sections: Record<string, string> | null;
  char_count?: number;
  current_step?: string;
  pipeline_steps?: Record<string, "pending" | "done">;
  error?: string | null;
  mandatory_requirements?: string[];
  key_warnings?: string[];
  summary?: string;
  entities_pending_review?: boolean;
  pending_review_note?: string | null;
  open_findings?: { id: string; description: string; priority: string; due?: string }[];
  inspector?: string;
}
