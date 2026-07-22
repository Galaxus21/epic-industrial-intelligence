/**
 * AI Operations Brain — Forms Hub
 * Two-tab layout:
 *   Tab 1 "All Forms" — Browse every form category in the system.
 *   Tab 2 "Smart Generator" — AI-powered form builder (existing functionality).
 *
 * All quick-capture form submissions now write to BOTH legacy tables AND the
 * workflow tables (IncidentReport, ManagedWorkOrder) so data always appears in
 * the respective workflow UI pages.
 */
"use client";

import { useState, useEffect, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { generateForm, submitForm, getFormTemplates, listEquipment, uploadFormImage } from "@/lib/api";
import { Badge } from "@/components/ui/Badge";
import {
  FormInput, Loader2, Send, CheckCircle2, AlertTriangle,
  Activity, Gauge, Wrench, FileWarning, PlusCircle, ClipboardList,
  ChevronRight, RotateCcw, Camera, X, ScanSearch, ImageIcon,
  ShieldAlert, BookOpen, ClipboardCheck, GitBranch, FolderKanban,
  Layers, ArrowRight, type LucideIcon,
} from "lucide-react";
import clsx from "clsx";
import type { Equipment } from "@/lib/types";

// ── Types ─────────────────────────────────────────────────────────────────────

type FieldDef = {
  id: string;
  type: string;
  label: string;
  required: boolean;
  placeholder: string;
  default_value: string;
  options: string[];
  unit: string;
  hint: string;
  min: number | null;
  max: number | null;
};

type FormSchema = {
  form_id: string;
  form_type: string;
  title: string;
  description: string;
  equipment_id: string | null;
  fields: FieldDef[];
  submit_action: string;
};

type Template = { id: string; label: string; icon: string; description: string; form_type: string; example_prompt: string };

// ── Template icon map ─────────────────────────────────────────────────────────

const TEMPLATE_ICONS: Record<string, LucideIcon> = {
  activity: Activity,
  gauge: Gauge,
  wrench: Wrench,
  "alert-triangle": FileWarning,
  "plus-circle": PlusCircle,
  "scan-search": ScanSearch,
};

// ── All form categories for the hub ──────────────────────────────────────────

type FormCategory = {
  id: string;
  label: string;
  icon: LucideIcon;
  color: string;
  bg: string;
  border: string;
  description: string;
  tags: string[];
} & (
  | { section: "quick"; prompt: string }
  | { section: "workflow"; href: string }
);

const FORM_CATEGORIES: FormCategory[] = [
  // ── Quick-capture forms (AI generator) ──────────────────────────────────────
  {
    id: "maintenance_record", label: "Maintenance Record",
    icon: Wrench, color: "text-blue-400", bg: "bg-blue-500/10", border: "border-blue-500/20",
    description: "Log vibration checks, lubrication, bearing inspections and sensor readings",
    tags: ["equipment", "inspection", "sensor"],
    section: "quick", prompt: "log a maintenance inspection for {equipment_id}",
  },
  {
    id: "sensor_log", label: "Sensor Log",
    icon: Gauge, color: "text-emerald-400", bg: "bg-emerald-500/10", border: "border-emerald-500/20",
    description: "Manually record all current sensor readings for an equipment unit",
    tags: ["sensor", "readings", "telemetry"],
    section: "quick", prompt: "record today's sensor readings for {equipment_id}",
  },
  {
    id: "incident_report", label: "Incident Report",
    icon: AlertTriangle, color: "text-red-400", bg: "bg-red-500/10", border: "border-red-500/20",
    description: "Report equipment failures, near-misses, or process upsets with severity tracking",
    tags: ["incident", "safety", "failure"],
    section: "quick", prompt: "report an incident on {equipment_id}",
  },
  {
    id: "work_order", label: "Work Order",
    icon: ClipboardList, color: "text-purple-400", bg: "bg-purple-500/10", border: "border-purple-500/20",
    description: "Create corrective, preventive, or emergency maintenance work orders",
    tags: ["maintenance", "repair", "schedule"],
    section: "quick", prompt: "create a corrective work order for {equipment_id}",
  },
  {
    id: "defect_report", label: "Defect Report",
    icon: ScanSearch, color: "text-orange-400", bg: "bg-orange-500/10", border: "border-orange-500/20",
    description: "Document physical defects — corrosion, cracks, leaks — with photo evidence",
    tags: ["defect", "inspection", "damage", "photo"],
    section: "quick", prompt: "report a defect found on {equipment_id}",
  },
  {
    id: "equipment_reg", label: "Equipment Registration",
    icon: PlusCircle, color: "text-amber-400", bg: "bg-amber-500/10", border: "border-amber-500/20",
    description: "Register new equipment in the plant knowledge graph with specs and criticality",
    tags: ["equipment", "registration", "asset"],
    section: "quick", prompt: "register a new pump in the plant",
  },
  // ── Workflow forms (navigate to dedicated page) ───────────────────────────
  {
    id: "ptw", label: "Permit to Work",
    icon: ShieldAlert, color: "text-yellow-400", bg: "bg-yellow-500/10", border: "border-yellow-500/20",
    description: "Full PTW workflow — hot work, confined space, electrical isolation, excavation",
    tags: ["safety", "permit", "approval", "PTW"],
    section: "workflow", href: "/permits",
  },
  {
    id: "safety_procedure", label: "Safety Procedure",
    icon: BookOpen, color: "text-sky-400", bg: "bg-sky-500/10", border: "border-sky-500/20",
    description: "Author SOP, JSA, SWMS, MSDS documents with peer & technical review workflow",
    tags: ["SOP", "JSA", "procedure", "document"],
    section: "workflow", href: "/procedures",
  },
  {
    id: "managed_wo", label: "Managed Work Order",
    icon: Wrench, color: "text-indigo-400", bg: "bg-indigo-500/10", border: "border-indigo-500/20",
    description: "Full approval-chain work orders — submit → approve → execute → verify → close",
    tags: ["approval", "workflow", "two-person"],
    section: "workflow", href: "/managed-work-orders",
  },
  {
    id: "inspection", label: "Quality Inspection",
    icon: ClipboardCheck, color: "text-teal-400", bg: "bg-teal-500/10", border: "border-teal-500/20",
    description: "Equipment, process, HSE, and contractor inspections with CAPA tracking",
    tags: ["HSE", "audit", "CAPA", "checklist"],
    section: "workflow", href: "/inspections",
  },
  {
    id: "rca", label: "Root Cause Analysis",
    icon: GitBranch, color: "text-pink-400", bg: "bg-pink-500/10", border: "border-pink-500/20",
    description: "5-Why and bow-tie RCA for incident investigation and lessons learned",
    tags: ["RCA", "investigation", "5-why"],
    section: "workflow", href: "/rca",
  },
  {
    id: "project", label: "Project & Site Management",
    icon: FolderKanban, color: "text-lime-400", bg: "bg-lime-500/10", border: "border-lime-500/20",
    description: "Manage projects, plants, equipment hierarchy, and team assignments",
    tags: ["project", "plant", "hierarchy"],
    section: "workflow", href: "/projects",
  },
];

// ── Forms Hub ─────────────────────────────────────────────────────────────────

function FormsHub({
  onSelectQuick,
  equipmentId,
}: {
  onSelectQuick: (prompt: string) => void;
  equipmentId: string;
}) {
  const quick    = FORM_CATEGORIES.filter(c => c.section === "quick");
  const workflow = FORM_CATEGORIES.filter(c => c.section === "workflow");

  const categoryCard = (cat: FormCategory) => {
    const Icon = cat.icon;
    const inner = (
      <div className={clsx(
        "group flex flex-col gap-2.5 p-4 rounded-2xl border transition-all duration-150 cursor-pointer h-full",
        cat.bg, cat.border,
        "hover:brightness-125 hover:shadow-md",
      )}>
        <div className="flex items-center justify-between">
          <div className={clsx("p-2 rounded-xl", cat.bg)}>
            <Icon size={18} className={cat.color} />
          </div>
          {"href" in cat
            ? <ArrowRight size={14} className="text-[#4b5563] group-hover:text-[#a0a0a0] transition-colors" />
            : <ChevronRight size={14} className="text-[#4b5563] group-hover:text-[#a0a0a0] transition-colors" />
          }
        </div>
        <div>
          <p className="text-sm font-semibold text-[#f9f9f9] leading-tight">{cat.label}</p>
          <p className="text-[11px] text-[#6b7280] mt-1 leading-relaxed line-clamp-2">{cat.description}</p>
        </div>
        <div className="flex flex-wrap gap-1 mt-auto">
          {cat.tags.slice(0, 3).map(t => (
            <span key={t} className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-[#1a1a1a] text-[#4b5563]">
              {t}
            </span>
          ))}
        </div>
      </div>
    );

    if (cat.section === "workflow") {
      return (
        <Link key={cat.id} href={(cat as { href: string }).href} className="block h-full">
          {inner}
        </Link>
      );
    }
    return (
      <button
        key={cat.id}
        onClick={() => onSelectQuick((cat as { prompt: string }).prompt.replace("{equipment_id}", equipmentId || "the equipment"))}
        className="block text-left h-full w-full"
      >
        {inner}
      </button>
    );
  };

  return (
    <div className="flex-1 overflow-y-auto space-y-8 pb-4">

      {/* Quick Capture */}
      <div>
        <div className="flex items-center gap-2 mb-4">
          <FormInput size={15} className="text-amber-400" />
          <h2 className="text-sm font-semibold text-[#f9f9f9]">Quick Capture</h2>
          <span className="text-[10px] text-[#4b5563] ml-1">AI generates the form instantly</span>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-6 gap-3">
          {quick.map(cat => categoryCard(cat))}
        </div>
      </div>

      {/* Workflow & Approvals */}
      <div>
        <div className="flex items-center gap-2 mb-4">
          <Layers size={15} className="text-sky-400" />
          <h2 className="text-sm font-semibold text-[#f9f9f9]">Workflow & Approvals</h2>
          <span className="text-[10px] text-[#4b5563] ml-1">Full lifecycle with sign-offs</span>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-6 gap-3">
          {workflow.map(cat => categoryCard(cat))}
        </div>
      </div>

      {/* Summary row */}
      <div className="flex flex-wrap gap-4 p-4 bg-[#141414] border border-[#252525] rounded-2xl text-xs text-[#6b7280]">
        <span className="flex items-center gap-1.5"><FormInput size={12} className="text-amber-400" />{quick.length} quick-capture forms</span>
        <span className="flex items-center gap-1.5"><Layers size={12} className="text-sky-400" />{workflow.length} workflow forms</span>
        <span className="flex items-center gap-1.5"><CheckCircle2 size={12} className="text-emerald-400" />All submissions stored in DB + knowledge graph</span>
      </div>

    </div>
  );
}

// ── Image upload field ────────────────────────────────────────────────────────

type UploadedImage = { url: string; name: string; preview: string };

function ImageUploadField({
  value, onChange, hint,
}: {
  value: string;           // JSON array of URLs or empty string
  onChange: (v: string) => void;
  hint: string;
}) {
  const [images, setImages] = useState<UploadedImage[]>(() => {
    try { return JSON.parse(value) as UploadedImage[]; } catch { return []; }
  });
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");

  const sync = (updated: UploadedImage[]) => {
    setImages(updated);
    onChange(JSON.stringify(updated));
  };

  const handleFiles = async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    setUploading(true);
    setError("");
    const added: UploadedImage[] = [];
    for (const file of Array.from(files)) {
      try {
        const preview = URL.createObjectURL(file);
        const res = await uploadFormImage(file);
        added.push({ url: res.url, name: file.name, preview });
      } catch {
        setError(`Failed to upload ${file.name}`);
      }
    }
    sync([...images, ...added]);
    setUploading(false);
  };

  const remove = (idx: number) => sync(images.filter((_, i) => i !== idx));

  return (
    <div>
      {/* Drop zone */}
      <label
        className={clsx(
          "flex flex-col items-center justify-center gap-2 p-5 border-2 border-dashed rounded-xl cursor-pointer transition-colors",
          uploading
            ? "border-amber-500/40 bg-amber-500/5"
            : "border-[#252525] hover:border-amber-500/30 hover:bg-[#141414]"
        )}
      >
        <input
          type="file"
          accept="image/*"
          multiple
          className="hidden"
          onChange={e => handleFiles(e.target.files)}
          disabled={uploading}
        />
        {uploading
          ? <Loader2 size={20} className="text-amber-400 animate-spin" />
          : <Camera size={20} className="text-[#4b5563]" />
        }
        <p className="text-xs text-[#6b7280] text-center">
          {uploading ? "Uploading…" : "Click or drag photos here"}
        </p>
        <p className="text-[10px] text-[#333]">JPG · PNG · WEBP · up to 20 MB each</p>
      </label>

      {hint && <p className="text-[10px] text-[#4b5563] mt-1">{hint}</p>}
      {error && <p className="text-[10px] text-red-400 mt-1">{error}</p>}

      {/* Thumbnails */}
      {images.length > 0 && (
        <div className="flex flex-wrap gap-2 mt-3">
          {images.map((img, i) => (
            <div key={i} className="relative group">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={img.preview || img.url}
                alt={img.name}
                className="w-20 h-20 object-cover rounded-xl border border-[#252525]"
              />
              <button
                type="button"
                onClick={() => remove(i)}
                className="absolute -top-1.5 -right-1.5 w-5 h-5 rounded-full bg-red-500 text-white flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
              >
                <X size={10} />
              </button>
              <div className="absolute bottom-0 left-0 right-0 bg-black/60 rounded-b-xl px-1 py-0.5">
                <p className="text-[8px] text-white truncate">{img.name}</p>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Dynamic field renderer ─────────────────────────────────────────────────────

function FormField({
  field, value, onChange,
}: {
  field: FieldDef;
  value: string;
  onChange: (v: string) => void;
}) {
  const baseInput = "w-full bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl px-3 py-2 text-sm text-[#f9f9f9] placeholder-[#4b5563] focus:outline-none focus:border-amber-500/50 transition-colors";

  return (
    <div>
      <div className="flex items-baseline gap-1 mb-1">
        <label className="text-xs font-medium text-[#a0a0a0]">{field.label}</label>
        {field.unit && <span className="text-[10px] text-[#4b5563]">({field.unit})</span>}
        {field.required && <span className="text-[10px] text-red-400 ml-0.5">*</span>}
      </div>

      {field.type === "image_upload" ? (
        <ImageUploadField value={value} onChange={onChange} hint={field.hint} />
      ) : field.type === "textarea" ? (
        <textarea
          value={value}
          onChange={e => onChange(e.target.value)}
          placeholder={field.placeholder}
          rows={3}
          className={clsx(baseInput, "resize-none")}
        />
      ) : field.type === "select" ? (
        <select
          value={value}
          onChange={e => onChange(e.target.value)}
          className={clsx(baseInput, "appearance-none")}
        >
          <option value="">Select…</option>
          {field.options.map(opt => (
            <option key={opt} value={opt}>{opt}</option>
          ))}
        </select>
      ) : field.type === "checkbox" ? (
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={value === "true"}
            onChange={e => onChange(e.target.checked ? "true" : "false")}
            className="w-4 h-4 rounded border-[#2a2a2a] bg-[#1a1a1a] accent-amber-500"
          />
          <span className="text-sm text-[#a0a0a0]">{field.placeholder || field.label}</span>
        </label>
      ) : (
        <input
          type={field.type === "number" ? "number" : field.type === "date" ? "date" : "text"}
          value={value}
          onChange={e => onChange(e.target.value)}
          placeholder={field.placeholder}
          min={field.min ?? undefined}
          max={field.max ?? undefined}
          step={field.type === "number" ? "any" : undefined}
          className={baseInput}
        />
      )}

      {field.hint && (
        <p className="text-[10px] text-[#4b5563] mt-0.5">{field.hint}</p>
      )}
    </div>
  );
}

// ── Form renderer ─────────────────────────────────────────────────────────────

type SubmitResult = { id: string; message: string; updated_sensors?: string[] };

function DynamicForm({
  schema, onReset,
}: {
  schema: FormSchema;
  onReset: () => void;
}) {
  const [values, setValues] = useState<Record<string, string>>(() => {
    const init: Record<string, string> = {};
    schema.fields.forEach(f => { init[f.id] = f.default_value || ""; });
    return init;
  });
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState<SubmitResult | null>(null);
  const [error, setError] = useState("");

  const handleSubmit = async () => {
    // Check required fields (skip image_upload — checked separately)
    const missing = schema.fields.filter(f => f.required && f.type !== "image_upload" && !values[f.id]?.trim());
    const missingImages = schema.fields.filter(f => f.required && f.type === "image_upload" && !values[f.id]);
    if (missing.length > 0 || missingImages.length > 0) {
      const names = [...missing, ...missingImages].map(f => f.label);
      setError(`Please fill in: ${names.join(", ")}`);
      return;
    }
    setError("");
    setSubmitting(true);
    try {
      const res = await submitForm({
        form_type: schema.submit_action,
        equipment_id: schema.equipment_id ?? undefined,
        field_values: values,
      }) as SubmitResult;
      setSubmitted(res);
    } catch {
      setError("Submission failed. Please try again.");
    } finally {
      setSubmitting(false);
    }
  };

  if (submitted) {
    const isSensorUpdate = schema.submit_action === "sensor_log" || schema.submit_action === "maintenance_record";
    const updatedSensors = submitted.updated_sensors ?? [];
    return (
      <div className="flex flex-col items-center justify-center py-16 gap-4 text-center">
        <CheckCircle2 size={40} className="text-emerald-400" />
        <div>
          <p className="text-sm font-semibold text-[#f9f9f9]">{submitted.message}</p>
          <p className="text-xs text-[#6b7280] mt-0.5">Record ID: <span className="font-mono text-amber-400">{submitted.id}</span></p>
        </div>

        {isSensorUpdate && updatedSensors.length > 0 && (
          <div className="bg-emerald-500/5 border border-emerald-500/20 rounded-xl px-5 py-3 text-left max-w-xs">
            <p className="text-xs font-semibold text-emerald-400 mb-2 flex items-center gap-1.5">
              <Activity size={12} /> Live sensor readings updated
            </p>
            <div className="flex flex-wrap gap-1.5">
              {updatedSensors.map(s => (
                <span key={s} className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-300">
                  {s.replace(/_/g, "\u00a0")}
                </span>
              ))}
            </div>
            <p className="text-[10px] text-[#4b5563] mt-2">
              The AI chat sensor strip and equipment detail page now reflect these values.
            </p>
          </div>
        )}

        <button
          onClick={onReset}
          className="flex items-center gap-2 text-xs px-4 py-2 rounded-xl bg-[#1a1a1a] border border-[#252525] text-[#a0a0a0] hover:border-amber-500/30 hover:text-amber-400 transition-colors"
        >
          <RotateCcw size={12} /> Create another form
        </button>
      </div>
    );
  }

  return (
    <div>
      {/* Form header */}
      <div className="flex items-start justify-between mb-5">
        <div>
          <h2 className="text-base font-bold text-[#f9f9f9]">{schema.title}</h2>
          <p className="text-xs text-[#6b7280] mt-0.5">{schema.description}</p>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          <Badge variant="muted">{schema.form_type.replace("_", " ")}</Badge>
          {schema.equipment_id && (
            <span className="text-[10px] font-mono text-amber-400 bg-amber-500/10 px-2 py-0.5 rounded">
              {schema.equipment_id}
            </span>
          )}
        </div>
      </div>

      {/* Fields grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-5">
        {schema.fields.map(field => (
          <div
            key={field.id}
            className={clsx(
              field.type === "image_upload" ||
              field.type === "textarea" || field.id === "findings" || field.id === "symptom" ||
              field.id === "description" || field.id === "action_taken"
                ? "md:col-span-2"
                : ""
            )}
          >
            <FormField
              field={field}
              value={values[field.id] ?? ""}
              onChange={v => setValues(prev => ({ ...prev, [field.id]: v }))}
            />
          </div>
        ))}
      </div>

      {error && (
        <div className="flex items-center gap-2 p-3 bg-red-500/10 border border-red-500/30 rounded-xl mb-4 text-xs text-red-400">
          <AlertTriangle size={12} /> {error}
        </div>
      )}

      <div className="flex justify-end">
        <button
          onClick={handleSubmit}
          disabled={submitting}
          className={clsx(
            "flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold transition-all",
            submitting
              ? "bg-[#2a2a2a] text-[#4b5563] cursor-not-allowed"
              : "bg-amber-500 hover:bg-amber-400 text-black"
          )}
        >
          {submitting ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}
          {submitting ? "Saving…" : "Submit Record"}
        </button>
      </div>
    </div>
  );
}

// ── Main page (inner) ─────────────────────────────────────────────────────────

function FormsPageInner() {
  const searchParams = useSearchParams();
  const presetEquipment = searchParams.get("equipment") ?? "";
  const presetTab = searchParams.get("tab") as "hub" | "generator" | null;

  const [activeTab, setActiveTab] = useState<"hub" | "generator">(presetTab ?? "hub");
  const [templates, setTemplates] = useState<Template[]>([]);
  const [equipmentList, setEquipmentList] = useState<Equipment[]>([]);
  const [equipmentId, setEquipmentId] = useState(presetEquipment);
  const [description, setDescription] = useState("");
  const [generating, setGenerating] = useState(false);
  const [schema, setSchema] = useState<FormSchema | null>(null);
  const [genError, setGenError] = useState("");

  useEffect(() => {
    getFormTemplates().then(t => setTemplates(t as Template[])).catch(() => {});
    listEquipment()
      .then(list => setEquipmentList(list.filter(e => !e._discovered)))
      .catch(() => {});
  }, []);

  const handleGenerate = async () => {
    if (!description.trim() || generating) return;
    setGenerating(true);
    setSchema(null);
    setGenError("");
    try {
      const result = await generateForm({
        description,
        equipment_id: equipmentId || undefined,
      }) as FormSchema;
      setSchema(result);
    } catch {
      setGenError("Form generation failed. Please try again.");
    } finally {
      setGenerating(false);
    }
  };

  const applyTemplate = (tmpl: Template) => {
    const prompt = tmpl.example_prompt.replace("{equipment_id}", equipmentId || "the equipment");
    setDescription(prompt);
    setSchema(null);
  };

  /** Called from the hub when a quick-capture category card is clicked. */
  const openGenerator = (prompt: string) => {
    setDescription(prompt);
    setSchema(null);
    setGenError("");
    setActiveTab("generator");
  };

  return (
    <div className="p-6 h-full flex flex-col">
      {/* Page header */}
      <div className="flex items-center justify-between mb-4 flex-shrink-0">
        <div className="flex items-center gap-3">
          <FormInput size={20} className="text-amber-400" />
          <div>
            <h1 className="text-xl font-bold text-[#f9f9f9]">Forms</h1>
            <p className="text-xs text-[#6b7280] mt-0.5">
              All form types and workflow entries in one place.
            </p>
          </div>
        </div>
      </div>

      {/* Tab switcher */}
      <div className="flex gap-1 mb-5 flex-shrink-0 bg-[#141414] border border-[#252525] rounded-xl p-1 w-fit">
        {(["hub", "generator"] as const).map(tab => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={clsx(
              "px-4 py-1.5 rounded-lg text-xs font-semibold transition-colors",
              activeTab === tab
                ? "bg-amber-500 text-black"
                : "text-[#6b7280] hover:text-[#a0a0a0]",
            )}
          >
            {tab === "hub" ? "All Forms" : "Smart Generator"}
          </button>
        ))}
      </div>

      {/* ── Hub tab ──────────────────────────────────────────────────── */}
      {activeTab === "hub" && (
        <FormsHub onSelectQuick={openGenerator} equipmentId={equipmentId} />
      )}

      {/* ── Smart Generator tab ──────────────────────────────────────── */}
      {activeTab === "generator" && (
        <div className="flex-1 min-h-0 grid grid-cols-1 lg:grid-cols-[340px_1fr] gap-5">

          {/* Left pane: describe */}
          <div className="flex flex-col gap-4">

            {/* Equipment selector */}
            <div className="bg-[#141414] border border-[#252525] rounded-2xl p-4">
              <label className="text-xs font-semibold text-[#6b7280] block mb-2">Equipment (optional)</label>
              <select
                value={equipmentId}
                onChange={e => setEquipmentId(e.target.value)}
                className="w-full bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl px-3 py-2 text-sm text-[#f9f9f9] appearance-none focus:outline-none focus:border-amber-500/50"
              >
                <option value="">— No specific equipment —</option>
                {equipmentList.map(eq => (
                  <option key={eq.id} value={eq.id}>
                    {eq.id} — {eq.name}
                  </option>
                ))}
              </select>
            </div>

            {/* Templates */}
            {templates.length > 0 && (
              <div className="bg-[#141414] border border-[#252525] rounded-2xl p-4">
                <p className="text-xs font-semibold text-[#6b7280] mb-3 uppercase tracking-wider">Quick templates</p>
                <div className="space-y-1.5">
                  {templates.map(tmpl => {
                    const Icon = TEMPLATE_ICONS[tmpl.icon] ?? ClipboardList;
                    return (
                      <button
                        key={tmpl.id}
                        onClick={() => applyTemplate(tmpl)}
                        className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl bg-[#0f0f0f] border border-[#1e1e1e] hover:border-amber-500/30 hover:bg-[#181818] transition-colors text-left"
                      >
                        <Icon size={14} className="text-amber-400 flex-shrink-0" />
                        <div className="min-w-0 flex-1">
                          <p className="text-xs font-medium text-[#e0e0e0]">{tmpl.label}</p>
                          <p className="text-[10px] text-[#4b5563] truncate">{tmpl.description}</p>
                        </div>
                        <ChevronRight size={12} className="text-[#333] flex-shrink-0" />
                      </button>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Description input */}
            <div className="bg-[#141414] border border-[#252525] rounded-2xl p-4">
              <label className="text-xs font-semibold text-[#6b7280] block mb-2">Describe what to record</label>
              <textarea
                value={description}
                onChange={e => setDescription(e.target.value)}
                placeholder={equipmentId
                  ? `e.g. "log a vibration check for ${equipmentId} today" or "report a bearing failure"`
                  : `e.g. "log a vibration check", "report an incident", "register new pump"`}
                rows={4}
                className="w-full bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl px-3 py-2.5 text-sm text-[#f9f9f9] placeholder-[#4b5563] focus:outline-none focus:border-amber-500/50 resize-none"
                onKeyDown={e => { if (e.key === "Enter" && e.ctrlKey) handleGenerate(); }}
              />
              <p className="text-[10px] text-[#2e2e2e] mt-1">Ctrl+Enter to generate</p>
              <button
                onClick={handleGenerate}
                disabled={generating || !description.trim()}
                className={clsx(
                  "mt-3 w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl text-sm font-semibold transition-all",
                  generating || !description.trim()
                    ? "bg-[#2a2a2a] text-[#4b5563] cursor-not-allowed"
                    : "bg-amber-500 hover:bg-amber-400 text-black"
                )}
              >
                {generating ? <Loader2 size={14} className="animate-spin" /> : <FormInput size={14} />}
                {generating ? "Generating form…" : "Generate Form"}
              </button>
            </div>
          </div>

          {/* Right pane: form */}
          <div className="bg-[#141414] border border-[#252525] rounded-2xl p-5 overflow-y-auto">
            {generating && (
              <div className="flex flex-col items-center justify-center py-20 gap-3 text-center">
                <Loader2 size={28} className="text-amber-400 animate-spin" />
                <p className="text-sm text-[#6b7280]">Generating your form…</p>
                <p className="text-xs text-[#333]">AI is reading equipment specs and building fields</p>
              </div>
            )}

            {genError && !generating && (
              <div className="flex items-center gap-2 p-4 bg-red-500/10 border border-red-500/30 rounded-xl text-sm text-red-400">
                <AlertTriangle size={14} /> {genError}
              </div>
            )}

            {!schema && !generating && !genError && (
              <div className="flex flex-col items-center justify-center py-20 gap-3 text-center">
                <FormInput size={40} className="text-[#252525]" />
                <p className="text-sm font-medium text-[#4b5563]">
                  {description ? "Click Generate Form →" : "Choose a template or describe what to record."}
                </p>
                <p className="text-xs text-[#2e2e2e] max-w-sm">
                  The AI reads equipment specifications and sensor ranges to pre-fill the right fields.
                </p>
              </div>
            )}

            {schema && !generating && (
              <DynamicForm
                schema={schema}
                onReset={() => { setSchema(null); setDescription(""); }}
              />
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Page export (wraps Suspense for useSearchParams) ──────────────────────────

export default function FormsPage() {
  return (
    <Suspense fallback={
      <div className="flex items-center justify-center h-full gap-2 text-[#4b5563]">
        <Loader2 size={16} className="animate-spin text-amber-400" /> Loading…
      </div>
    }>
      <FormsPageInner />
    </Suspense>
  );
}
