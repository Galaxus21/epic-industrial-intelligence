/**
 * EPIC — Current User Context
 * The signed-in user comes from GET /api/v1/users/me, which reads the session cookie. There is no way to
 * act as anyone else in the UI: the server checks every write against the session, so the UI shows the
 * same identity the server uses.
 */
"use client";

import { createContext, useContext, useEffect, useState } from "react";

export interface UserProfile {
  id: string;
  employee_id: string;
  name: string;
  role: string;
  department: string | null;
  certifications: string[] | null;
}

interface UserContextType {
  currentUser: UserProfile | null;
  loginUser: (employeeId: string, password?: string) => Promise<void>;
  logoutUser: () => Promise<void>;
}

const loginPath = "/login";

const UserContext = createContext<UserContextType>({
  currentUser: null,
  loginUser: async () => {},
  logoutUser: async () => {},
});

export function UserProvider({ children }: { children: React.ReactNode }) {
  const [currentUser, setCurrentUser] = useState<UserProfile | null>(null);

  useEffect(() => {
    let mounted = true;
    (async () => {
      const api = await import("@/lib/api");
      const me = await api.get<UserProfile>("/api/v1/users/me").catch(() => null);
      if (!mounted) return;
      setCurrentUser(me?.id ? me : null);
      if (!me?.id) goToLogin();
    })();
    return () => { mounted = false; };
  }, []);

  const loginUser = async (employeeId: string, password?: string) => {
    const { login } = await import("@/lib/api");
    const result = await login(employeeId, password);
    if (result.user) setCurrentUser(result.user as UserProfile);
  };

  const logoutUser = async () => {
    const { logout } = await import("@/lib/api");
    await logout().catch(() => {});
    setCurrentUser(null);
    goToLogin();
  };

  return (
    <UserContext.Provider value={{ currentUser, loginUser, logoutUser }}>
      {children}
    </UserContext.Provider>
  );
}

export const useCurrentUser = () => useContext(UserContext);

function goToLogin() {
  if (typeof window !== "undefined" && window.location.pathname !== loginPath) {
    window.location.href = loginPath;
  }
}
