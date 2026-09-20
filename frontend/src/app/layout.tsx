/**
 * EPIC — Root Layout
 * Wraps all pages with sidebar navigation and top bar.
 * ThemeProvider + UserProvider injected via ClientProviders (client component).
 * Anti-flicker theme script runs before React hydration.
 */
import type { Metadata, Viewport } from "next";
import "./globals.css";
import { Sidebar } from "@/components/Layout/Sidebar";
import { Toaster } from "sonner";
import { ClientProviders } from "./providers";
import { ServiceWorkerRegister } from "@/components/PWA/ServiceWorkerRegister";

export const metadata: Metadata = {
  title: "EPIC — Enterprise Platform for Industrial Cognition",
  description: "Equipment-aware question answering over plant records, documents and live telemetry",
};

export const viewport: Viewport = {
  themeColor: "#0f172a",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      {/* Anti-flicker: set data-theme before first paint. React never renders that attribute, hence suppressHydrationWarning. */}
      <head>
        <script dangerouslySetInnerHTML={{ __html: `
          try {
            var t = localStorage.getItem('epicTheme');
            document.documentElement.setAttribute('data-theme', t === 'light' ? 'light' : 'dark');
          } catch(e) {
            document.documentElement.setAttribute('data-theme','dark');
          }
        ` }} />
      </head>
      <body className="flex h-screen overflow-hidden bg-[#0f0f0f]">
        <ClientProviders>
          <ServiceWorkerRegister />
          <Sidebar />
          <main className="flex-1 overflow-y-auto bg-[#0f0f0f] lg:pt-0 pt-12">
            {children}
          </main>
          <Toaster
            theme="system"
            toastOptions={{
              style: { background: "var(--bg-card)", border: "1px solid var(--border)", color: "var(--text-primary)" },
            }}
          />
        </ClientProviders>
      </body>
    </html>
  );
}
