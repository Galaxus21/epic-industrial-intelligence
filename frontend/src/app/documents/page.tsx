/**
 * AI Operations Brain — Documents Page
 * Upload a document → shows live pipeline steps → displays extracted entities.
 * Polls GET /api/v1/documents/{id} every 1.5 s until status transitions
 * from "processing" to "processed" or "failed".
 */
"use client";

import { useEffect, useState, useRef } from "react";
import { listDocuments, uploadDocument, checkDuplicateDocument, deleteDocument, errorText } from "@/lib/api";
import type { Document, PipelineStepStatus } from "@/lib/types";
import { Badge } from "@/components/ui/Badge";
import { DocumentModal } from "@/components/ui/DocumentModal";
import { CreateDocumentModal } from "@/components/ui/CreateDocumentModal";
import { HeldEntitiesNotice } from "@/components/ui/HeldEntitiesNotice";
import { usePageState } from "@/lib/page-state";
import { approverRoles, hasRole } from "@/lib/roles";
import { useCurrentUser } from "@/lib/user-context";
import {
  FileText, Upload, CheckCircle2, Loader2, AlertCircle,
  ChevronDown, ChevronUp, Network, Tag, BookOpen, Trash2, FilePlus,
} from "lucide-react";
import { toast } from "sonner";
import clsx from "clsx";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "";

const TYPE_BADGE: Record<string, "info" | "success" | "warning" | "muted" | "high"> = {
  manual: "info",
  sop: "success",
  regulation: "warning",
  inspection_report: "muted",
  commissioning: "info",
  drawing: "warning",
  cad: "info",
  incident_report: "high",
  standard: "muted",
  uploaded: "muted",
  other: "muted",
};

const PIPELINE_STEPS: { key: string; label: string; description: string; skippedLabel?: string }[] = [
  { key: "saved",     label: "File Saved",              description: "Written to storage" },
  { key: "extracted", label: "Text Extracted",           description: "OCR / parser ran" },
  { key: "entities",  label: "Entities Extracted",       description: "LLM identifies equipment, people, regulations" },
  { key: "graph",     label: "Knowledge Graph Updated",  description: "New nodes linked to equipment" },
  { key: "indexed",   label: "Vector Index Updated",     description: "Ready for semantic search", skippedLabel: "Vector Index Skipped" },
];

interface UploadedDoc {
  id: string;
  name: string;
  type: string;
  status: "processing" | "processed" | "failed";
  current_step: string;
  steps: Record<string, PipelineStepStatus>;
  step_detail?: string;
  entities: null | {
    equipment_ids: string[];
    incident_ids: string[];
    people: string[];
    regulations: string[];
    symptoms: string[];
    measurements: string[];
    document_type: string;
    summary: string;
  };
  error: string | null;
  char_count?: number;
  entities_pending_review?: boolean;
  pending_review_note?: string | null;
  held_entities?: string[];
  unresolved_equipment_ids?: string[];
}

// ── Component: live pipeline progress card ───────────────────────────────────
function PipelineCard({ doc, onView }: { doc: UploadedDoc; onView: () => void }) {
  const isDone = doc.status === "processed";
  const isFail = doc.status === "failed";
  const [showEntities, setShowEntities] = useState(false);

  return (
    <div className={clsx(
      "border rounded-xl p-4 transition-all",
      isDone ? "bg-[#1f1f1f] border-emerald-500/30" :
      isFail ? "bg-[#1f1f1f] border-red-500/30" :
               "bg-[#1f1f1f] border-amber-500/20",
    )}>
      {/* Header */}
      <div className="flex items-center gap-3 mb-3">
        {isDone ? <CheckCircle2 size={16} className="text-emerald-400 flex-shrink-0" /> :
         isFail ? <AlertCircle size={16} className="text-red-400 flex-shrink-0" /> :
                  <Loader2 size={16} className="text-amber-400 animate-spin flex-shrink-0" />}
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-[#f9f9f9] truncate">{doc.name}</p>
          <p className="text-xs text-[#6b7280]">
            {isDone ? `Processed · ${doc.type}` :
             isFail ? `Failed: ${doc.error}` :
                      "Processing…"}
          </p>
        </div>
        {isDone && <Badge variant="low">Done</Badge>}
        {isDone && (
          <button onClick={onView} className="text-xs text-purple-400 hover:text-purple-300 transition-colors flex-shrink-0">
            View →
          </button>
        )}
        {isFail && <Badge variant="critical">Failed</Badge>}
      </div>

      {/* Pipeline steps */}
      <div className="flex items-center gap-1 mb-3 overflow-x-auto pb-1">
        {PIPELINE_STEPS.map((step, i) => {
          const stepStatus = doc.steps?.[step.key] ?? "pending";
          const isSkipped = stepStatus === "skipped";
          const isActive = doc.current_step === step.key && !isDone;
          return (
            <div key={step.key} className="flex items-center gap-1 flex-shrink-0" title={isSkipped ? doc.step_detail : undefined}>
              <div className="flex flex-col items-center">
                <div className={clsx(
                  "w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold transition-all",
                  stepStatus === "done" ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/40" :
                  isActive             ? "bg-amber-500/20 text-amber-400 border border-amber-500/40 animate-pulse" :
                                         "bg-[#2a2a2a] text-[#4b5563] border border-[#333]",
                )}>
                  {stepStatus === "done" ? "✓" : isSkipped ? "–" : isActive ? <Loader2 size={10} className="animate-spin" /> : i + 1}
                </div>
                <p className={clsx(
                  "text-xs mt-1 text-center w-14 leading-tight",
                  stepStatus === "done" ? "text-emerald-400" :
                  isActive             ? "text-amber-400" :
                                         "text-[#6b7280]",
                )}>{isSkipped ? step.skippedLabel ?? "Skipped" : step.label}</p>
              </div>
              {i < PIPELINE_STEPS.length - 1 && (
                <div className={clsx(
                  "w-4 h-px flex-shrink-0 mb-4",
                  stepStatus === "done" ? "bg-emerald-500/40" : "bg-[#2a2a2a]"
                )} />
              )}
            </div>
          );
        })}
      </div>

      {/* Extracted entities (shown after completion) */}
      {isDone && doc.entities && (
        <div className="mt-2 border-t border-[#2a2a2a] pt-3">
          <button
            onClick={() => setShowEntities(e => !e)}
            className="flex items-center gap-2 text-xs text-[#a0a0a0] hover:text-amber-400 transition-colors w-full"
          >
            <Tag size={12} />
            <span className="font-medium">Extracted Entities</span>
            <span className="text-[#4b5563] ml-1">
              ({(doc.entities.equipment_ids || []).length} equipment, {(doc.entities.regulations || []).length} regulations)
            </span>
            <span className="ml-auto">{showEntities ? <ChevronUp size={12} /> : <ChevronDown size={12} />}</span>
          </button>

          {showEntities && (
            <div className="mt-3 space-y-2">
              <HeldEntitiesNotice doc={doc} />
              {doc.entities.summary && (
                <p className="text-xs text-[#a0a0a0] italic bg-[#1a1a1a] rounded p-2 border border-[#2a2a2a]">
                  {doc.entities.summary}
                </p>
              )}
              {[
                { label: "Equipment Tags", items: doc.entities.equipment_ids || [], color: "text-amber-400", bg: "bg-amber-500/10" },
                { label: "Incident Refs",  items: doc.entities.incident_ids  || [], color: "text-red-400",   bg: "bg-red-500/10" },
                { label: "Regulations",   items: doc.entities.regulations   || [], color: "text-teal-400",  bg: "bg-teal-500/10" },
                { label: "Measurements",  items: doc.entities.measurements  || [], color: "text-blue-400",  bg: "bg-blue-500/10" },
                { label: "People",        items: doc.entities.people        || [], color: "text-purple-400",bg: "bg-purple-500/10" },
              ].filter(g => g.items.length > 0).map(group => (
                <div key={group.label}>
                  <p className="text-xs text-[#6b7280] mb-1">{group.label}</p>
                  <div className="flex flex-wrap gap-1">
                    {group.items.map(item => (
                      <span key={item} className={`text-xs px-2 py-0.5 rounded-full font-mono ${group.bg} ${group.color}`}>
                        {item}
                      </span>
                    ))}
                  </div>
                </div>
              ))}
              {doc.entities_pending_review ? (
                <div className="flex items-center gap-2 mt-2 text-xs text-amber-400">
                  <AlertCircle size={10} />
                  <span>Entities held for review — graph registration pending</span>
                </div>
              ) : (
                <div className="flex items-center gap-2 mt-2 text-xs text-emerald-400">
                  <Network size={10} />
                  <span>Knowledge graph updated — entities linked to existing equipment nodes</span>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

async function computeFileHash(file: File): Promise<string> {
  const buf = await file.arrayBuffer();
  const hashBuf = await crypto.subtle.digest("SHA-256", buf);
  return Array.from(new Uint8Array(hashBuf)).map(b => b.toString(16).padStart(2, "0")).join("");
}

type DuplicateMatch = { id: string; name: string; type: string; date: string; match_reason: string };

// ── Main page ────────────────────────────────────────────────────────────────
export default function DocumentsPage() {
  const { documents: docsState, updateDocuments } = usePageState();
  const [docs, setDocs] = useState<Document[]>([]);
  const [processing, setProcessing] = useState<UploadedDoc[]>([]);
  const [uploading, setUploading] = useState(false);
  const [dragActive, setDragActive] = useState(false);
  const [selectedDocId, _setSelectedDocId] = useState<string | null>(docsState.selectedDocId);
  const setSelectedDocId = (id: string | null) => { _setSelectedDocId(id); updateDocuments({ selectedDocId: id }); };
  const [dupWarning, setDupWarning] = useState<{ file: File; matches: DuplicateMatch[] } | null>(null);
  const [deletingDocId, setDeletingDocId] = useState<string | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [delDocLoading, setDelDocLoading] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const { currentUser } = useCurrentUser();
  const canDelete = hasRole(currentUser?.role, approverRoles);
  const pollRefs = useRef<Map<string, ReturnType<typeof setInterval>>>(new Map());

  const loadDocs = () => listDocuments().then(setDocs).catch(console.error);
  useEffect(() => { loadDocs(); return () => { pollRefs.current.forEach(t => clearInterval(t)); }; }, []);

  const pollDocument = (docId: string) => {
    if (pollRefs.current.has(docId)) return;
    const timer = setInterval(async () => {
      try {
        const res = await fetch(`${BASE}/api/v1/documents/${docId}`);
        if (!res.ok) return;
        const data: UploadedDoc = await res.json();
        setProcessing(prev => prev.map(d => d.id === docId ? data : d));
        if (data.status !== "processing") {
          clearInterval(timer);
          pollRefs.current.delete(docId);
          if (data.status === "processed") {
            toast.success(`${data.name} — processed successfully`);
            loadDocs();
          } else {
            toast.error(`${data.name} — processing failed`);
          }
        }
      } catch { /* ignore transient */ }
    }, 1500);
    pollRefs.current.set(docId, timer);
  };

  const handleUpload = async (file: File, force = false) => {
    if (!force) {
      try {
        const hash = await computeFileHash(file);
        const { matches } = await checkDuplicateDocument(file.name, hash);
        if (matches.length > 0) {
          setDupWarning({ file, matches });
          return;
        }
      } catch { /* ignore check errors — proceed with upload */ }
    }
    setUploading(true);
    try {
      const { doc_id } = await uploadDocument(file);
      const initial: UploadedDoc = {
        id: doc_id, name: file.name, type: "uploaded",
        status: "processing", current_step: "saved",
        steps: { saved: "pending", extracted: "pending", entities: "pending", graph: "pending", indexed: "pending" },
        entities: null, error: null,
      };
      setProcessing(prev => [initial, ...prev]);
      pollDocument(doc_id);
      toast.info(`${file.name} — pipeline started`);
    } catch (err) {
      toast.error(errorText(err, "Upload failed"));
    } finally {
      setUploading(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragActive(false);
    Array.from(e.dataTransfer.files).forEach(f => handleUpload(f));
  };

  const handleDeleteDoc = async (docId: string) => {
    setDelDocLoading(true);
    try {
      await deleteDocument(docId);
      setDeletingDocId(null);
      toast.success("Document and graph nodes removed");
      loadDocs();
    } catch (err) {
      toast.error(errorText(err, "Delete failed"));
    } finally {
      setDelDocLoading(false);
    }
  };

  const processedCount = processing.filter(d => d.status === "processed").length;
  const pendingCount   = processing.filter(d => d.status === "processing").length;

  return (
    <div className="p-6">
      <div className="flex items-start justify-between mb-6 gap-4">
        <div className="min-w-0">
          <h1 className="text-xl font-bold text-[#f9f9f9]">Document Intelligence</h1>
          <p className="text-sm text-[#6b7280] mt-1">
            Upload inspection reports, SOPs, incident reports and shift logs (PDF, DOCX, XLSX, PPTX, TXT, CSV, JSON), or create new documents with AI assistance.
          </p>
        </div>
        <button
          onClick={() => setShowCreateModal(true)}
          className="flex items-center gap-2 px-4 py-2 bg-amber-500/15 hover:bg-amber-500/25 text-amber-400 border border-amber-500/40 rounded-xl text-sm font-medium transition-colors flex-shrink-0"
        >
          <FilePlus size={15} />
          Create with AI
        </button>
      </div>

      {/* Drop zone */}
      <div
        onDrop={handleDrop}
        onDragOver={e => { e.preventDefault(); setDragActive(true); }}
        onDragLeave={() => setDragActive(false)}
        onClick={() => inputRef.current?.click()}
        className={clsx(
          "flex flex-col items-center justify-center gap-3 p-10 mb-6 border-2 border-dashed rounded-xl cursor-pointer transition-colors",
          dragActive ? "border-amber-500 bg-amber-500/5" : "border-[#333] bg-[#1f1f1f] hover:border-[#444]"
        )}
      >
        {uploading ? <Loader2 size={32} className="text-amber-500 animate-spin" /> : <Upload size={32} className="text-[#4b5563]" />}
        <p className="text-xs text-[#6b7280]">PDF, DOCX, XLSX, PPTX, TXT, CSV, JSON — max 50 MB</p>
        <input ref={inputRef} type="file" className="hidden" multiple
          accept=".pdf,.docx,.xlsx,.pptx,.txt,.csv,.json"
          onChange={e => Array.from(e.target.files ?? []).forEach(f => handleUpload(f))} />
      </div>

      {/* Duplicate warning banner */}
      {dupWarning && (
        <div className="mb-6 p-4 bg-amber-500/10 border border-amber-500/40 rounded-xl">
          <div className="flex items-start gap-3">
            <AlertCircle size={16} className="text-amber-400 flex-shrink-0 mt-0.5" />
            <div className="flex-1 min-w-0">
              <p className="text-sm font-semibold text-amber-400">Possible duplicate detected</p>
              <p className="text-xs text-[#a0a0a0] mt-1 mb-3">
                <span className="font-mono text-[#f9f9f9]">&ldquo;{dupWarning.file.name}&rdquo;</span>
                {" matches "}
                {dupWarning.matches.length === 1 ? "an existing document" : `${dupWarning.matches.length} existing documents`}:
              </p>
              <div className="space-y-1.5 mb-4">
                {dupWarning.matches.map(m => (
                  <div key={m.id} className="flex items-center gap-2 text-xs bg-[#1a1a1a] px-2 py-1.5 rounded-lg border border-[#2a2a2a]">
                    <FileText size={11} className="text-[#6b7280] flex-shrink-0" />
                    <span className="text-[#f9f9f9] truncate flex-1">{m.name}</span>
                    <Badge variant={TYPE_BADGE[m.type] ?? "muted"}>{m.type}</Badge>
                    <span className="text-[#4b5563]">{m.date}</span>
                    <span className="text-amber-400/70 flex-shrink-0 text-[10px]">
                      {m.match_reason === "content" ? "same content" : "same filename"}
                    </span>
                  </div>
                ))}
              </div>
              <div className="flex gap-2">
                <button
                  onClick={() => { const f = dupWarning.file; setDupWarning(null); handleUpload(f, true); }}
                  className="px-3 py-1.5 text-xs bg-amber-500/20 hover:bg-amber-500/30 text-amber-400 rounded-lg border border-amber-500/40 transition-colors"
                >
                  Upload anyway
                </button>
                <button
                  onClick={() => setDupWarning(null)}
                  className="px-3 py-1.5 text-xs bg-[#2a2a2a] hover:bg-[#333] text-[#a0a0a0] rounded-lg border border-[#333] transition-colors"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Pipeline steps legend */}
      <div className="flex items-center gap-2 mb-6 overflow-x-auto pb-1">
        {PIPELINE_STEPS.map((step, i) => (
          <div key={step.key} className="flex items-center gap-2 flex-shrink-0">
            <div className="flex items-center gap-1.5 px-3 py-1.5 bg-[#1f1f1f] border border-[#2a2a2a] rounded-full">
              <span className="text-xs text-[#4b5563]">{i + 1}.</span>
              <span className="text-xs text-[#6b7280]">{step.label}</span>
            </div>
            {i < PIPELINE_STEPS.length - 1 && <span className="text-[#4b5563] text-xs">→</span>}
          </div>
        ))}
      </div>

      {/* Active pipeline cards */}
      {processing.length > 0 && (
        <div className="mb-6">
          <div className="flex items-center gap-2 mb-3">
            <BookOpen size={14} className="text-amber-400" />
            <p className="text-sm font-semibold text-[#a0a0a0]">
              Processing Queue
              {pendingCount > 0 && <span className="ml-2 text-xs text-amber-400">({pendingCount} in progress)</span>}
              {processedCount > 0 && <span className="ml-2 text-xs text-emerald-400">({processedCount} done)</span>}
            </p>
          </div>
          <div className="space-y-3">
            {processing.map(d => <PipelineCard key={d.id} doc={d} onView={() => setSelectedDocId(d.id)} />)}
          </div>
        </div>
      )}

      {/* Existing documents list */}
      <div>
        <p className="text-sm font-semibold text-[#a0a0a0] mb-3">Knowledge Base Documents ({docs.length})</p>
        <div className="space-y-2">
          {docs.map(doc => (
            <div
              key={doc.id}
              className="flex items-center gap-2 p-3 bg-[#1f1f1f] border border-[#2a2a2a] rounded-lg hover:border-purple-500/40 hover:bg-[#242424] transition-all group"
            >
              <button
                onClick={() => setSelectedDocId(doc.id)}
                className="flex items-center gap-3 flex-1 min-w-0 text-left"
              >
                <FileText size={16} className="text-[#6b7280] flex-shrink-0 group-hover:text-purple-400 transition-colors" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-[#f9f9f9] truncate">{doc.name}</p>
                  <div className="flex items-center gap-2 mt-0.5 flex-wrap">
                    <Badge variant={TYPE_BADGE[doc.type] ?? "muted"}>{doc.type}</Badge>
                    {doc.equipment_ids?.map(e => (
                      <span key={e} className="text-xs text-amber-400 font-mono">{e}</span>
                    ))}
                    <span className="text-xs text-[#4b5563]">{doc.date}</span>
                  </div>
                </div>
                <span className="text-xs text-[#4b5563] group-hover:text-purple-400 transition-colors flex-shrink-0 mr-1">View →</span>
              </button>
              {deletingDocId === doc.id ? (
                <div className="flex items-center gap-1 flex-shrink-0">
                  <button
                    onClick={() => handleDeleteDoc(doc.id)}
                    disabled={delDocLoading}
                    className="px-2 py-1 text-xs bg-red-500/20 hover:bg-red-500/30 text-red-400 rounded border border-red-500/40 transition-colors disabled:opacity-50"
                  >
                    {delDocLoading ? <Loader2 size={10} className="animate-spin" /> : "Confirm"}
                  </button>
                  <button
                    onClick={() => setDeletingDocId(null)}
                    className="px-2 py-1 text-xs bg-[#2a2a2a] hover:bg-[#333] text-[#9ca3af] rounded border border-[#333] transition-colors"
                  >
                    Cancel
                  </button>
                </div>
              ) : canDelete && (
                <button
                  onClick={() => setDeletingDocId(doc.id)}
                  className="flex-shrink-0 p-1.5 text-[#4b5563] hover:text-red-400 hover:bg-red-500/10 rounded transition-colors opacity-0 group-hover:opacity-100"
                  title="Delete document and graph nodes"
                  aria-label={`Delete ${doc.name}`}
                >
                  <Trash2 size={13} />
                </button>
              )}
            </div>
          ))}
        </div>
      </div>

      <DocumentModal docId={selectedDocId} onClose={() => setSelectedDocId(null)} />

      {showCreateModal && (
        <CreateDocumentModal
          onClose={() => setShowCreateModal(false)}
          onSaved={() => { setShowCreateModal(false); loadDocs(); }}
        />
      )}
    </div>
  );
}

