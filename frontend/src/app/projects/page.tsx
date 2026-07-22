/**
 * AI Operations Brain — Projects & Plants Page
 * Full CRUD: create / edit / delete projects and plants.
 * UX: search, status filters, modal forms, toast notifications.
 */
"use client";

import { useEffect, useState } from "react";
import {
  FolderKanban, Factory, Plus, MapPin,
  Calendar, CheckCircle2, AlertCircle,
  Layers, Wrench, X, Search, Pencil, Trash2, Loader2,
} from "lucide-react";
import clsx from "clsx";

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────

interface Project {
  id: string; code: string; name: string; description?: string;
  type: string; phase: string; status: string; location?: string;
  plant_ids: string[]; equipment_ids: string[];
  manager_id?: string; start_date?: string; end_date?: string;
  tags: string[]; created_at: string;
}

interface Plant {
  id: string; code: string; name: string; project_id?: string;
  type: string; location?: string; area?: string; description?: string;
  equipment_ids: string[]; status: string;
}

// ─────────────────────────────────────────────────────────────────────────────
// Constants
// ─────────────────────────────────────────────────────────────────────────────

const API = process.env.NEXT_PUBLIC_API_URL ?? "";

const STATUS_COLOR: Record<string, string> = {
  Active:      "text-emerald-400 bg-emerald-500/10 border-emerald-500/30",
  "On-Hold":   "text-amber-400 bg-amber-500/10 border-amber-500/30",
  Closed:      "text-[#6b7280] bg-[#2a2a2a] border-[#333]",
  Operational: "text-emerald-400 bg-emerald-500/10 border-emerald-500/30",
  Shutdown:    "text-red-400 bg-red-500/10 border-red-500/30",
  Mothballed:  "text-[#6b7280] bg-[#2a2a2a] border-[#333]",
};

const PHASE_COLOR: Record<string, string> = {
  Planning:   "text-blue-400 bg-blue-500/10 border-blue-500/30",
  Execution:  "text-amber-400 bg-amber-500/10 border-amber-500/30",
  Operations: "text-emerald-400 bg-emerald-500/10 border-emerald-500/30",
  Closed:     "text-[#6b7280] bg-[#2a2a2a] border-[#333]",
};

const PROJECT_TYPES    = ["Industrial", "Infrastructure", "Greenfield", "Brownfield", "Turnaround", "Maintenance"];
const PROJECT_PHASES   = ["Planning", "Execution", "Operations", "Closed"];
const PROJECT_STATUSES = ["Active", "On-Hold", "Closed"];
const PLANT_TYPES      = ["Process Unit", "Utility", "Storage", "Offsite", "Administration", "Fired Equipment"];
const PLANT_STATUSES   = ["Operational", "Shutdown", "Mothballed"];

// ─────────────────────────────────────────────────────────────────────────────
// Toast
// ─────────────────────────────────────────────────────────────────────────────

function Toast({ msg, ok, onDone }: { msg: string; ok: boolean; onDone: () => void }) {
  useEffect(() => { const t = setTimeout(onDone, 3200); return () => clearTimeout(t); }, [onDone]);
  return (
    <div className={clsx(
      "fixed bottom-6 right-6 z-[100] flex items-center gap-2 px-4 py-3 rounded-lg border shadow-xl text-sm font-medium",
      ok ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-300" : "bg-red-500/10 border-red-500/30 text-red-300",
    )}>
      {ok ? <CheckCircle2 size={16} /> : <AlertCircle size={16} />}
      {msg}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Confirm Delete Dialog
// ─────────────────────────────────────────────────────────────────────────────

function ConfirmDialog({ label, onConfirm, onCancel, loading }: {
  label: string; onConfirm: () => void; onCancel: () => void; loading: boolean;
}) {
  return (
    <div className="fixed inset-0 z-[80] flex items-center justify-center bg-black/60">
      <div className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl p-6 w-full max-w-sm">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 rounded-full bg-red-500/10 flex items-center justify-center">
            <Trash2 size={18} className="text-red-400" />
          </div>
          <div>
            <p className="text-sm font-semibold text-[#f9f9f9]">Confirm Delete</p>
            <p className="text-xs text-[#6b7280]">This action cannot be undone</p>
          </div>
        </div>
        <p className="text-sm text-[#a0a0a0] mb-5">Delete <span className="text-[#f9f9f9] font-medium">&ldquo;{label}&rdquo;</span>?</p>
        <div className="flex gap-2">
          <button onClick={onCancel} disabled={loading}
            className="flex-1 py-2 text-sm rounded-lg border border-[#333] text-[#a0a0a0] hover:text-[#f9f9f9]">Cancel</button>
          <button onClick={onConfirm} disabled={loading}
            className="flex-1 py-2 text-sm rounded-lg bg-red-500/20 border border-red-500/40 text-red-400 hover:bg-red-500/30 flex items-center justify-center gap-2">
            {loading && <Loader2 size={13} className="animate-spin" />} Delete
          </button>
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Form helpers
// ─────────────────────────────────────────────────────────────────────────────

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="block text-xs font-medium text-[#a0a0a0] mb-1">{label}</label>
      {children}
    </div>
  );
}

const inputCls  = "w-full bg-[#111] border border-[#333] rounded-lg px-3 py-2 text-sm text-[#f9f9f9] focus:outline-none focus:border-amber-500/60 placeholder-[#444]";
const selectCls = "w-full bg-[#111] border border-[#333] rounded-lg px-3 py-2 text-sm text-[#f9f9f9] focus:outline-none focus:border-amber-500/60";

// ─────────────────────────────────────────────────────────────────────────────
// Project Form Modal
// ─────────────────────────────────────────────────────────────────────────────

function ProjectFormModal({ initial, onClose, onSave }: {
  initial?: Project; onClose: () => void; onSave: () => void;
}) {
  const isEdit = !!initial;
  const [form, setForm] = useState({
    code: initial?.code ?? "", name: initial?.name ?? "",
    description: initial?.description ?? "", type: initial?.type ?? "Industrial",
    phase: initial?.phase ?? "Operations", status: initial?.status ?? "Active",
    location: initial?.location ?? "", start_date: initial?.start_date ?? "",
    end_date: initial?.end_date ?? "", tags: (initial?.tags ?? []).join(", "),
  });
  const [saving, setSaving] = useState(false);
  const [err, setErr]       = useState("");

  const set = (k: string, v: string) => setForm(f => ({ ...f, [k]: v }));

  const submit = async () => {
    if (!form.name.trim()) { setErr("Name is required"); return; }
    if (!isEdit && !form.code.trim()) { setErr("Code is required"); return; }
    setSaving(true); setErr("");
    try {
      const payload: Record<string, unknown> = {
        name: form.name.trim(), description: form.description || undefined,
        type: form.type, phase: form.phase, status: form.status,
        location: form.location || undefined,
        start_date: form.start_date || undefined, end_date: form.end_date || undefined,
        tags: form.tags ? form.tags.split(",").map(s => s.trim()).filter(Boolean) : [],
      };
      if (!isEdit) payload.code = form.code.trim();
      const url = isEdit ? `${API}/api/v1/pm/projects/${initial!.id}` : `${API}/api/v1/pm/projects`;
      const res = await fetch(url, { method: isEdit ? "PATCH" : "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
      if (!res.ok) { const e = await res.json(); setErr(e.detail ?? "Failed to save"); }
      else { onSave(); }
    } catch { setErr("Network error"); }
    setSaving(false);
  };

  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center bg-black/60">
      <div className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl w-full max-w-xl max-h-[92vh] overflow-y-auto">
        <div className="sticky top-0 bg-[#1a1a1a] border-b border-[#2a2a2a] px-6 py-4 flex items-center justify-between">
          <p className="text-base font-bold text-[#f9f9f9]">{isEdit ? "Edit Project" : "New Project"}</p>
          <button onClick={onClose} className="text-[#6b7280] hover:text-[#f9f9f9]"><X size={18} /></button>
        </div>
        <div className="p-6 space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <Field label="Name *"><input className={inputCls} value={form.name} onChange={e => set("name", e.target.value)} placeholder="CDU Revamp 2025" /></Field>
            <Field label="Code *"><input className={inputCls} value={form.code} onChange={e => set("code", e.target.value)} disabled={isEdit} placeholder="PRJ-001" /></Field>
          </div>
          <Field label="Description"><textarea className={inputCls + " resize-none h-16"} value={form.description} onChange={e => set("description", e.target.value)} placeholder="Brief description…" /></Field>
          <div className="grid grid-cols-3 gap-4">
            <Field label="Type"><select className={selectCls} value={form.type} onChange={e => set("type", e.target.value)}>{PROJECT_TYPES.map(t => <option key={t}>{t}</option>)}</select></Field>
            <Field label="Phase"><select className={selectCls} value={form.phase} onChange={e => set("phase", e.target.value)}>{PROJECT_PHASES.map(t => <option key={t}>{t}</option>)}</select></Field>
            <Field label="Status"><select className={selectCls} value={form.status} onChange={e => set("status", e.target.value)}>{PROJECT_STATUSES.map(t => <option key={t}>{t}</option>)}</select></Field>
          </div>
          <Field label="Location"><input className={inputCls} value={form.location} onChange={e => set("location", e.target.value)} placeholder="Refinery Site A, Gujarat" /></Field>
          <div className="grid grid-cols-2 gap-4">
            <Field label="Start Date"><input type="date" className={inputCls} value={form.start_date} onChange={e => set("start_date", e.target.value)} /></Field>
            <Field label="End Date"><input type="date" className={inputCls} value={form.end_date} onChange={e => set("end_date", e.target.value)} /></Field>
          </div>
          <Field label="Tags (comma-separated)"><input className={inputCls} value={form.tags} onChange={e => set("tags", e.target.value)} placeholder="refinery, turnaround, CDU" /></Field>
          {err && <p className="text-xs text-red-400">{err}</p>}
          <div className="flex gap-3 pt-2">
            <button onClick={onClose} className="flex-1 py-2 text-sm rounded-lg border border-[#333] text-[#a0a0a0] hover:text-[#f9f9f9]">Cancel</button>
            <button onClick={submit} disabled={saving} className="flex-1 py-2 text-sm rounded-lg bg-amber-500/20 border border-amber-500/40 text-amber-400 hover:bg-amber-500/30 flex items-center justify-center gap-2">
              {saving && <Loader2 size={13} className="animate-spin" />}{isEdit ? "Save Changes" : "Create Project"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Plant Form Modal
// ─────────────────────────────────────────────────────────────────────────────

function PlantFormModal({ initial, projects, onClose, onSave }: {
  initial?: Plant; projects: Project[]; onClose: () => void; onSave: () => void;
}) {
  const isEdit = !!initial;
  const [form, setForm] = useState({
    code: initial?.code ?? "", name: initial?.name ?? "",
    project_id: initial?.project_id ?? "", type: initial?.type ?? "Process Unit",
    location: initial?.location ?? "", area: initial?.area ?? "",
    description: initial?.description ?? "", status: initial?.status ?? "Operational",
  });
  const [saving, setSaving] = useState(false);
  const [err, setErr]       = useState("");

  const set = (k: string, v: string) => setForm(f => ({ ...f, [k]: v }));

  const submit = async () => {
    if (!form.name.trim()) { setErr("Name is required"); return; }
    if (!isEdit && !form.code.trim()) { setErr("Code is required"); return; }
    setSaving(true); setErr("");
    try {
      const payload: Record<string, unknown> = {
        name: form.name.trim(), project_id: form.project_id || undefined,
        type: form.type, location: form.location || undefined,
        area: form.area || undefined, description: form.description || undefined, status: form.status,
      };
      if (!isEdit) payload.code = form.code.trim();
      const url = isEdit ? `${API}/api/v1/pm/plants/${initial!.id}` : `${API}/api/v1/pm/plants`;
      const res = await fetch(url, { method: isEdit ? "PATCH" : "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
      if (!res.ok) { const e = await res.json(); setErr(e.detail ?? "Failed to save"); }
      else { onSave(); }
    } catch { setErr("Network error"); }
    setSaving(false);
  };

  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center bg-black/60">
      <div className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl w-full max-w-xl max-h-[92vh] overflow-y-auto">
        <div className="sticky top-0 bg-[#1a1a1a] border-b border-[#2a2a2a] px-6 py-4 flex items-center justify-between">
          <p className="text-base font-bold text-[#f9f9f9]">{isEdit ? "Edit Plant" : "New Plant"}</p>
          <button onClick={onClose} className="text-[#6b7280] hover:text-[#f9f9f9]"><X size={18} /></button>
        </div>
        <div className="p-6 space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <Field label="Name *"><input className={inputCls} value={form.name} onChange={e => set("name", e.target.value)} placeholder="CDU Unit 4" /></Field>
            <Field label="Code *"><input className={inputCls} value={form.code} onChange={e => set("code", e.target.value)} disabled={isEdit} placeholder="PLT-001" /></Field>
          </div>
          <Field label="Parent Project">
            <select className={selectCls} value={form.project_id} onChange={e => set("project_id", e.target.value)}>
              <option value="">— None —</option>
              {projects.map(p => <option key={p.id} value={p.id}>{p.name} ({p.code})</option>)}
            </select>
          </Field>
          <div className="grid grid-cols-2 gap-4">
            <Field label="Type"><select className={selectCls} value={form.type} onChange={e => set("type", e.target.value)}>{PLANT_TYPES.map(t => <option key={t}>{t}</option>)}</select></Field>
            <Field label="Status"><select className={selectCls} value={form.status} onChange={e => set("status", e.target.value)}>{PLANT_STATUSES.map(t => <option key={t}>{t}</option>)}</select></Field>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <Field label="Location"><input className={inputCls} value={form.location} onChange={e => set("location", e.target.value)} placeholder="Site A, Block 3" /></Field>
            <Field label="Area"><input className={inputCls} value={form.area} onChange={e => set("area", e.target.value)} placeholder="North Wing" /></Field>
          </div>
          <Field label="Description"><textarea className={inputCls + " resize-none h-16"} value={form.description} onChange={e => set("description", e.target.value)} placeholder="Brief description…" /></Field>
          {err && <p className="text-xs text-red-400">{err}</p>}
          <div className="flex gap-3 pt-2">
            <button onClick={onClose} className="flex-1 py-2 text-sm rounded-lg border border-[#333] text-[#a0a0a0] hover:text-[#f9f9f9]">Cancel</button>
            <button onClick={submit} disabled={saving} className="flex-1 py-2 text-sm rounded-lg bg-amber-500/20 border border-amber-500/40 text-amber-400 hover:bg-amber-500/30 flex items-center justify-center gap-2">
              {saving && <Loader2 size={13} className="animate-spin" />}{isEdit ? "Save Changes" : "Create Plant"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Pill
// ─────────────────────────────────────────────────────────────────────────────

function Pill({ label, cls }: { label: string; cls: string }) {
  return <span className={clsx("text-xs px-2 py-0.5 rounded border font-medium", cls)}>{label}</span>;
}

// ─────────────────────────────────────────────────────────────────────────────
// Project Card
// ─────────────────────────────────────────────────────────────────────────────

function ProjectCard({ project, plants, onSelect, onEdit, onDelete }: {
  project: Project; plants: Plant[];
  onSelect: (p: Project) => void; onEdit: (p: Project) => void; onDelete: (p: Project) => void;
}) {
  const myPlants = plants.filter(pl => pl.project_id === project.id);
  return (
    <div className="group bg-[#1f1f1f] border border-[#2a2a2a] rounded-lg p-4 hover:border-amber-500/40 transition-colors relative">
      {/* hover actions */}
      <div className="absolute top-3 right-3 flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
        <button onClick={e => { e.stopPropagation(); onEdit(project); }}
          className="p-1.5 rounded bg-[#2a2a2a] text-[#6b7280] hover:text-amber-400 hover:bg-amber-500/10 transition-colors" title="Edit">
          <Pencil size={13} />
        </button>
        <button onClick={e => { e.stopPropagation(); onDelete(project); }}
          className="p-1.5 rounded bg-[#2a2a2a] text-[#6b7280] hover:text-red-400 hover:bg-red-500/10 transition-colors" title="Delete">
          <Trash2 size={13} />
        </button>
      </div>
      <div className="cursor-pointer" onClick={() => onSelect(project)}>
        <div className="flex items-start gap-2 mb-3 pr-16">
          <FolderKanban size={18} className="text-amber-500 flex-shrink-0 mt-0.5" />
          <div className="min-w-0">
            <p className="text-sm font-semibold text-[#f9f9f9] truncate">{project.name}</p>
            <p className="text-xs text-[#6b7280]">{project.code}</p>
          </div>
        </div>
        <div className="flex flex-wrap gap-1.5 mb-3">
          <Pill label={project.status} cls={STATUS_COLOR[project.status] ?? "text-[#a0a0a0]"} />
          <Pill label={project.phase} cls={PHASE_COLOR[project.phase] ?? "text-[#a0a0a0]"} />
        </div>
        {project.description && <p className="text-xs text-[#a0a0a0] mb-3 line-clamp-2">{project.description}</p>}
        <div className="grid grid-cols-3 gap-2 mb-3">
          <div className="bg-[#242424] rounded p-2 text-center"><p className="text-lg font-bold text-amber-400">{myPlants.length}</p><p className="text-xs text-[#6b7280]">Plants</p></div>
          <div className="bg-[#242424] rounded p-2 text-center"><p className="text-lg font-bold text-blue-400">{project.equipment_ids?.length ?? 0}</p><p className="text-xs text-[#6b7280]">Equipment</p></div>
          <div className="bg-[#242424] rounded p-2 text-center"><p className="text-xs font-bold text-purple-400 leading-5">{project.type.split(" ")[0]}</p><p className="text-xs text-[#6b7280]">Type</p></div>
        </div>
        <div className="flex items-center gap-3 text-xs text-[#6b7280] flex-wrap">
          {project.location && <span className="flex items-center gap-1"><MapPin size={11} />{project.location}</span>}
          {project.start_date && <span className="flex items-center gap-1"><Calendar size={11} />Since {project.start_date.slice(0, 4)}</span>}
        </div>
        {project.tags?.length > 0 && (
          <div className="flex flex-wrap gap-1 mt-2">
            {project.tags.slice(0, 4).map(t => <span key={t} className="text-xs px-1.5 py-0.5 rounded bg-[#2a2a2a] text-[#6b7280]">{t}</span>)}
          </div>
        )}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Plant Card
// ─────────────────────────────────────────────────────────────────────────────

function PlantCard({ plant, onEdit, onDelete }: {
  plant: Plant; onEdit: (p: Plant) => void; onDelete: (p: Plant) => void;
}) {
  return (
    <div className="group bg-[#1a1a1a] border border-[#2a2a2a] rounded-lg p-4 hover:border-blue-500/30 transition-colors relative">
      <div className="absolute top-3 right-3 flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
        <button onClick={() => onEdit(plant)} className="p-1.5 rounded bg-[#2a2a2a] text-[#6b7280] hover:text-amber-400 hover:bg-amber-500/10 transition-colors" title="Edit"><Pencil size={13} /></button>
        <button onClick={() => onDelete(plant)} className="p-1.5 rounded bg-[#2a2a2a] text-[#6b7280] hover:text-red-400 hover:bg-red-500/10 transition-colors" title="Delete"><Trash2 size={13} /></button>
      </div>
      <div className="flex items-start justify-between gap-2 mb-2 pr-16">
        <div className="flex items-center gap-2">
          <Factory size={16} className="text-blue-400 flex-shrink-0" />
          <div><p className="text-sm font-semibold text-[#f9f9f9]">{plant.name}</p><p className="text-xs text-[#6b7280]">{plant.code}</p></div>
        </div>
        <Pill label={plant.status} cls={STATUS_COLOR[plant.status] ?? "text-[#a0a0a0]"} />
      </div>
      {plant.description && <p className="text-xs text-[#a0a0a0] mb-2 line-clamp-2">{plant.description}</p>}
      <div className="flex items-center gap-3 text-xs text-[#6b7280] flex-wrap">
        {plant.location && <span className="flex items-center gap-1"><MapPin size={11} />{plant.location}</span>}
        {plant.area && <span className="flex items-center gap-1"><Layers size={11} />{plant.area}</span>}
        <span className="flex items-center gap-1"><Wrench size={11} />{plant.equipment_ids?.length ?? 0} equipment</span>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Project Detail Drawer
// ─────────────────────────────────────────────────────────────────────────────

function ProjectDetail({ project, plants, onClose }: { project: Project; plants: Plant[]; onClose: () => void }) {
  const myPlants = plants.filter(pl => pl.project_id === project.id);
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <div className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl w-full max-w-2xl max-h-[90vh] overflow-y-auto">
        <div className="sticky top-0 bg-[#1a1a1a] border-b border-[#2a2a2a] px-6 py-4 flex items-center justify-between">
          <div>
            <p className="text-base font-bold text-[#f9f9f9]">{project.name}</p>
            <p className="text-xs text-[#6b7280]">{project.code} &middot; {project.type}</p>
          </div>
          <button onClick={onClose} className="text-[#6b7280] hover:text-[#f9f9f9]"><X size={20} /></button>
        </div>
        <div className="p-6 space-y-5">
          <div className="flex flex-wrap gap-2">
            <Pill label={project.status} cls={STATUS_COLOR[project.status] ?? "text-[#a0a0a0]"} />
            <Pill label={project.phase} cls={PHASE_COLOR[project.phase] ?? "text-[#a0a0a0]"} />
          </div>
          {project.description && <p className="text-sm text-[#a0a0a0]">{project.description}</p>}
          <div className="grid grid-cols-2 gap-3 text-sm">
            {project.location && <div className="flex items-center gap-2 text-[#a0a0a0]"><MapPin size={13} className="text-amber-400" />{project.location}</div>}
            {project.start_date && <div className="flex items-center gap-2 text-[#a0a0a0]"><Calendar size={13} className="text-amber-400" />Start: {project.start_date}</div>}
            {project.end_date && <div className="flex items-center gap-2 text-[#a0a0a0]"><Calendar size={13} className="text-red-400" />End: {project.end_date}</div>}
          </div>
          {project.tags?.length > 0 && (
            <div className="flex flex-wrap gap-1">
              {project.tags.map(t => <span key={t} className="text-xs px-2 py-0.5 rounded bg-[#2a2a2a] text-[#6b7280] border border-[#333]">{t}</span>)}
            </div>
          )}
          <div>
            <h3 className="text-sm font-semibold text-[#f9f9f9] mb-3 flex items-center gap-2">
              <Factory size={14} className="text-blue-400" />Plants ({myPlants.length})
            </h3>
            {myPlants.length === 0
              ? <p className="text-xs text-[#6b7280]">No plants assigned to this project.</p>
              : <div className="space-y-2">{myPlants.map(pl => (
                  <div key={pl.id} className="bg-[#242424] rounded-lg p-3 flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Factory size={14} className="text-blue-400" />
                      <div><p className="text-sm text-[#f9f9f9]">{pl.name}</p><p className="text-xs text-[#6b7280]">{pl.code} &middot; {pl.type}</p></div>
                    </div>
                    <Pill label={pl.status} cls={STATUS_COLOR[pl.status] ?? "text-[#a0a0a0]"} />
                  </div>
                ))}</div>
            }
          </div>
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Main Page
// ─────────────────────────────────────────────────────────────────────────────

export default function ProjectsPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [plants,   setPlants]   = useState<Plant[]>([]);
  const [stats,    setStats]    = useState<Record<string, unknown> | null>(null);
  const [loading,  setLoading]  = useState(true);
  const [activeTab, setActiveTab] = useState<"projects" | "plants">("projects");

  const [search,       setSearch]       = useState("");
  const [filterStatus, setFilterStatus] = useState("all");

  const [detailProject, setDetailProject] = useState<Project | null>(null);
  const [projectForm, setProjectForm]     = useState<{ open: boolean; initial?: Project }>({ open: false });
  const [plantForm,   setPlantForm]       = useState<{ open: boolean; initial?: Plant }>({ open: false });
  const [deleteTarget, setDeleteTarget]   = useState<{ id: string; label: string; type: "project" | "plant" } | null>(null);
  const [deleteLoading, setDeleteLoading] = useState(false);
  const [toast, setToast] = useState<{ msg: string; ok: boolean } | null>(null);

  const notify = (msg: string, ok = true) => setToast({ msg, ok });

  const load = async () => {
    setLoading(true);
    const [pRes, plRes, stRes] = await Promise.all([
      fetch(`${API}/api/v1/pm/projects`).then(r => r.ok ? r.json() : []),
      fetch(`${API}/api/v1/pm/plants`).then(r => r.ok ? r.json() : []),
      fetch(`${API}/api/v1/pm/stats`).then(r => r.ok ? r.json() : null),
    ]);
    setProjects(pRes);
    setPlants(plRes);
    setStats(stRes);
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  const handleDeleteConfirm = async () => {
    if (!deleteTarget) return;
    setDeleteLoading(true);
    try {
      const url = deleteTarget.type === "project"
        ? `${API}/api/v1/pm/projects/${deleteTarget.id}`
        : `${API}/api/v1/pm/plants/${deleteTarget.id}`;
      const res = await fetch(url, { method: "DELETE" });
      if (res.ok || res.status === 204) {
        notify(`${deleteTarget.type === "project" ? "Project" : "Plant"} deleted`);
        await load();
      } else { notify("Delete failed", false); }
    } catch { notify("Network error", false); }
    setDeleteLoading(false);
    setDeleteTarget(null);
  };

  const filteredProjects = projects.filter(p => {
    const q = search.toLowerCase();
    return (!q || p.name.toLowerCase().includes(q) || p.code.toLowerCase().includes(q) || (p.location ?? "").toLowerCase().includes(q))
      && (filterStatus === "all" || p.status === filterStatus);
  });

  const filteredPlants = plants.filter(p => {
    const q = search.toLowerCase();
    return (!q || p.name.toLowerCase().includes(q) || p.code.toLowerCase().includes(q) || (p.location ?? "").toLowerCase().includes(q))
      && (filterStatus === "all" || p.status === filterStatus);
  });

  const statusOptions = activeTab === "projects"
    ? ["all", "Active", "On-Hold", "Closed"]
    : ["all", "Operational", "Shutdown", "Mothballed"];

  return (
    <div className="flex-1 overflow-y-auto p-6 bg-[#0f0f0f] min-h-screen">
      {/* Overlays */}
      {detailProject && <ProjectDetail project={detailProject} plants={plants} onClose={() => setDetailProject(null)} />}
      {projectForm.open && (
        <ProjectFormModal
          initial={projectForm.initial}
          onClose={() => setProjectForm({ open: false })}
          onSave={() => { load(); setProjectForm({ open: false }); notify(projectForm.initial ? "Project updated" : "Project created"); }}
        />
      )}
      {plantForm.open && (
        <PlantFormModal
          initial={plantForm.initial}
          projects={projects}
          onClose={() => setPlantForm({ open: false })}
          onSave={() => { load(); setPlantForm({ open: false }); notify(plantForm.initial ? "Plant updated" : "Plant created"); }}
        />
      )}
      {deleteTarget && (
        <ConfirmDialog label={deleteTarget.label} loading={deleteLoading} onConfirm={handleDeleteConfirm} onCancel={() => setDeleteTarget(null)} />
      )}
      {toast && <Toast msg={toast.msg} ok={toast.ok} onDone={() => setToast(null)} />}

      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-[#f9f9f9] flex items-center gap-3">
            <FolderKanban size={26} className="text-amber-500" />Project Management
          </h1>
          <p className="text-sm text-[#6b7280] mt-1">Manage projects, plants, and equipment hierarchy</p>
        </div>
        <button
          onClick={() => activeTab === "projects" ? setProjectForm({ open: true }) : setPlantForm({ open: true })}
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-amber-500/20 border border-amber-500/40 text-amber-400 hover:bg-amber-500/30 text-sm font-medium transition-colors">
          <Plus size={16} />{activeTab === "projects" ? "New Project" : "New Plant"}
        </button>
      </div>

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
          <div className="bg-[#1f1f1f] border border-[#2a2a2a] rounded-lg p-4 text-center">
            <p className="text-2xl font-bold text-amber-400">{stats.projects as number}</p>
            <p className="text-xs text-[#6b7280]">Total Projects</p>
          </div>
          <div className="bg-[#1f1f1f] border border-[#2a2a2a] rounded-lg p-4 text-center">
            <p className="text-2xl font-bold text-blue-400">{stats.plants as number}</p>
            <p className="text-xs text-[#6b7280]">Total Plants</p>
          </div>
          <div className="bg-[#1f1f1f] border border-[#2a2a2a] rounded-lg p-4 text-center">
            <p className="text-2xl font-bold text-emerald-400">{(stats.projects_by_status as Record<string,number>)?.Active ?? 0}</p>
            <p className="text-xs text-[#6b7280]">Active Projects</p>
          </div>
          <div className="bg-[#1f1f1f] border border-[#2a2a2a] rounded-lg p-4 text-center">
            <p className="text-2xl font-bold text-emerald-400">{(stats.plants_by_status as Record<string,number>)?.Operational ?? 0}</p>
            <p className="text-xs text-[#6b7280]">Operational Plants</p>
          </div>
        </div>
      )}

      {/* Toolbar */}
      <div className="flex flex-col sm:flex-row gap-3 mb-5">
        <div className="flex gap-1">
          {(["projects", "plants"] as const).map(tab => (
            <button key={tab} onClick={() => { setActiveTab(tab); setFilterStatus("all"); setSearch(""); }}
              className={clsx(
                "px-4 py-1.5 rounded-lg text-sm font-medium transition-colors",
                activeTab === tab ? "bg-amber-500/10 text-amber-400 border border-amber-500/30" : "text-[#6b7280] hover:text-[#f9f9f9] border border-transparent",
              )}>
              {tab === "projects" ? `Projects (${projects.length})` : `Plants (${plants.length})`}
            </button>
          ))}
        </div>
        <div className="relative flex-1 max-w-xs">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-[#6b7280]" />
          <input
            className="w-full bg-[#1a1a1a] border border-[#2a2a2a] rounded-lg pl-9 pr-3 py-1.5 text-sm text-[#f9f9f9] placeholder-[#4b5563] focus:outline-none focus:border-amber-500/50"
            placeholder={activeTab === "projects" ? "Search projects…" : "Search plants…"}
            value={search} onChange={e => setSearch(e.target.value)}
          />
        </div>
        <div className="flex gap-1.5 flex-wrap">
          {statusOptions.map(s => (
            <button key={s} onClick={() => setFilterStatus(s)}
              className={clsx(
                "px-3 py-1 text-xs rounded border font-medium transition-colors",
                filterStatus === s ? "border-amber-500/50 bg-amber-500/10 text-amber-400" : "border-[#2a2a2a] text-[#6b7280] hover:text-[#f9f9f9]",
              )}>
              {s === "all" ? "All" : s}
            </button>
          ))}
        </div>
      </div>

      {/* Content */}
      {loading ? (
        <div className="flex items-center justify-center py-20 text-[#6b7280]">
          <Loader2 size={20} className="animate-spin mr-2" />Loading&hellip;
        </div>
      ) : activeTab === "projects" ? (
        filteredProjects.length === 0 ? (
          <div className="text-center py-20">
            <FolderKanban size={40} className="text-[#333] mx-auto mb-3" />
            <p className="text-sm text-[#6b7280]">{search ? "No projects match your search" : "No projects yet"}</p>
            {!search && <button onClick={() => setProjectForm({ open: true })} className="mt-3 text-sm text-amber-400 hover:underline">Create your first project &rarr;</button>}
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {filteredProjects.map(p => (
              <ProjectCard key={p.id} project={p} plants={plants}
                onSelect={setDetailProject}
                onEdit={pr => setProjectForm({ open: true, initial: pr })}
                onDelete={pr => setDeleteTarget({ id: pr.id, label: pr.name, type: "project" })}
              />
            ))}
          </div>
        )
      ) : (
        filteredPlants.length === 0 ? (
          <div className="text-center py-20">
            <Factory size={40} className="text-[#333] mx-auto mb-3" />
            <p className="text-sm text-[#6b7280]">{search ? "No plants match your search" : "No plants yet"}</p>
            {!search && <button onClick={() => setPlantForm({ open: true })} className="mt-3 text-sm text-amber-400 hover:underline">Create your first plant &rarr;</button>}
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {filteredPlants.map(p => (
              <PlantCard key={p.id} plant={p}
                onEdit={pl => setPlantForm({ open: true, initial: pl })}
                onDelete={pl => setDeleteTarget({ id: pl.id, label: pl.name, type: "plant" })}
              />
            ))}
          </div>
        )
      )}
    </div>
  );
}
