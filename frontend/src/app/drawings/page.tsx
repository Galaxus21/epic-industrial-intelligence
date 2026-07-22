/**
 * AI Operations Brain — Engineering Drawing Reader (/drawings)
 *
 * Feature set
 * ───────────
 * • Multi-format upload: PNG, JPG, TIFF, BMP, WebP, GIF, PDF, SVG, DXF, DWG,
 *   STEP, IGES, IFC, DGN — all industry-standard formats.
 * • Hierarchy: Project → Plant/Site → Drawing (left panel navigator).
 * • Each drawing is auto-digitised after upload:
 *     - Images/PDF  → GPT-4V vision P&ID extraction → dark SVG
 *     - DXF/DWG     → ezdxf → dark SVG
 *     - 3-D/BIM     → info placeholder
 * • Analytics overlay per plant/site:
 *     Incidents · Active PTWs · Open Work Orders · Open Inspections · Risk score
 * • Drawing viewer: full SVG viewer + live analytics side panel.
 * • Upload modal: drag-and-drop with project/plant picker.
 */
"use client";

import React, { useCallback, useEffect, useRef, useState } from "react";
import clsx from "clsx";
import {
  Layers, UploadCloud, FileText, AlertTriangle, ShieldAlert,
  Wrench, ClipboardList, X, ChevronDown, ChevronRight,
  Search, RefreshCw, Trash2, RotateCcw, Plus, Loader2,
  CheckCircle2, AlertCircle, Clock, ZoomIn, ZoomOut,
  Maximize2, Minimize2, Building2, FolderOpen, FileImage,
  Activity, BarChart3, Download,
} from "lucide-react";
import {
  listEngDrawings, getDrawingsTree, getDrawingAnalytics,
  uploadEngDrawing, deleteEngDrawing, reExtractDrawing,
  type EngDrawing, type DrawingAnalytics, type ProjectTree,
} from "@/lib/api";
import { usePageState } from "@/lib/page-state";

const API = process.env.NEXT_PUBLIC_API_URL ?? "";

const SUPPORTED_FORMATS = [
  { group: "Raster Images",  exts: ["PNG", "JPG", "JPEG", "TIFF", "BMP", "WebP", "GIF"] },
  { group: "Vector / Doc",   exts: ["SVG", "PDF"] },
  { group: "CAD Vector",     exts: ["DXF", "DWG"] },
  { group: "3-D / BIM",      exts: ["STEP", "STP", "IGES", "IGS", "IFC", "DGN"] },
];

const DRAWING_TYPES = [
  "general", "pid", "pfd", "electrical", "mechanical",
  "civil", "hvac", "isometric", "layout",
];

const DISCIPLINES = ["Process", "Mechanical", "Electrical", "Civil", "Instrumentation", "Structural", "HVAC"];

const TYPE_LABEL: Record<string, string> = {
  pid: "P&ID", pfd: "PFD", electrical: "Electrical", mechanical: "Mechanical",
  civil: "Civil", hvac: "HVAC", isometric: "Isometric", layout: "Layout", general: "General",
};

const EXTR_COLOR: Record<string, string> = {
  done:        "text-emerald-400 bg-emerald-500/10 border-emerald-500/30",
  processing:  "text-amber-400  bg-amber-500/10  border-amber-500/30",
  pending:     "text-blue-400   bg-blue-500/10   border-blue-500/30",
  failed:      "text-red-400    bg-red-500/10    border-red-500/30",
  unsupported: "text-[#6b7280]  bg-[#1a1a1a]     border-[#2a2a2a]",
};

const FORMAT_COLOR: Record<string, string> = {
  pdf: "text-red-400 bg-red-500/10 border-red-500/30",
  dxf: "text-blue-400 bg-blue-500/10 border-blue-500/30",
  dwg: "text-purple-400 bg-purple-500/10 border-purple-500/30",
  svg: "text-emerald-400 bg-emerald-500/10 border-emerald-500/30",
  step: "text-cyan-400 bg-cyan-500/10 border-cyan-500/30",
  iges: "text-cyan-400 bg-cyan-500/10 border-cyan-500/30",
  ifc:  "text-orange-400 bg-orange-500/10 border-orange-500/30",
};

function Pill({ label, cls }: { label: string; cls: string }) {
  return (
    <span className={clsx("text-xs px-2 py-0.5 rounded border font-medium", cls)}>
      {label}
    </span>
  );
}

function Toast({ msg, ok, onDone }: { msg: string; ok: boolean; onDone: () => void }) {
  useEffect(() => { const t = setTimeout(onDone, 3200); return () => clearTimeout(t); }, [onDone]);
  return (
    <div className={clsx(
      "fixed bottom-6 right-6 z-[100] flex items-center gap-2 px-4 py-3 rounded-lg border shadow-xl text-sm font-medium",
      ok ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-300" : "bg-red-500/10 border-red-500/30 text-red-300",
    )}>
      {ok ? <CheckCircle2 size={16} /> : <AlertCircle size={16} />}{msg}
    </div>
  );
}

function MetricCard({ icon, label, value, sub, color, bg }: {
  icon: React.ReactNode; label: string; value: number; sub?: string; color: string; bg: string;
}) {
  return (
    <div className={clsx("rounded-lg border p-3", bg)}>
      <div className="flex items-center gap-2 mb-1">
        <span className={color}>{icon}</span>
        <p className="text-xs text-[#6b7280]">{label}</p>
      </div>
      <p className={clsx("text-3xl font-black", value > 0 ? color : "text-[#4b5563]")}>{value}</p>
      {sub && <p className="text-xs text-[#6b7280] mt-0.5">{sub}</p>}
    </div>
  );
}

function DrawingViewer({ drawing, onClose, onDeleted, onRefresh }: {
  drawing: EngDrawing; onClose: () => void; onDeleted: () => void; onRefresh: () => void;
}) {
  const [analytics, setAnalytics] = useState<DrawingAnalytics | null>(drawing.analytics ?? null);
  const [loadingAnalytics, setLoadingAnalytics] = useState(false);
  const [reExtracting, setReExtracting] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [tab, setTab] = useState<"view" | "info" | "analytics">("view");
  const [zoom, setZoom] = useState(1);
  const [fullscreen, setFullscreen] = useState(false);

  const viewUrl = `${API}/api/v1/drawings/${drawing.id}/view`;

  const loadAnalytics = async () => {
    setLoadingAnalytics(true);
    try { const data = await getDrawingAnalytics(drawing.id); setAnalytics(data); } catch { /* ignore */ }
    setLoadingAnalytics(false);
  };

  useEffect(() => { if (tab === "analytics" && !analytics) loadAnalytics(); }, [tab]);

  const handleReExtract = async () => {
    setReExtracting(true);
    try { await reExtractDrawing(drawing.id); onRefresh(); } catch { /* ignore */ }
    setReExtracting(false);
  };

  const handleDelete = async () => {
    setDeleting(true);
    try { await deleteEngDrawing(drawing.id); onDeleted(); } catch { /* ignore */ }
    setDeleting(false);
  };

  const fmtCls  = FORMAT_COLOR[drawing.file_format] ?? "text-[#a0a0a0] bg-[#1a1a1a] border-[#2a2a2a]";
  const extrCls = EXTR_COLOR[drawing.extraction_status] ?? "";

  return (
    <div className={clsx(
      "fixed z-50 bg-[#111] border border-[#2a2a2a] flex flex-col shadow-2xl transition-all",
      fullscreen ? "inset-0 rounded-none" : "inset-4 rounded-xl",
    )}>
      <div className="flex items-center justify-between px-5 py-3 border-b border-[#2a2a2a] flex-shrink-0">
        <div className="flex items-center gap-3 min-w-0">
          <FileImage size={18} className="text-amber-500 flex-shrink-0" />
          <div className="min-w-0">
            <p className="text-sm font-bold text-[#f9f9f9] truncate">{drawing.title}</p>
            <p className="text-xs text-[#6b7280]">{drawing.drawing_number} · Rev {drawing.revision} · {drawing.original_filename}</p>
          </div>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          <Pill label={drawing.file_format.toUpperCase()} cls={fmtCls} />
          <Pill label={drawing.extraction_status} cls={extrCls} />
          <button onClick={handleReExtract} disabled={reExtracting} title="Re-extract"
            className="p-1.5 rounded bg-[#1f1f1f] border border-[#333] text-[#6b7280] hover:text-amber-400 hover:border-amber-500/40">
            {reExtracting ? <Loader2 size={14} className="animate-spin" /> : <RotateCcw size={14} />}
          </button>
          <a href={viewUrl} download={`${drawing.drawing_number}.svg`} title="Download SVG"
            className="p-1.5 rounded bg-[#1f1f1f] border border-[#333] text-[#6b7280] hover:text-emerald-400 hover:border-emerald-500/40">
            <Download size={14} />
          </a>
          <button onClick={() => setConfirmDelete(true)} title="Delete"
            className="p-1.5 rounded bg-[#1f1f1f] border border-[#333] text-[#6b7280] hover:text-red-400 hover:border-red-500/40">
            <Trash2 size={14} />
          </button>
          <button onClick={() => setFullscreen(f => !f)}
            className="p-1.5 rounded bg-[#1f1f1f] border border-[#333] text-[#6b7280] hover:text-[#f9f9f9]">
            {fullscreen ? <Minimize2 size={14} /> : <Maximize2 size={14} />}
          </button>
          <button onClick={onClose} className="p-1.5 rounded text-[#6b7280] hover:text-[#f9f9f9]"><X size={16} /></button>
        </div>
      </div>

      <div className="flex gap-1 px-5 pt-2 border-b border-[#2a2a2a] flex-shrink-0">
        {(["view", "analytics", "info"] as const).map(t => (
          <button key={t} onClick={() => setTab(t)}
            className={clsx("px-3 py-1.5 text-xs rounded-t font-medium capitalize",
              tab === t ? "bg-amber-500/10 text-amber-400 border-b-2 border-amber-500" : "text-[#6b7280] hover:text-[#f9f9f9]")}>
            {t === "view" ? "Drawing View" : t === "analytics" ? "Analytics" : "Metadata"}
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-hidden">
        {tab === "view" && (
          <div className="h-full flex flex-col">
            <div className="flex items-center gap-2 px-4 py-2 border-b border-[#1a1a1a] flex-shrink-0">
              <button onClick={() => setZoom(z => Math.max(0.25, z - 0.25))} className="p-1 rounded text-[#6b7280] hover:text-[#f9f9f9]"><ZoomOut size={14} /></button>
              <span className="text-xs text-[#6b7280] w-12 text-center">{Math.round(zoom * 100)}%</span>
              <button onClick={() => setZoom(z => Math.min(4, z + 0.25))} className="p-1 rounded text-[#6b7280] hover:text-[#f9f9f9]"><ZoomIn size={14} /></button>
              <button onClick={() => setZoom(1)} className="text-xs text-[#6b7280] hover:text-[#f9f9f9] ml-1">Reset</button>
            </div>
            <div className="flex-1 overflow-auto flex items-start justify-center p-4 bg-[#0a0a0a]">
              <img src={viewUrl} alt={drawing.title}
                style={{ transform: `scale(${zoom})`, transformOrigin: "top center", transition: "transform 0.15s" }}
                className="max-w-full rounded border border-[#1a1a1a]"
                onError={e => {
                  (e.target as HTMLImageElement).src = `data:image/svg+xml,${encodeURIComponent(
                    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 200" style="background:#0f0f0f"><text x="200" y="100" text-anchor="middle" fill="#6b7280" font-size="14">Preview unavailable</text></svg>`
                  )}`;
                }}
              />
            </div>
          </div>
        )}

        {tab === "analytics" && (
          <div className="h-full overflow-y-auto p-5 space-y-5">
            <div className="flex items-center justify-between">
              <p className="text-sm font-semibold text-[#f9f9f9]">Site Analytics</p>
              <button onClick={loadAnalytics} disabled={loadingAnalytics}
                className="flex items-center gap-1.5 text-xs text-amber-400 hover:text-amber-300">
                {loadingAnalytics ? <Loader2 size={12} className="animate-spin" /> : <RefreshCw size={12} />}Refresh
              </button>
            </div>
            {loadingAnalytics && <div className="flex items-center gap-2 text-sm text-[#6b7280]"><Loader2 size={14} className="animate-spin" />Loading…</div>}
            {analytics && !loadingAnalytics && (
              <>
                <div className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-lg p-4">
                  <p className="text-xs text-[#6b7280] mb-2">Site Risk Score</p>
                  <div className="flex items-end gap-3">
                    <span className={clsx("text-4xl font-black",
                      analytics.risk_score >= 60 ? "text-red-400" : analytics.risk_score >= 30 ? "text-amber-400" : "text-emerald-400")}>
                      {analytics.risk_score}
                    </span>
                    <span className="text-sm text-[#6b7280] mb-1">/ 100</span>
                  </div>
                  <div className="mt-2 h-2 bg-[#2a2a2a] rounded-full overflow-hidden">
                    <div className={clsx("h-full rounded-full transition-all",
                      analytics.risk_score >= 60 ? "bg-red-500" : analytics.risk_score >= 30 ? "bg-amber-500" : "bg-emerald-500")}
                      style={{ width: `${analytics.risk_score}%` }} />
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <MetricCard icon={<AlertTriangle size={16} />} label="Total Incidents"
                    value={analytics.incident_count} sub={`${analytics.open_incident_count} open`}
                    color="text-red-400" bg="bg-red-500/10 border-red-500/20" />
                  <MetricCard icon={<ShieldAlert size={16} />} label="Active PTWs"
                    value={analytics.active_ptw_count} sub={`${analytics.total_ptw_count} total`}
                    color="text-amber-400" bg="bg-amber-500/10 border-amber-500/20" />
                  <MetricCard icon={<Wrench size={16} />} label="Open Work Orders"
                    value={analytics.open_wo_count}
                    color="text-blue-400" bg="bg-blue-500/10 border-blue-500/20" />
                  <MetricCard icon={<ClipboardList size={16} />} label="Open Inspections"
                    value={analytics.open_inspection_count}
                    color="text-purple-400" bg="bg-purple-500/10 border-purple-500/20" />
                </div>
                {analytics.high_severity_incidents > 0 && (
                  <div className="flex items-center gap-2 bg-red-500/10 border border-red-500/30 rounded-lg p-3">
                    <AlertTriangle size={14} className="text-red-400 flex-shrink-0" />
                    <p className="text-xs text-red-300">
                      <span className="font-bold">{analytics.high_severity_incidents}</span> high-severity incident(s) (P1/P2).
                    </p>
                  </div>
                )}
                {analytics.last_incident_date && (
                  <p className="text-xs text-[#6b7280]">Last incident: {analytics.last_incident_date}</p>
                )}
              </>
            )}
          </div>
        )}

        {tab === "info" && (
          <div className="h-full overflow-y-auto p-5 space-y-4">
            <div className="grid grid-cols-2 gap-3 text-sm">
              {[
                ["Drawing Number", drawing.drawing_number],
                ["Revision",       drawing.revision],
                ["Type",           TYPE_LABEL[drawing.drawing_type] ?? drawing.drawing_type],
                ["Discipline",     drawing.discipline ?? "—"],
                ["Format",         drawing.file_format.toUpperCase()],
                ["File Size",      drawing.file_size ? `${(drawing.file_size / 1024).toFixed(1)} KB` : "—"],
                ["Project",        drawing.project_id ?? "—"],
                ["Plant/Site",     drawing.plant_id ?? "—"],
                ["Uploaded by",    drawing.created_by ?? "—"],
                ["Created",        new Date(drawing.created_at).toLocaleString()],
              ].map(([k, v]) => (
                <div key={k}><p className="text-xs text-[#6b7280]">{k}</p><p className="text-[#a0a0a0]">{v}</p></div>
              ))}
            </div>
            {drawing.description && (
              <div><p className="text-xs text-[#6b7280] mb-1">Description</p><p className="text-sm text-[#a0a0a0]">{drawing.description}</p></div>
            )}
            {drawing.tags.length > 0 && (
              <div className="flex flex-wrap gap-1">
                {drawing.tags.map(t => <span key={t} className="text-xs px-2 py-0.5 rounded bg-[#1f1f1f] border border-[#2a2a2a] text-[#6b7280]">{t}</span>)}
              </div>
            )}
            {drawing.extraction_error && (
              <div className="bg-red-500/10 border border-red-500/30 rounded p-3 text-xs text-red-300">Extraction error: {drawing.extraction_error}</div>
            )}
          </div>
        )}
      </div>

      {confirmDelete && (
        <div className="absolute inset-0 bg-black/70 flex items-center justify-center z-10 rounded-xl">
          <div className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl p-6 w-80">
            <p className="text-sm font-semibold text-[#f9f9f9] mb-1">Delete drawing?</p>
            <p className="text-xs text-[#6b7280] mb-4">{drawing.title} — this cannot be undone.</p>
            <div className="flex gap-2">
              <button onClick={() => setConfirmDelete(false)} className="flex-1 py-2 text-sm rounded border border-[#333] text-[#a0a0a0] hover:text-[#f9f9f9]">Cancel</button>
              <button onClick={handleDelete} disabled={deleting}
                className="flex-1 py-2 text-sm rounded bg-red-500/20 border border-red-500/40 text-red-400 flex items-center justify-center gap-1">
                {deleting && <Loader2 size={13} className="animate-spin" />}Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function UploadModal({ tree, onClose, onUploaded }: {
  tree: ProjectTree[]; onClose: () => void; onUploaded: (d: EngDrawing) => void;
}) {
  const [dragOver, setDragOver] = useState(false);
  const [file, setFile]         = useState<File | null>(null);
  const fileInputRef            = useRef<HTMLInputElement>(null);
  const [form, setForm] = useState({
    drawing_number: "", title: "", revision: "A", drawing_type: "general",
    discipline: "", description: "", tags: "", project_id: "", plant_id: "",
  });
  const [uploading, setUploading] = useState(false);
  const [err, setErr]             = useState("");

  const setF = (k: string, v: string) => setForm(f => ({ ...f, [k]: v }));
  const selectedProject = tree.find(p => p.id === form.project_id);
  const plants = selectedProject?.plants ?? [];

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault(); setDragOver(false);
    const f = e.dataTransfer.files[0]; if (f) setFile(f);
  }, []);

  useEffect(() => {
    if (file && !form.drawing_number) setF("drawing_number", file.name.replace(/\.[^.]+$/, "").replace(/[_\s-]+/g, "-").toUpperCase().slice(0, 40));
    if (file && !form.title) setF("title", file.name.replace(/\.[^.]+$/, "").replace(/[_-]/g, " ").slice(0, 80));
  }, [file]);

  const submit = async () => {
    if (!file)                       { setErr("Please select a file"); return; }
    if (!form.drawing_number.trim()) { setErr("Drawing number is required"); return; }
    if (!form.title.trim())          { setErr("Title is required"); return; }
    setUploading(true); setErr("");
    try {
      const result = await uploadEngDrawing(file, {
        drawing_number: form.drawing_number.trim(), title: form.title.trim(),
        revision: form.revision || "A", drawing_type: form.drawing_type || "general",
        discipline:  form.discipline  || undefined, description: form.description || undefined,
        tags:        form.tags        || undefined, project_id:  form.project_id  || undefined,
        plant_id:    form.plant_id    || undefined,
      });
      onUploaded(result);
    } catch (e: unknown) { setErr(e instanceof Error ? e.message : "Upload failed"); }
    setUploading(false);
  };

  const inp = "w-full bg-[#111] border border-[#333] rounded-lg px-3 py-2 text-sm text-[#f9f9f9] focus:outline-none focus:border-amber-500/60 placeholder-[#444]";
  const sel = "w-full bg-[#111] border border-[#333] rounded-lg px-3 py-2 text-sm text-[#f9f9f9] focus:outline-none focus:border-amber-500/60";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
      <div className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl w-full max-w-2xl max-h-[92vh] overflow-y-auto">
        <div className="sticky top-0 bg-[#1a1a1a] border-b border-[#2a2a2a] px-6 py-4 flex items-center justify-between">
          <div>
            <p className="text-base font-bold text-[#f9f9f9]">Import Drawing</p>
            <p className="text-xs text-[#6b7280]">Supports PNG, JPG, PDF, SVG, DXF, DWG, STEP, IGES, IFC…</p>
          </div>
          <button onClick={onClose} className="text-[#6b7280] hover:text-[#f9f9f9]"><X size={18} /></button>
        </div>
        <div className="p-6 space-y-4">
          {/* Drop zone */}
          <div
            onDragOver={e => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            className={clsx("border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition-colors",
              dragOver ? "border-amber-500 bg-amber-500/5" : file ? "border-emerald-500/50 bg-emerald-500/5" : "border-[#333] hover:border-[#444]")}
          >
            <input ref={fileInputRef} type="file" className="hidden" onChange={e => { const f = e.target.files?.[0]; if (f) setFile(f); }}
              accept=".png,.jpg,.jpeg,.tiff,.tif,.bmp,.webp,.gif,.pdf,.svg,.dxf,.dwg,.step,.stp,.iges,.igs,.ifc,.dgn" />
            {file ? (
              <div className="flex items-center justify-center gap-3">
                <FileImage size={24} className="text-emerald-400" />
                <div className="text-left">
                  <p className="text-sm font-medium text-[#f9f9f9]">{file.name}</p>
                  <p className="text-xs text-[#6b7280]">{(file.size / 1024).toFixed(1)} KB</p>
                </div>
                <button onClick={e => { e.stopPropagation(); setFile(null); }} className="ml-2 text-[#6b7280] hover:text-red-400"><X size={14} /></button>
              </div>
            ) : (
              <>
                <UploadCloud size={28} className="mx-auto mb-2 text-[#4b5563]" />
                <p className="text-sm font-medium text-[#f9f9f9]">Drop your drawing here</p>
                <p className="text-xs text-[#6b7280] mt-1">or click to browse</p>
                <div className="mt-3 flex flex-wrap justify-center gap-1">
                  {SUPPORTED_FORMATS.flatMap(g => g.exts).map(e => (
                    <span key={e} className="text-xs px-1.5 py-0.5 rounded bg-[#1f1f1f] border border-[#2a2a2a] text-[#6b7280]">{e}</span>
                  ))}
                </div>
              </>
            )}
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-[#a0a0a0] mb-1">Project</label>
              <select className={sel} value={form.project_id}
                onChange={e => { setF("project_id", e.target.value); setF("plant_id", ""); }}>
                <option value="">— Select project —</option>
                {tree.filter(p => p.id !== "__unassigned__").map(p => <option key={p.id} value={p.id}>{p.code} — {p.name}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-[#a0a0a0] mb-1">Plant / Site</label>
              <select className={sel} value={form.plant_id} onChange={e => setF("plant_id", e.target.value)} disabled={plants.length === 0}>
                <option value="">— Select plant —</option>
                {plants.map(p => <option key={p.id} value={p.id}>{p.code} — {p.name}</option>)}
              </select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-[#a0a0a0] mb-1">Drawing Number<span className="text-red-400 ml-0.5">*</span></label>
              <input className={inp} value={form.drawing_number} onChange={e => setF("drawing_number", e.target.value)} placeholder="DRW-CDU-001" />
            </div>
            <div>
              <label className="block text-xs font-medium text-[#a0a0a0] mb-1">Revision</label>
              <input className={inp} value={form.revision} onChange={e => setF("revision", e.target.value)} placeholder="A" />
            </div>
          </div>
          <div>
            <label className="block text-xs font-medium text-[#a0a0a0] mb-1">Title<span className="text-red-400 ml-0.5">*</span></label>
            <input className={inp} value={form.title} onChange={e => setF("title", e.target.value)} placeholder="Crude Distillation Unit P&ID" />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-[#a0a0a0] mb-1">Drawing Type</label>
              <select className={sel} value={form.drawing_type} onChange={e => setF("drawing_type", e.target.value)}>
                {DRAWING_TYPES.map(t => <option key={t} value={t}>{TYPE_LABEL[t] ?? t}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-[#a0a0a0] mb-1">Discipline</label>
              <select className={sel} value={form.discipline} onChange={e => setF("discipline", e.target.value)}>
                <option value="">— Select —</option>
                {DISCIPLINES.map(d => <option key={d}>{d}</option>)}
              </select>
            </div>
          </div>
          <div>
            <label className="block text-xs font-medium text-[#a0a0a0] mb-1">Description</label>
            <textarea className={`${inp} resize-none h-16`} value={form.description} onChange={e => setF("description", e.target.value)} placeholder="Brief description…" />
          </div>
          <div>
            <label className="block text-xs font-medium text-[#a0a0a0] mb-1">Tags (comma-separated)</label>
            <input className={inp} value={form.tags} onChange={e => setF("tags", e.target.value)} placeholder="cdu, startup, pid" />
          </div>

          {err && <p className="text-xs text-red-400">{err}</p>}
          <div className="flex gap-3 pt-2">
            <button onClick={onClose} className="flex-1 py-2 text-sm rounded-lg border border-[#333] text-[#a0a0a0] hover:text-[#f9f9f9]">Cancel</button>
            <button onClick={submit} disabled={uploading}
              className="flex-1 py-2 text-sm rounded-lg bg-amber-500/20 border border-amber-500/40 text-amber-400 hover:bg-amber-500/30 flex items-center justify-center gap-2">
              {uploading ? <Loader2 size={13} className="animate-spin" /> : <UploadCloud size={13} />}
              {uploading ? "Uploading…" : "Import Drawing"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function DrawingCard({ drawing, onClick }: { drawing: EngDrawing; onClick: () => void }) {
  const fmtCls  = FORMAT_COLOR[drawing.file_format] ?? "text-[#a0a0a0] bg-[#1a1a1a] border-[#2a2a2a]";
  const extrCls = EXTR_COLOR[drawing.extraction_status] ?? "";
  const analytics = drawing.analytics;

  return (
    <div className="group bg-[#1f1f1f] border border-[#2a2a2a] rounded-lg hover:border-amber-500/40 transition-colors cursor-pointer overflow-hidden" onClick={onClick}>
      <div className="relative h-36 bg-[#111] overflow-hidden flex items-center justify-center">
        {(drawing.has_svg || ["svg","png","jpg","tiff","bmp","webp","gif"].includes(drawing.file_format)) ? (
          <img src={`${API}/api/v1/drawings/${drawing.id}/view`} alt={drawing.title}
            className="w-full h-full object-contain"
            onError={e => { (e.target as HTMLImageElement).style.display = "none"; }} />
        ) : (
          <div className="flex flex-col items-center gap-2 text-[#374151]">
            <FileImage size={32} />
            <p className="text-xs">{drawing.extraction_status === "processing" ? "Extracting…" : "Preview pending"}</p>
          </div>
        )}
        {drawing.extraction_status === "processing" && (
          <div className="absolute inset-0 flex items-center justify-center bg-black/50">
            <Loader2 size={20} className="animate-spin text-amber-400" />
          </div>
        )}
        <div className="absolute top-2 left-2">
          <span className={clsx("text-xs px-1.5 py-0.5 rounded border font-bold", fmtCls)}>{drawing.file_format.toUpperCase()}</span>
        </div>
      </div>
      <div className="p-3 space-y-2">
        <div>
          <p className="text-sm font-semibold text-[#f9f9f9] truncate">{drawing.title}</p>
          <p className="text-xs text-[#6b7280]">{drawing.drawing_number} · Rev {drawing.revision}</p>
        </div>
        <div className="flex flex-wrap gap-1">
          <Pill label={TYPE_LABEL[drawing.drawing_type] ?? drawing.drawing_type} cls="text-blue-400 bg-blue-500/10 border-blue-500/20" />
          {drawing.discipline && <Pill label={drawing.discipline} cls="text-purple-400 bg-purple-500/10 border-purple-500/20" />}
          <Pill label={drawing.extraction_status} cls={extrCls} />
        </div>
        {analytics && (
          <div className="flex gap-2 pt-1">
            {analytics.incident_count > 0 && <span className="flex items-center gap-1 text-xs text-red-400"><AlertTriangle size={10}/>{analytics.incident_count}</span>}
            {analytics.active_ptw_count > 0 && <span className="flex items-center gap-1 text-xs text-amber-400"><ShieldAlert size={10}/>{analytics.active_ptw_count}</span>}
            {analytics.open_wo_count > 0 && <span className="flex items-center gap-1 text-xs text-blue-400"><Wrench size={10}/>{analytics.open_wo_count}</span>}
            {analytics.risk_score > 0 && (
              <span className={clsx("flex items-center gap-1 text-xs",
                analytics.risk_score >= 60 ? "text-red-400" : analytics.risk_score >= 30 ? "text-amber-400" : "text-emerald-400")}>
                <Activity size={10}/>{analytics.risk_score}
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default function DrawingsPage() {
  const { drawings: drawingsState, updateDrawings } = usePageState();
  const [drawings, setDrawings]     = useState<EngDrawing[]>([]);
  const [tree, setTree]             = useState<ProjectTree[]>([]);
  const [loading, setLoading]       = useState(true);
  const [search, _setSearch]        = useState(drawingsState.search);
  const setSearch = (s: string) => { _setSearch(s); updateDrawings({ search: s }); };
  const [selected, setSelected]     = useState<EngDrawing | null>(null);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [toast, setToast]           = useState<{ msg: string; ok: boolean } | null>(null);
  const [scopeProjectId, _setScopeProjectId] = useState<string | undefined>(drawingsState.scopeProjectId);
  const [scopePlantId,   _setScopePlantId]   = useState<string | undefined>(drawingsState.scopePlantId);
  const [expanded, _setExpanded] = useState<Set<string>>(new Set(drawingsState.expandedProjectIds));

  const notify = (msg: string, ok = true) => setToast({ msg, ok });
  const treeRef = useRef<ProjectTree[]>([]);

  const load = async () => {
    setLoading(true);
    try {
      const [ds, t] = await Promise.all([
        listEngDrawings(scopeProjectId, scopePlantId),
        treeRef.current.length ? Promise.resolve(treeRef.current) : getDrawingsTree(),
      ]);
      setDrawings(ds);
      if (!treeRef.current.length) { treeRef.current = t; setTree(t); }
    } catch { /* ignore */ }
    setLoading(false);
  };

  useEffect(() => { load(); }, [scopeProjectId, scopePlantId]);

  const toggleProject = (id: string) => {
    const n = new Set(expanded);
    n.has(id) ? n.delete(id) : n.add(id);
    _setExpanded(n);
    updateDrawings({ expandedProjectIds: Array.from(n) });
  };
  const selectScope = (pj?: string, pl?: string) => {
    _setScopeProjectId(pj);
    _setScopePlantId(pl);
    updateDrawings({ scopeProjectId: pj, scopePlantId: pl });
  };

  const filtered = drawings.filter(d => {
    const q = search.toLowerCase();
    return !q || d.title.toLowerCase().includes(q) || d.drawing_number.toLowerCase().includes(q) || d.file_format.includes(q);
  });

  return (
    <div className="flex h-screen overflow-hidden bg-[#0f0f0f]">
      {/* Left navigator */}
      <div className="w-56 flex-shrink-0 border-r border-[#1a1a1a] overflow-y-auto flex flex-col">
        <div className="px-4 pt-5 pb-3 border-b border-[#1a1a1a]">
          <p className="text-xs font-semibold text-[#6b7280] uppercase tracking-wider">Drawings</p>
        </div>
        <button onClick={() => selectScope()} className={clsx(
          "flex items-center gap-2 px-4 py-2 text-sm w-full text-left",
          !scopeProjectId && !scopePlantId ? "text-amber-400 bg-amber-500/10" : "text-[#a0a0a0] hover:text-[#f9f9f9] hover:bg-[#1a1a1a]")}>
          <Layers size={14} /><span className="flex-1">All Drawings</span>
          <span className="text-xs text-[#4b5563]">{drawings.length}</span>
        </button>
        {tree.map(project => {
          const isExpanded = expanded.has(project.id);
          const isSelected = scopeProjectId === project.id && !scopePlantId;
          return (
            <div key={project.id}>
              <button className={clsx(
                "flex items-center gap-2 px-4 py-2 text-sm w-full text-left",
                isSelected ? "text-amber-400 bg-amber-500/10" : "text-[#a0a0a0] hover:text-[#f9f9f9] hover:bg-[#1a1a1a]")}
                onClick={() => { toggleProject(project.id); selectScope(project.id === "__unassigned__" ? undefined : project.id); }}>
                {isExpanded ? <ChevronDown size={12} className="flex-shrink-0" /> : <ChevronRight size={12} className="flex-shrink-0" />}
                <FolderOpen size={13} className="flex-shrink-0" />
                <span className="flex-1 truncate text-xs">{project.name}</span>
              </button>
              {isExpanded && project.plants.map(plant => (
                <button key={plant.id} onClick={() => selectScope(project.id, plant.id)}
                  className={clsx("flex items-center gap-2 pl-10 pr-4 py-1.5 text-xs w-full text-left",
                    scopePlantId === plant.id ? "text-amber-400 bg-amber-500/5" : "text-[#6b7280] hover:text-[#f9f9f9] hover:bg-[#1a1a1a]")}>
                  <Building2 size={11} className="flex-shrink-0" />
                  <span className="flex-1 truncate">{plant.name}</span>
                  <span className="text-[#374151] text-xs">{plant.drawing_count}</span>
                </button>
              ))}
            </div>
          );
        })}
      </div>

      {/* Main content */}
      <div className="flex-1 overflow-y-auto flex flex-col">
        <div className="flex-shrink-0 flex items-center justify-between px-6 py-4 border-b border-[#1a1a1a]">
          <div>
            <h1 className="text-xl font-bold text-[#f9f9f9] flex items-center gap-2">
              <FileImage size={20} className="text-amber-500" />
              {scopePlantId
                ? tree.flatMap(p => p.plants).find(pl => pl.id === scopePlantId)?.name ?? "Plant Drawings"
                : scopeProjectId
                ? tree.find(p => p.id === scopeProjectId)?.name ?? "Project Drawings"
                : "All Engineering Drawings"}
            </h1>
            <p className="text-xs text-[#6b7280] mt-0.5">{filtered.length} drawing{filtered.length !== 1 ? "s" : ""} · Click to view &amp; inspect analytics</p>
          </div>
          <div className="flex items-center gap-2">
            <div className="relative">
              <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-[#6b7280]" />
              <input className="bg-[#1a1a1a] border border-[#2a2a2a] rounded-lg pl-8 pr-3 py-1.5 text-sm text-[#f9f9f9] placeholder-[#4b5563] focus:outline-none focus:border-amber-500/50 w-48"
                placeholder="Search drawings…" value={search} onChange={e => setSearch(e.target.value)} />
            </div>
            <button onClick={load} className="p-2 rounded-lg border border-[#2a2a2a] text-[#6b7280] hover:text-[#f9f9f9] hover:bg-[#1a1a1a]" title="Refresh"><RefreshCw size={14} /></button>
            <button onClick={() => setUploadOpen(true)}
              className="flex items-center gap-2 px-3 py-2 rounded-lg bg-amber-500/20 border border-amber-500/40 text-amber-400 hover:bg-amber-500/30 text-sm font-medium">
              <Plus size={14} />Import Drawing
            </button>
          </div>
        </div>

        <div className="flex-shrink-0 px-6 py-2 border-b border-[#1a1a1a] bg-[#111] flex flex-wrap items-center gap-x-4 gap-y-1">
          <span className="text-xs text-[#6b7280] font-medium">Supported formats:</span>
          {SUPPORTED_FORMATS.map(g => (
            <span key={g.group} className="text-xs text-[#4b5563]">
              <span className="text-[#6b7280] mr-1">{g.group}:</span>{g.exts.join(", ")}
            </span>
          ))}
        </div>

        <div className="flex-1 p-5">
          {loading ? (
            <div className="flex items-center justify-center py-24 text-[#6b7280]"><Loader2 size={20} className="animate-spin mr-2" />Loading drawings…</div>
          ) : filtered.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-24 text-center">
              <FileImage size={48} className="text-[#2a2a2a] mb-4" />
              <p className="text-[#6b7280] text-sm mb-1">{search ? "No drawings match your search" : "No drawings imported yet"}</p>
              {!search && (
                <button onClick={() => setUploadOpen(true)} className="mt-3 text-sm text-amber-400 hover:underline flex items-center gap-1">
                  <UploadCloud size={14} />Import your first drawing
                </button>
              )}
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
              {filtered.map(d => <DrawingCard key={d.id} drawing={d} onClick={() => setSelected(d)} />)}
            </div>
          )}
        </div>
      </div>

      {selected && (
        <DrawingViewer drawing={selected} onClose={() => setSelected(null)}
          onDeleted={() => { setSelected(null); load(); notify("Drawing deleted"); }}
          onRefresh={() => { load(); setSelected(null); }} />
      )}
      {uploadOpen && (
        <UploadModal tree={tree} onClose={() => setUploadOpen(false)}
          onUploaded={d => { setUploadOpen(false); notify(`"${d.title}" imported — extracting…`); load(); }} />
      )}
      {toast && <Toast msg={toast.msg} ok={toast.ok} onDone={() => setToast(null)} />}
    </div>
  );
}
