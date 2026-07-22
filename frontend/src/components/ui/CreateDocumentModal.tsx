/**
 * CreateDocumentModal — AI-assisted document authoring.
 *
 * Three-step flow:
 *  1. Choose document type (6 types).
 *  2. Provide equipment + context description + optional extra fields.
 *  3. Stream AI draft → review & edit each section → save to knowledge base.
 */
"use client";

import { useState, useRef, useCallback } from "react";
import { listEquipment, generateDocument, saveGeneratedDocument } from "@/lib/api";
import type { Equipment, GeneratedDoc, DocumentCreateType } from "@/lib/types";
import {
  X, Wrench, ShieldCheck, ClipboardList, BookOpen, FolderOpen,
  AlertTriangle, Sparkles, Loader2, CheckCircle2, ChevronRight,
  ChevronLeft, Save, RotateCcw,
} from "lucide-react";
import clsx from "clsx";
import { toast } from "sonner";

// ── Document type definitions ─────────────────────────────────────────────────

interface DocTypeDef {
  type: DocumentCreateType;
  label: string;
  description: string;
  icon: React.ReactNode;
  color: string;
  extraFields: Array<{ key: string; label: string; placeholder: string }>;
  sectionLabels: Record<string, string>;
}

const DOC_TYPES: DocTypeDef[] = [
  {
    type: "maintenance_record",
    label: "Maintenance Record",
    description: "Document work performed, findings, and next actions",
    icon: <Wrench size={20} />,
    color: "text-amber-400 bg-amber-500/10 border-amber-500/30",
    extraFields: [
      { key: "technician", label: "Technician / Lead", placeholder: "e.g. Rajesh Kumar" },
      { key: "work_type", label: "Work Type", placeholder: "Preventive / Corrective / Emergency" },
      { key: "permit_number", label: "Permit Number", placeholder: "e.g. PTW-2026-0721" },
    ],
    sectionLabels: {
      equipment_summary: "Equipment Summary",
      work_performed: "Work Performed",
      findings: "Findings",
      measurements_before_after: "Measurements (Before / After)",
      spare_parts_used: "Spare Parts Used",
      recommendations: "Recommendations",
      next_maintenance_due: "Next Maintenance Due",
    },
  },
  {
    type: "safety_procedure",
    label: "Safety Procedure",
    description: "Hazard controls, PPE requirements, step-by-step safe work",
    icon: <ShieldCheck size={20} />,
    color: "text-red-400 bg-red-500/10 border-red-500/30",
    extraFields: [
      { key: "revision", label: "Revision", placeholder: "e.g. Rev. 02" },
      { key: "approved_by", label: "Approved By", placeholder: "e.g. Safety Officer" },
    ],
    sectionLabels: {
      scope_and_purpose: "Scope & Purpose",
      prerequisites_and_permits: "Prerequisites & Permits Required",
      ppe_requirements: "PPE Requirements",
      hazard_identification_and_controls: "Hazard Identification & Controls",
      step_by_step_procedure: "Step-by-Step Procedure",
      emergency_actions: "Emergency Actions",
      regulatory_references: "Regulatory References",
    },
  },
  {
    type: "inspection_report",
    label: "Inspection Report",
    description: "Structured findings, pass/fail items, corrective actions",
    icon: <ClipboardList size={20} />,
    color: "text-blue-400 bg-blue-500/10 border-blue-500/30",
    extraFields: [
      { key: "inspector_name", label: "Inspector", placeholder: "e.g. Amit Shah" },
      { key: "inspection_type", label: "Inspection Type", placeholder: "Routine / Statutory / Detailed" },
    ],
    sectionLabels: {
      inspection_summary: "Inspection Summary",
      scope_and_methodology: "Scope & Methodology",
      inspection_findings: "Inspection Findings",
      defects_found: "Defects Found",
      pass_fail_checklist: "Pass / Fail Checklist",
      corrective_actions_required: "Corrective Actions Required",
      next_inspection_due: "Next Inspection Due",
    },
  },
  {
    type: "operating_instruction",
    label: "Operating Instruction",
    description: "Startup, normal ops, shutdown, troubleshooting guide",
    icon: <BookOpen size={20} />,
    color: "text-emerald-400 bg-emerald-500/10 border-emerald-500/30",
    extraFields: [
      { key: "revision", label: "Revision", placeholder: "e.g. Rev. 01" },
      { key: "unit_section", label: "Unit / Section", placeholder: "e.g. CDU — Unit 4" },
    ],
    sectionLabels: {
      purpose_and_applicability: "Purpose & Applicability",
      normal_operating_parameters: "Normal Operating Parameters",
      startup_procedure: "Startup Procedure",
      normal_operation_guidelines: "Normal Operation Guidelines",
      shutdown_procedure: "Shutdown Procedure",
      troubleshooting_guide: "Troubleshooting Guide",
      safety_interlocks_and_alarms: "Safety Interlocks & Alarms",
    },
  },
  {
    type: "project_file",
    label: "Project File",
    description: "Scope, team, timeline, risk register, referenced docs",
    icon: <FolderOpen size={20} />,
    color: "text-purple-400 bg-purple-500/10 border-purple-500/30",
    extraFields: [
      { key: "project_number", label: "Project Number", placeholder: "e.g. PROJ-2026-042" },
      { key: "project_manager", label: "Project Manager", placeholder: "e.g. Priya Nair" },
    ],
    sectionLabels: {
      project_overview: "Project Overview",
      team_and_responsibilities: "Team & Responsibilities",
      equipment_in_scope: "Equipment in Scope",
      project_timeline: "Project Timeline",
      technical_requirements: "Technical Requirements",
      risk_register: "Risk Register",
      referenced_documents: "Referenced Documents",
    },
  },
  {
    type: "incident_report",
    label: "Incident Report",
    description: "RCA, timeline, contributing factors, corrective actions",
    icon: <AlertTriangle size={20} />,
    color: "text-orange-400 bg-orange-500/10 border-orange-500/30",
    extraFields: [
      { key: "incident_id", label: "Incident ID", placeholder: "e.g. INC-2026-007" },
      { key: "severity", label: "Severity", placeholder: "Critical / High / Medium / Low" },
    ],
    sectionLabels: {
      incident_summary: "Incident Summary",
      chronological_timeline: "Chronological Timeline",
      root_cause_analysis: "Root Cause Analysis",
      contributing_factors: "Contributing Factors",
      immediate_actions_taken: "Immediate Actions Taken",
      permanent_corrective_actions: "Permanent Corrective Actions",
      lessons_learned: "Lessons Learned",
    },
  },
];

// ── Props ─────────────────────────────────────────────────────────────────────

interface Props {
  onClose: () => void;
  onSaved: () => void;
}

// ── Main component ────────────────────────────────────────────────────────────

export function CreateDocumentModal({ onClose, onSaved }: Props) {
  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [selectedType, setSelectedType] = useState<DocTypeDef | null>(null);
  const [equipmentId, setEquipmentId] = useState("");
  const [description, setDescription] = useState("");
  const [extraFields, setExtraFields] = useState<Record<string, string>>({});
  const [equipment, setEquipment] = useState<Equipment[]>([]);
  const [eqLoaded, setEqLoaded] = useState(false);

  // Step 3 — generation state
  const [genStatus, setGenStatus] = useState<"idle" | "context" | "generating" | "done" | "error">("idle");
  const [genMessage, setGenMessage] = useState("");
  const [genDoc, setGenDoc] = useState<GeneratedDoc | null>(null);
  const [editedSections, setEditedSections] = useState<Record<string, string>>({});
  const [editedTitle, setEditedTitle] = useState("");
  const [saving, setSaving] = useState(false);
  const abortRef = useRef(false);

  const loadEquipment = useCallback(async () => {
    if (eqLoaded) return;
    try {
      const eq = await listEquipment();
      setEquipment(eq);
      setEqLoaded(true);
    } catch {
      // ignore — equipment select still works with manual input
    }
  }, [eqLoaded]);

  // ── Step navigation ─────────────────────────────────────────────────────────

  const goToStep2 = (type: DocTypeDef) => {
    setSelectedType(type);
    setExtraFields({});
    loadEquipment();
    setStep(2);
  };

  const goToStep3 = async () => {
    if (!selectedType || !equipmentId.trim() || !description.trim()) return;
    setStep(3);
    setGenStatus("context");
    setGenMessage("Loading equipment context…");
    setGenDoc(null);
    abortRef.current = false;

    try {
      for await (const event of generateDocument(
        selectedType.type,
        equipmentId.trim(),
        description.trim(),
        extraFields,
      )) {
        if (abortRef.current) break;
        if (event.step === "context") {
          setGenStatus("context");
          setGenMessage(event.message ?? "Loading context…");
        } else if (event.step === "generating") {
          setGenStatus("generating");
          setGenMessage(event.message ?? "AI is writing…");
        } else if (event.step === "complete" && event.document) {
          setGenDoc(event.document);
          setEditedSections({ ...event.document.sections });
          setEditedTitle(event.document.title);
          setGenStatus("done");
        }
      }
    } catch {
      setGenStatus("error");
      setGenMessage("Generation failed. Check your API key or try again.");
    }
  };

  const regenerate = () => {
    abortRef.current = true;
    setTimeout(() => goToStep3(), 100);
  };

  const handleSave = async () => {
    if (!genDoc || !selectedType) return;
    setSaving(true);
    try {
      await saveGeneratedDocument({
        doc_type: selectedType.type,
        equipment_id: equipmentId.trim(),
        title: editedTitle,
        sections: editedSections,
        entities: {
          ...genDoc.entities,
          document_type: selectedType.type,
        },
      });
      toast.success(`${editedTitle} saved to knowledge base`);
      onSaved();
      onClose();
    } catch {
      toast.error("Failed to save document");
    } finally {
      setSaving(false);
    }
  };

  // ── Render ──────────────────────────────────────────────────────────────────

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
      <div className="w-full max-w-2xl max-h-[90vh] flex flex-col bg-[#141414] border border-[#2a2a2a] rounded-2xl shadow-2xl overflow-hidden">

        {/* Header */}
        <div className="flex items-center gap-3 px-5 py-4 border-b border-[#2a2a2a] flex-shrink-0">
          <Sparkles size={18} className="text-amber-400" />
          <div className="flex-1 min-w-0">
            <p className="text-sm font-semibold text-[#f9f9f9]">
              {step === 1 ? "Create Document with AI" :
               step === 2 ? `New ${selectedType?.label}` :
               genStatus === "done" ? "Review & Save" : "Generating…"}
            </p>
            <p className="text-xs text-[#6b7280] mt-0.5">
              Step {step} of 3 — {step === 1 ? "Choose type" : step === 2 ? "Describe context" : "AI draft ready"}
            </p>
          </div>
          {/* Step dots */}
          <div className="flex gap-1.5 mr-2">
            {[1, 2, 3].map(s => (
              <div key={s} className={clsx("h-1.5 rounded-full transition-all", s === step ? "w-5 bg-amber-400" : s < step ? "w-3 bg-emerald-500" : "w-3 bg-[#333]")} />
            ))}
          </div>
          <button onClick={onClose} className="p-1 rounded-lg hover:bg-[#2a2a2a] text-[#6b7280] hover:text-[#f9f9f9] transition-colors flex-shrink-0">
            <X size={16} />
          </button>
        </div>

        {/* Step 1 — Type Selection */}
        {step === 1 && (
          <div className="flex-1 overflow-y-auto p-5">
            <p className="text-xs text-[#6b7280] mb-4">What type of document do you want to create?</p>
            <div className="grid grid-cols-2 gap-3">
              {DOC_TYPES.map(dt => (
                <button
                  key={dt.type}
                  onClick={() => goToStep2(dt)}
                  className="flex items-start gap-3 p-4 text-left bg-[#1f1f1f] border border-[#2a2a2a] rounded-xl hover:border-amber-500/40 hover:bg-[#242424] transition-all group"
                >
                  <span className={clsx("p-2 rounded-lg border flex-shrink-0 group-hover:scale-105 transition-transform", dt.color)}>
                    {dt.icon}
                  </span>
                  <div className="min-w-0">
                    <p className="text-sm font-semibold text-[#f9f9f9] leading-tight">{dt.label}</p>
                    <p className="text-xs text-[#6b7280] mt-1 leading-snug">{dt.description}</p>
                  </div>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Step 2 — Context form */}
        {step === 2 && selectedType && (
          <div className="flex-1 overflow-y-auto p-5 space-y-4">
            {/* Equipment selector */}
            <div>
              <label className="text-xs font-medium text-[#a0a0a0] mb-1.5 block">Equipment ID *</label>
              {equipment.length > 0 ? (
                <select
                  value={equipmentId}
                  onChange={e => setEquipmentId(e.target.value)}
                  className="w-full bg-[#1f1f1f] border border-[#2a2a2a] rounded-lg px-3 py-2 text-sm text-[#f9f9f9] focus:outline-none focus:border-amber-500/60 transition-colors"
                >
                  <option value="">Select equipment…</option>
                  {equipment.map(eq => (
                    <option key={eq.id} value={eq.id}>{eq.id} — {eq.name}</option>
                  ))}
                </select>
              ) : (
                <input
                  type="text"
                  value={equipmentId}
                  onChange={e => setEquipmentId(e.target.value)}
                  placeholder="e.g. P-101"
                  className="w-full bg-[#1f1f1f] border border-[#2a2a2a] rounded-lg px-3 py-2 text-sm text-[#f9f9f9] placeholder:text-[#4b5563] focus:outline-none focus:border-amber-500/60 transition-colors"
                />
              )}
            </div>

            {/* Description */}
            <div>
              <label className="text-xs font-medium text-[#a0a0a0] mb-1.5 block">
                Context / Description *
                <span className="text-[#4b5563] font-normal ml-1">— describe what happened or what you need</span>
              </label>
              <textarea
                value={description}
                onChange={e => setDescription(e.target.value)}
                rows={4}
                placeholder={
                  selectedType.type === "maintenance_record"
                    ? "e.g. Replaced drive-end bearing on P-101 after vibration alarm at 7.2 mm/s. Found significant wear at inner race."
                    : selectedType.type === "safety_procedure"
                    ? "e.g. Safe procedure for bearing replacement on centrifugal pumps in CDU. Includes isolation, lubrication, and restart."
                    : selectedType.type === "inspection_report"
                    ? "e.g. Statutory annual inspection of P-101. Check bearing, seal, coupling, foundation, and instrumentation."
                    : selectedType.type === "incident_report"
                    ? "e.g. P-101 vibration reached 9.2 mm/s and pump tripped on high-high. Bearing failure confirmed on disassembly."
                    : "Describe the context for this document…"
                }
                className="w-full bg-[#1f1f1f] border border-[#2a2a2a] rounded-lg px-3 py-2 text-sm text-[#f9f9f9] placeholder:text-[#4b5563] focus:outline-none focus:border-amber-500/60 transition-colors resize-none"
              />
            </div>

            {/* Type-specific extra fields */}
            {selectedType.extraFields.length > 0 && (
              <div className="grid grid-cols-2 gap-3">
                {selectedType.extraFields.map(f => (
                  <div key={f.key}>
                    <label className="text-xs font-medium text-[#a0a0a0] mb-1.5 block">{f.label}</label>
                    <input
                      type="text"
                      value={extraFields[f.key] ?? ""}
                      onChange={e => setExtraFields(prev => ({ ...prev, [f.key]: e.target.value }))}
                      placeholder={f.placeholder}
                      className="w-full bg-[#1f1f1f] border border-[#2a2a2a] rounded-lg px-3 py-2 text-sm text-[#f9f9f9] placeholder:text-[#4b5563] focus:outline-none focus:border-amber-500/60 transition-colors"
                    />
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Step 3 — AI Draft */}
        {step === 3 && (
          <div className="flex-1 overflow-y-auto p-5">
            {/* Generating state */}
            {genStatus !== "done" && genStatus !== "error" && (
              <div className="flex flex-col items-center justify-center py-16 gap-4">
                <div className="relative">
                  <div className="w-16 h-16 rounded-2xl bg-amber-500/10 border border-amber-500/30 flex items-center justify-center">
                    <Sparkles size={28} className="text-amber-400" />
                  </div>
                  <div className="absolute -bottom-1 -right-1 w-6 h-6 bg-[#141414] rounded-full flex items-center justify-center border border-[#2a2a2a]">
                    <Loader2 size={14} className="text-amber-400 animate-spin" />
                  </div>
                </div>
                <div className="text-center">
                  <p className="text-sm font-semibold text-[#f9f9f9]">
                    {genStatus === "context" ? "Loading context…" : "Writing document…"}
                  </p>
                  <p className="text-xs text-[#6b7280] mt-1">{genMessage}</p>
                </div>
                <div className="flex gap-2">
                  {["context", "generating", "processing"].map((s, i) => (
                    <div key={s} className={clsx(
                      "h-1 rounded-full transition-all duration-500",
                      (genStatus === "context" && i === 0) ||
                      (genStatus === "generating" && i <= 1)
                        ? "w-8 bg-amber-400"
                        : "w-4 bg-[#333]",
                    )} />
                  ))}
                </div>
              </div>
            )}

            {/* Error state */}
            {genStatus === "error" && (
              <div className="flex flex-col items-center justify-center py-16 gap-3">
                <div className="w-14 h-14 rounded-2xl bg-red-500/10 border border-red-500/30 flex items-center justify-center">
                  <AlertTriangle size={24} className="text-red-400" />
                </div>
                <p className="text-sm font-semibold text-red-400">Generation failed</p>
                <p className="text-xs text-[#6b7280] text-center max-w-xs">{genMessage}</p>
                <button onClick={regenerate} className="flex items-center gap-2 px-4 py-2 mt-2 bg-[#2a2a2a] hover:bg-[#333] text-[#a0a0a0] rounded-lg text-sm transition-colors border border-[#333]">
                  <RotateCcw size={13} /> Try again
                </button>
              </div>
            )}

            {/* Done — review sections */}
            {genStatus === "done" && genDoc && selectedType && (
              <div className="space-y-4">
                {/* Title */}
                <div>
                  <div className="flex items-center gap-2 mb-1.5">
                    <CheckCircle2 size={14} className="text-emerald-400" />
                    <label className="text-xs font-semibold text-emerald-400">Document Title</label>
                  </div>
                  <input
                    type="text"
                    value={editedTitle}
                    onChange={e => setEditedTitle(e.target.value)}
                    className="w-full bg-[#1f1f1f] border border-emerald-500/30 rounded-lg px-3 py-2 text-sm font-semibold text-[#f9f9f9] focus:outline-none focus:border-emerald-500/60 transition-colors"
                  />
                </div>

                {/* Entities row */}
                <div className="flex flex-wrap gap-2 p-3 bg-[#1a1a1a] rounded-lg border border-[#2a2a2a]">
                  {genDoc.entities.equipment_ids?.map(e => (
                    <span key={e} className="text-xs font-mono text-amber-400 bg-amber-500/10 px-2 py-0.5 rounded">{e}</span>
                  ))}
                  {genDoc.entities.people?.map(p => (
                    <span key={p} className="text-xs text-blue-400 bg-blue-500/10 px-2 py-0.5 rounded">{p}</span>
                  ))}
                  {genDoc.entities.regulations?.map(r => (
                    <span key={r} className="text-xs text-purple-400 bg-purple-500/10 px-2 py-0.5 rounded">{r}</span>
                  ))}
                </div>

                {/* Sections */}
                <p className="text-xs text-[#6b7280]">Review and edit each section before saving. All sections become searchable in the knowledge base.</p>
                {Object.entries(editedSections).map(([key, value]) => (
                  <div key={key}>
                    <label className="text-xs font-semibold text-[#a0a0a0] mb-1.5 block">
                      {selectedType.sectionLabels[key] ?? key.replace(/_/g, " ")}
                    </label>
                    <textarea
                      value={value}
                      onChange={e => setEditedSections(prev => ({ ...prev, [key]: e.target.value }))}
                      rows={Math.max(3, Math.ceil(value.length / 80))}
                      className="w-full bg-[#1f1f1f] border border-[#2a2a2a] rounded-lg px-3 py-2 text-sm text-[#f9f9f9] focus:outline-none focus:border-amber-500/40 transition-colors resize-none leading-relaxed"
                    />
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Footer */}
        <div className="flex items-center gap-2 px-5 py-3 border-t border-[#2a2a2a] flex-shrink-0 bg-[#141414]">
          {step > 1 && genStatus !== "context" && genStatus !== "generating" && (
            <button
              onClick={() => { abortRef.current = true; setStep(step === 3 ? 2 : 1 as 1 | 2 | 3); setGenStatus("idle"); setGenDoc(null); }}
              className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-[#6b7280] hover:text-[#a0a0a0] hover:bg-[#2a2a2a] rounded-lg transition-colors"
            >
              <ChevronLeft size={15} /> Back
            </button>
          )}
          <div className="flex-1" />

          {step === 2 && (
            <button
              onClick={goToStep3}
              disabled={!equipmentId.trim() || !description.trim()}
              className="flex items-center gap-2 px-4 py-2 bg-amber-500/20 hover:bg-amber-500/30 disabled:opacity-40 disabled:cursor-not-allowed text-amber-400 rounded-lg text-sm font-medium border border-amber-500/40 transition-colors"
            >
              <Sparkles size={14} /> Generate with AI <ChevronRight size={14} />
            </button>
          )}

          {step === 3 && genStatus === "done" && (
            <>
              <button
                onClick={regenerate}
                className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-[#6b7280] hover:text-[#a0a0a0] hover:bg-[#2a2a2a] rounded-lg transition-colors border border-[#2a2a2a]"
              >
                <RotateCcw size={13} /> Regenerate
              </button>
              <button
                onClick={handleSave}
                disabled={saving || !editedTitle.trim()}
                className="flex items-center gap-2 px-4 py-2 bg-emerald-500/20 hover:bg-emerald-500/30 disabled:opacity-40 disabled:cursor-not-allowed text-emerald-400 rounded-lg text-sm font-medium border border-emerald-500/40 transition-colors"
              >
                {saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
                Save to Knowledge Base
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
