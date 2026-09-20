/**
 * AI Operations Brain — Query Page
 * Full-height chat interface.
 */
"use client";

import { Suspense } from "react";
import { QueryInterface } from "@/components/Query/QueryInterface";

export default function QueryPage() {
  return (
    <div className="h-full overflow-hidden">
      <Suspense fallback={null}>
        <QueryInterface />
      </Suspense>
    </div>
  );
}
