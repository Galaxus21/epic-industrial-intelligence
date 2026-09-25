/**
 * EPIC — Document Modal
 * Slide-over panel that shows extracted data for any document.
 * Fetches GET /api/v1/documents/{id} on open.
 */
"use client";

import { useEffect, useState } from "react";
import {
  X, FileText, Tag, BookOpen, AlertCircle, Loader2, CheckCircle2,
  Users, ShieldAlert, Ruler, Wrench, ChevronDown, ChevronUp,
  AlertTriangle, Info,
} from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { HeldEntitiesNotice } from "@/components/ui/HeldEntitiesNotice";
import type { DocumentDetail } from "@/lib/types";
import { getDocument } from "@/lib/api";
import { useDialogFocus } from "@/lib/useDialogFocus";
import clsx from "clsx";

const TYPE_BADGE: Record<string, "info" | "success" | "warning" | "muted" | "high"> = {
  manual: "info",
  sop: "success",
  regulation: "warning",
  inspection_report: "muted",
  commissioning: "info",
  drawing: "warning",
  incident_report: "high",
  standard: "muted",
  uploaded: "muted",
  other: "muted",
};

// ── Entity group config ───────────────────────────────────────────────────────

const ENTITY_GROUPS = [
  { key: "equipment_ids" as const, label: "Equipment Tags",  icon: <Tag size={12} />,          color: "text-amber-400",  bg: "bg-amber-500/10",  border: "border-amber-500/20" },
  { key: "regulations"  as const, label: "Regulations",     icon: <ShieldAlert size={12} />,   color: "text-teal-400",   bg: "bg-teal-500/10",   border: "border-teal-500/20" },
  { key: "incident_ids" as const, label: "Incident Refs",   icon: <AlertTriangle size={12} />, color: "text-red-400",    bg: "bg-red-500/10",    border: "border-red-500/20" },
  { key: "measurements" as const, label: "Measurements",    icon: <Ruler size={12} />,         color: "text-blue-400",   bg: "bg-blue-500/10",   border: "border-blue-500/20" },
  { key: "people"       as const, label: "People",          icon: <Users size={12} />,         color: "text-purple-400", bg: "bg-purple-500/10", border: "border-purple-500/20" },
  { key: "symptoms"     as const, label: "Symptoms",        icon: <Wrench size={12} />,        color: "text-orange-400", bg: "bg-orange-500/10", border: "border-orange-500/20" },
] as const;

// ── Section viewer ────────────────────────────────────────────────────────────

function SectionItem({ sectionId, text }: { sectionId: string; text: string }) {
  const [expanded, setExpanded] = useState(false);
  const isLong = text.length > 200;

  return (
    <div className="border border-[#2a2a2a] rounded-lg overflow-hidden">
      <button
        onClick={() => setExpanded(e => !e)}
        className="w-full flex items-center gap-2 px-3 py-2 bg-[#1a1a1a] text-left hover:bg-[#222] transition-colors"
      >
        <span className="text-xs font-mono text-amber-400 flex-shrink-0 w-16">{sectionId}</span>
        <span className="text-xs text-[#a0a0a0] flex-1 truncate">{text.substring(0, 80)}{text.length > 80 ? "…" : ""}</span>
        {isLong && (expanded ? <ChevronUp size={12} className="text-[#4b5563] flex-shrink-0" /> : <ChevronDown size={12} className="text-[#4b5563] flex-shrink-0" />)}
      </button>
      {(expanded || !isLong) && (
        <div className="px-3 py-2 bg-[#111] border-t border-[#2a2a2a]">
          <p className="text-xs text-[#c0c0c0] leading-relaxed whitespace-pre-wrap">{text}</p>
        </div>
      )}
    </div>
  );
}

// ── Main modal ────────────────────────────────────────────────────────────────

interface DocumentModalProps {
  docId: string | null;
  onClose: () => void;
}

export function DocumentModal({ docId, onClose }: DocumentModalProps) {
  const [doc, setDoc] = useState<DocumentDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!docId) { setDoc(null); return; }
    setLoading(true);
    setError(null);
    getDocument(docId)
      .then((data: DocumentDetail) => setDoc(data))
      .catch(e => setError(e instanceof Error ? e.message : "Failed to load document"))
      .finally(() => setLoading(false));
  }, [docId]);

  const dialogRef = useDialogFocus<HTMLDivElement>(onClose, Boolean(docId));

  if (!docId) return null;

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/60 backdrop-blur-sm z-40"
        onClick={onClose}
      />

      {/* Slide-over panel */}
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="document-modal-title"
        tabIndex={-1}
        className="fixed inset-y-0 right-0 w-full max-w-2xl bg-[#0f0f0f] border-l border-[#2a2a2a] z-50 flex flex-col shadow-2xl overflow-hidden"
      >

        {/* Header */}
        <div className="flex items-center gap-3 px-5 py-4 border-b border-[#2a2a2a] flex-shrink-0">
          <FileText size={18} className="text-purple-400 flex-shrink-0" aria-hidden="true" />
          <div className="flex-1 min-w-0">
            {loading ? (
              <div className="h-4 w-48 bg-[#2a2a2a] rounded animate-pulse" />
            ) : (
              <p id="document-modal-title" className="text-sm font-semibold text-[#f9f9f9] truncate">{doc?.name ?? docId}</p>
            )}
            {doc && (
              <div className="flex items-center gap-2 mt-0.5">
                <Badge variant={TYPE_BADGE[doc.type] ?? "muted"}>{doc.type}</Badge>
                {doc.date && <span className="text-xs text-[#6b7280]">{doc.date}</span>}
                <span className="text-xs text-[#4b5563] font-mono">{doc.id}</span>
              </div>
            )}
          </div>
          <button
            onClick={onClose}
            aria-label="Close document panel"
            className="p-1.5 rounded-lg hover:bg-[#2a2a2a] transition-colors text-[#6b7280] hover:text-[#f9f9f9]"
          >
            <X size={16} />
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-5 space-y-6">

          {loading && (
            <div className="flex items-center justify-center py-20 gap-2 text-[#6b7280]">
              <Loader2 size={18} className="animate-spin" />
              <span className="text-sm">Loading document data…</span>
            </div>
          )}

          {error && (
            <div className="flex items-center gap-2 p-4 bg-red-500/10 border border-red-500/30 rounded-xl text-red-400">
              <AlertCircle size={16} />
              <span className="text-sm">Failed to load document: {error}</span>
            </div>
          )}

          {doc && !loading && (
            <>
              {/* Equipment links */}
              {(doc.equipment_ids?.length ?? 0) > 0 && (
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-xs text-[#6b7280]">Linked equipment:</span>
                  {doc.equipment_ids.map(eq => (
                    <a key={eq} href={`/equipment/${eq}`}
                      className="text-xs font-mono px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/20 hover:bg-amber-500/20 transition-colors">
                      {eq}
                    </a>
                  ))}
                </div>
              )}

              {/* Summary */}
              {(doc.entities?.summary || doc.summary) && (
                <div className="p-3 bg-[#1a1a1a] border border-[#2a2a2a] rounded-xl">
                  <div className="flex items-center gap-1.5 mb-2">
                    <Info size={12} className="text-blue-400" />
                    <span className="text-xs font-semibold text-blue-400">Summary</span>
                  </div>
                  <p className="text-xs text-[#c0c0c0] leading-relaxed italic">
                    {doc.entities?.summary ?? doc.summary}
                  </p>
                </div>
              )}

              <HeldEntitiesNotice doc={doc} />

              {/* Char count / processing stats */}
              {doc.char_count != null && (
                <div className="flex items-center gap-2 text-xs text-[#6b7280]">
                  <CheckCircle2 size={12} className="text-emerald-400" />
                  <span>{doc.char_count.toLocaleString()} characters extracted · status: {doc.status}</span>
                </div>
              )}

              {/* Extracted Entities */}
              {doc.entities && (
                <section>
                  <div className="flex items-center gap-2 mb-3">
                    <Tag size={14} className="text-amber-400" />
                    <h2 className="text-sm font-semibold text-[#f9f9f9]">Extracted Entities</h2>
                  </div>
                  <div className="space-y-3">
                    {ENTITY_GROUPS.map(({ key, label, icon, color, bg, border }) => {
                      const items = doc.entities![key] as string[] | undefined;
                      if (!items?.length) return null;
                      return (
                        <div key={key}>
                          <div className="flex items-center gap-1.5 mb-1.5">
                            <span className={color}>{icon}</span>
                            <span className={`text-xs font-semibold ${color}`}>{label}</span>
                            <span className="text-xs text-[#4b5563] ml-1">({items.length})</span>
                          </div>
                          <div className="flex flex-wrap gap-1.5 pl-4">
                            {items.map(item => (
                              <span key={item} className={clsx(
                                "text-xs px-2 py-0.5 rounded-full font-mono border",
                                bg, color, border
                              )}>
                                {item}
                              </span>
                            ))}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </section>
              )}

              {/* Key Warnings */}
              {doc.key_warnings && doc.key_warnings.length > 0 && (
                <section>
                  <div className="flex items-center gap-2 mb-3">
                    <AlertTriangle size={14} className="text-red-400" />
                    <h2 className="text-sm font-semibold text-[#f9f9f9]">Key Warnings</h2>
                  </div>
                  <div className="space-y-2">
                    {doc.key_warnings.map((w, i) => (
                      <div key={i} className="flex gap-2 p-2 bg-red-500/5 border border-red-500/20 rounded-lg">
                        <AlertTriangle size={12} className="text-red-400 flex-shrink-0 mt-0.5" />
                        <p className="text-xs text-[#c0c0c0] leading-relaxed">{w}</p>
                      </div>
                    ))}
                  </div>
                </section>
              )}

              {/* Mandatory Requirements */}
              {doc.mandatory_requirements && doc.mandatory_requirements.length > 0 && (
                <section>
                  <div className="flex items-center gap-2 mb-3">
                    <ShieldAlert size={14} className="text-teal-400" />
                    <h2 className="text-sm font-semibold text-[#f9f9f9]">Mandatory Requirements</h2>
                  </div>
                  <ul className="space-y-1.5 pl-2">
                    {doc.mandatory_requirements.map((req, i) => (
                      <li key={i} className="flex gap-2 text-xs text-[#c0c0c0]">
                        <span className="text-teal-400 flex-shrink-0">•</span>
                        {req}
                      </li>
                    ))}
                  </ul>
                </section>
              )}

              {/* Open Findings */}
              {doc.open_findings && doc.open_findings.length > 0 && (
                <section>
                  <div className="flex items-center gap-2 mb-3">
                    <AlertCircle size={14} className="text-orange-400" />
                    <h2 className="text-sm font-semibold text-[#f9f9f9]">Open Findings</h2>
                  </div>
                  <div className="space-y-2">
                    {doc.open_findings.map(f => (
                      <div key={f.id} className="flex items-start gap-2 p-2 bg-orange-500/5 border border-orange-500/20 rounded-lg">
                        <span className="text-xs font-mono text-orange-400 flex-shrink-0">{f.id}</span>
                        <div className="flex-1">
                          <p className="text-xs text-[#c0c0c0]">{f.description}</p>
                          {f.due && <p className="text-xs text-[#6b7280] mt-0.5">Due: {f.due} · Priority: {f.priority}</p>}
                        </div>
                      </div>
                    ))}
                  </div>
                </section>
              )}

              {/* Document Sections */}
              {doc.sections && Object.keys(doc.sections).length > 0 && (
                <section>
                  <div className="flex items-center gap-2 mb-3">
                    <BookOpen size={14} className="text-blue-400" />
                    <h2 className="text-sm font-semibold text-[#f9f9f9]">Document Sections</h2>
                    <span className="text-xs text-[#4b5563]">({Object.keys(doc.sections).length})</span>
                  </div>
                  <div className="space-y-2">
                    {Object.entries(doc.sections).map(([sectionId, text]) => (
                      <SectionItem key={sectionId} sectionId={sectionId} text={text} />
                    ))}
                  </div>
                </section>
              )}

              {/* Inspector (for inspection reports) */}
              {doc.inspector && (
                <div className="flex items-center gap-2 text-xs text-[#6b7280]">
                  <Users size={12} />
                  <span>Inspector: <span className="text-[#a0a0a0]">{doc.inspector}</span></span>
                </div>
              )}

              {/* No extracted data fallback */}
              {!doc.entities && !doc.sections && (
                <div className="flex flex-col items-center justify-center py-10 text-[#4b5563]">
                  <FileText size={32} className="mb-3 opacity-40" />
                  <p className="text-sm">No extracted data available for this document.</p>
                  <p className="text-xs mt-1">Upload the file to run the extraction pipeline.</p>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </>
  );
}
