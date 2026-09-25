/**
 * What the review gate held back on a document, one line per entity. Read-only: to accept an entity,
 * register the equipment (POST /api/v1/equipment) and upload the document again, or run the backend
 * with AUTO_REGISTER_ENTITIES=true (README section 2.2).
 */
import { AlertTriangle } from "lucide-react";

import type { DocumentDetail } from "@/lib/types";

type HeldReview = Pick<DocumentDetail, "entities_pending_review" | "pending_review_note" | "held_entities" | "unresolved_equipment_ids">;

export function HeldEntitiesNotice({ doc }: { doc: HeldReview }) {
  const held = doc.held_entities ?? [];
  const unresolved = doc.unresolved_equipment_ids ?? [];
  if (!doc.entities_pending_review && held.length === 0 && unresolved.length === 0) return null;

  return (
    <div className="p-3 bg-amber-500/10 border border-amber-500/30 rounded-xl text-xs">
      <div className="flex items-center gap-1.5 mb-1.5">
        <AlertTriangle size={14} className="text-amber-400" />
        <span className="font-semibold text-amber-400">Entities held for review</span>
      </div>
      {doc.pending_review_note && <p className="text-[#d0d0d0] leading-relaxed">{doc.pending_review_note}</p>}
      {held.length > 0 ? (
        <ul className="mt-1.5 space-y-0.5 list-disc pl-4 text-[#d0d0d0]">
          {held.map((label, i) => <li key={i}>{label}</li>)}
        </ul>
      ) : (
        unresolved.length > 0 && (
          <p className="mt-1.5 text-[#d0d0d0]">Not linked, no such equipment: {unresolved.join(", ")}</p>
        )
      )}
      <p className="mt-1.5 text-[#a0a0a0]">
        To accept one, register the equipment and upload the document again, or run with AUTO_REGISTER_ENTITIES=true.
      </p>
    </div>
  );
}
