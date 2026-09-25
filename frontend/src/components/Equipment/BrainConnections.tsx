/**
 * AI Operations Brain — Brain Connections Component
 * Shows the equipment's knowledge connections as a compact grid.
 * Documents are clickable — opens the DocumentModal with extracted data.
 */
"use client";

import { useState } from "react";
import { AlertTriangle, FileText, Users, Package, ShieldCheck, Wrench, ChevronRight } from "lucide-react";
import type { Incident, MaintenanceRecord, Document } from "@/lib/types";
import { DocumentModal } from "@/components/ui/DocumentModal";

interface BrainConnectionsProps {
  brain: Record<string, unknown>;
  equipmentId: string;
}

export function BrainConnections({ brain, equipmentId }: BrainConnectionsProps) {
  const [selectedDocId, setSelectedDocId] = useState<string | null>(null);

  const incidents = (brain.incidents as Incident[]) ?? [];
  const maintenanceRecords = (brain.maintenance_records as MaintenanceRecord[]) ?? [];
  const documents = (brain.documents as Document[]) ?? [];
  const technicians = (brain.technicians as { name: string; role: string }[]) ?? [];
  const spareParts = (brain.spare_parts as { name: string; quantity_on_hand: number }[]) ?? [];
  const compliance = brain.compliance as { overall_score?: number; status?: string; issues?: unknown[] } | undefined;
  const downstream = (brain.downstream_equipment as { id: string; name: string }[]) ?? [];

  const groups = [
    {
      label: "Incidents",
      icon: <AlertTriangle size={13} className="text-orange-400" />,
      color: "text-orange-400",
      items: incidents.slice(0, 3).map(i => ({ id: i.id, text: i.title, sub: i.date, dot: i.severity === "High" ? "#f97316" : "#a0a0a0", clickable: false })),
    },
    {
      label: "Maintenance",
      icon: <Wrench size={13} className="text-blue-400" />,
      color: "text-blue-400",
      items: maintenanceRecords.slice(0, 3).map(m => ({
        id: m.id,
        text: m.description.substring(0, 40) + "…",
        sub: m.date ?? m.id,
        dot: m.status === "Overdue" ? "#f97316" : "#10b981",
        clickable: false,
      })),
    },
    {
      label: "Documents",
      icon: <FileText size={13} className="text-purple-400" />,
      color: "text-purple-400",
      items: documents.slice(0, 3).map(d => ({ id: d.id, text: d.name.substring(0, 40), sub: d.type, dot: "#a855f7", clickable: true })),
    },
    {
      label: "Technicians",
      icon: <Users size={13} className="text-emerald-400" />,
      color: "text-emerald-400",
      items: technicians.slice(0, 3).map(t => ({ id: t.name, text: t.name, sub: t.role, dot: "#10b981", clickable: false })),
    },
    {
      label: "Spare Parts",
      icon: <Package size={13} className="text-amber-400" />,
      color: "text-amber-400",
      items: spareParts.slice(0, 2).map(s => ({ id: s.name, text: s.name.substring(0, 35), sub: `${s.quantity_on_hand} in stock`, dot: "#f59e0b", clickable: false })),
    },
    {
      label: "Compliance",
      icon: <ShieldCheck size={13} className="text-teal-400" />,
      color: "text-teal-400",
      // Equipment with no compliance record comes back as {}, which is no record rather than a score.
      items: compliance?.overall_score != null
        ? [{ id: "cmp", text: `Score: ${compliance.overall_score}%`, sub: `${(compliance.issues as unknown[] | undefined)?.length ?? 0} open issues`, dot: (compliance.overall_score ?? 100) >= 90 ? "#10b981" : "#f97316", clickable: false }]
        : [],
    },
  ];

  return (
    <div className="space-y-3">
      {groups.map(group => (
        <div key={group.label}>
          <div className="flex items-center gap-1.5 mb-1.5">
            {group.icon}
            <span className={`text-xs font-semibold ${group.color}`}>{group.label}</span>
            <span className="text-xs text-[#6b7280] ml-auto">{group.items.length}</span>
          </div>
          {group.items.length === 0 ? (
            <p className="text-xs text-[#6b7280] pl-4">None recorded</p>
          ) : (
            <div className="space-y-1 pl-4">
              {group.items.map(item => (
                item.clickable ? (
                  <button
                    key={item.id}
                    onClick={() => setSelectedDocId(item.id)}
                    className="w-full flex items-center gap-2 hover:bg-[#1a1a1a] rounded px-1 py-0.5 transition-colors group/doc"
                  >
                    <span className="h-1.5 w-1.5 rounded-full flex-shrink-0" style={{ background: item.dot }} />
                    <span className="text-xs text-[#a0a0a0] flex-1 truncate text-left group-hover/doc:text-purple-300 transition-colors">{item.text}</span>
                    <span className="text-xs text-[#4b5563] group-hover/doc:text-purple-400 transition-colors">{item.sub} →</span>
                  </button>
                ) : (
                  <div key={item.id} className="flex items-center gap-2">
                    <span className="h-1.5 w-1.5 rounded-full flex-shrink-0" style={{ background: item.dot }} />
                    <span className="text-xs text-[#a0a0a0] flex-1 truncate">{item.text}</span>
                    <span className="text-xs text-[#6b7280]">{item.sub}</span>
                  </div>
                )
              ))}
            </div>
          )}
        </div>
      ))}

      {downstream.length > 0 && (
        <div>
          <div className="flex items-center gap-1.5 mb-1.5">
            <ChevronRight size={13} className="text-[#6b7280]" />
            <span className="text-xs font-semibold text-[#6b7280]">Downstream Equipment</span>
          </div>
          <div className="flex flex-wrap gap-1.5 pl-4">
            {downstream.map(d => (
              <span key={d.id} className="px-2 py-0.5 rounded-full bg-[#2a2a2a] text-xs text-[#a0a0a0]">{d.id}</span>
            ))}
          </div>
        </div>
      )}

      <DocumentModal docId={selectedDocId} onClose={() => setSelectedDocId(null)} />
    </div>
  );
}
