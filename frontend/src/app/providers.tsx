/**
 * AI Operations Brain — Client-side Providers
 * Wraps the app with ThemeProvider + UserProvider.
 * Kept separate so RootLayout remains a Server Component.
 */
"use client";

import { ThemeProvider } from "@/lib/theme-context";
import { UserProvider } from "@/lib/user-context";

export function ClientProviders({ children }: { children: React.ReactNode }) {
  return (
    <ThemeProvider>
      <UserProvider>
        {children}
      </UserProvider>
    </ThemeProvider>
  );
}
