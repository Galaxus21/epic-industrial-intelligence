"use client";

import { useEffect } from "react";

export function ServiceWorkerRegister() {
  useEffect(() => {
    if (typeof window !== "undefined" && "serviceWorker" in navigator) {
      navigator.serviceWorker
        .register("/sw.js")
        .then((reg) => {
          console.debug("[PWA] Service Worker registered:", reg.scope);
        })
        .catch((err) => {
          console.debug("[PWA] Service Worker registration skipped:", err);
        });
    }
  }, []);

  return null;
}
