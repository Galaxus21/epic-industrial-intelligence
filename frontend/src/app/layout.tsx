/**
 * AI Operations Brain — Root Layout
 * Wraps all pages with sidebar navigation and top bar.
 * ThemeProvider + UserProvider injected via ClientProviders (client component).
 * Anti-flicker theme script runs before React hydration.
 */
import type { Metadata } from "next";
import "./globals.css";
import { Sidebar } from "@/components/Layout/Sidebar";
import { Toaster } from "sonner";
import { ClientProviders } from "./providers";

export const metadata: Metadata = {
  title: "AI Operations Brain",
  description: "Industrial knowledge graph + multi-agent AI for plant operations",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      {/* Anti-flicker: set data-theme before first paint */}
      <head>
        <script dangerouslySetInnerHTML={{ __html: `
          try {
            var t = localStorage.getItem('opsbrain-theme');
            document.documentElement.setAttribute('data-theme', t === 'light' ? 'light' : 'dark');
          } catch(e) {
            document.documentElement.setAttribute('data-theme','dark');
          }
        ` }} />
      </head>
      <body className="flex h-screen overflow-hidden bg-[#0f0f0f]">
        <ClientProviders>
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
