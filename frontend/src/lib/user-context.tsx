/**
 * EPIC — Current User Context
 * Loads user profiles from /api/v1/users and exposes the "acting-as" user.
 * Stored in localStorage so workflow action buttons can use real DB identities
 * instead of hardcoded reviewer names and IDs.
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

const ROLE_LABEL: Record<string, string> = {
  technician: "Technician",
  supervisor: "Supervisor",
  manager:    "Manager",
};

export { ROLE_LABEL };

interface UserContextType {
  users: UserProfile[];
  currentUser: UserProfile | null;
  setCurrentUser: (u: UserProfile | null) => void;
  loadingUsers: boolean;
  authToken?: string | null;
  loginUser: (employeeId: string, password?: string) => Promise<void>;
  logoutUser: () => Promise<void>;
}

const UserContext = createContext<UserContextType>({
  users: [],
  currentUser: null,
  setCurrentUser: () => {},
  loadingUsers: true,
  authToken: null,
  loginUser: async () => {},
  logoutUser: async () => {},
});

export function UserProvider({ children }: { children: React.ReactNode }) {
  const [users, setUsers]               = useState<UserProfile[]>([]);
  const [currentUser, setCurrentState]  = useState<UserProfile | null>(null);
  const [loadingUsers, setLoadingUsers] = useState(true);

  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const api = await import("@/lib/api");
        // /api/v1/users/me is the source of truth for the session cookie
        const me = await api.get<UserProfile>("/api/v1/users/me").catch(() => null);
        const allUsers = await api.get<UserProfile[]>("/api/v1/users").catch(() => []);
        if (!mounted) return;
        setUsers(allUsers);
        if (me && me.id) {
          setCurrentState(me);
          try { localStorage.setItem("epicCurrentUserId", me.id); } catch { /* ignore */ }
        } else {
          setCurrentState(null);
          try { localStorage.removeItem("epicCurrentUserId"); } catch { /* ignore */ }
          if (typeof window !== "undefined" && window.location.pathname !== "/login") {
            window.location.href = "/login";
          }
        }
      } catch {
        if (!mounted) return;
        setCurrentState(null);
        try { localStorage.removeItem("epicCurrentUserId"); } catch { /* ignore */ }
        if (typeof window !== "undefined" && window.location.pathname !== "/login") {
          window.location.href = "/login";
        }
      } finally {
        if (mounted) setLoadingUsers(false);
      }
    })();
    return () => { mounted = false; };
  }, []);

  const setCurrentUser = (u: UserProfile | null) => {
    setCurrentState(u);
    try {
      if (u) localStorage.setItem("epicCurrentUserId", u.id);
      else    localStorage.removeItem("epicCurrentUserId");
    } catch { /* ignore */ }
  };

  const loginUser = async (employeeId: string, password?: string) => {
    const { login } = await import("@/lib/api");
    const result = await login(employeeId, password);
    const user = result.user as UserProfile;
    if (user) {
      setCurrentState(user);
      try { localStorage.setItem("epicCurrentUserId", user.id); } catch { /* ignore */ }
    }
  };

  const logoutUser = async () => {
    const { logout } = await import("@/lib/api");
    await logout().catch(() => {});
    setCurrentState(null);
    try { localStorage.removeItem("epicCurrentUserId"); } catch { /* ignore */ }
    if (typeof window !== "undefined" && window.location.pathname !== "/login") {
      window.location.href = "/login";
    }
  };

  return (
    <UserContext.Provider value={{ users, currentUser, setCurrentUser, loadingUsers, authToken: null, loginUser, logoutUser }}>
      {children}
    </UserContext.Provider>
  );
}

export const useCurrentUser = () => useContext(UserContext);
