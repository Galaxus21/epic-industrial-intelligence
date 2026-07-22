/**
 * AI Operations Brain — Current User Context
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
  plant_ids: string[] | null;
}

const ROLE_LABEL: Record<string, string> = {
  technician:        "Technician",
  supervisor:        "Supervisor",
  safety_officer:    "Safety Officer",
  area_authority:    "Area Authority",
  authorized_person: "Authorized Person",
  manager:           "Manager",
  quality_inspector: "Quality Inspector",
};

export { ROLE_LABEL };

interface UserContextType {
  users: UserProfile[];
  currentUser: UserProfile | null;
  setCurrentUser: (u: UserProfile | null) => void;
  loadingUsers: boolean;
}

const UserContext = createContext<UserContextType>({
  users: [],
  currentUser: null,
  setCurrentUser: () => {},
  loadingUsers: true,
});

export function UserProvider({ children }: { children: React.ReactNode }) {
  const [users, setUsers]               = useState<UserProfile[]>([]);
  const [currentUser, setCurrentState]  = useState<UserProfile | null>(null);
  const [loadingUsers, setLoadingUsers] = useState(true);

  useEffect(() => {
    fetch("/api/v1/users")
      .then(r => r.ok ? r.json() : [])
      .then((data: UserProfile[]) => {
        setUsers(data);
        // Restore previously selected user
        let restored: UserProfile | null = null;
        try {
          const storedId = localStorage.getItem("opsbrain-currentUserId");
          if (storedId) restored = data.find(u => u.id === storedId) ?? null;
        } catch { /* ignore */ }
        // Default to first user if nothing stored
        const initial = restored ?? (data.length > 0 ? data[0] : null);
        setCurrentState(initial);
        if (initial) {
          try { localStorage.setItem("opsbrain-currentUserId", initial.id); } catch { /* ignore */ }
        }
      })
      .catch(() => {})
      .finally(() => setLoadingUsers(false));
  }, []);

  const setCurrentUser = (u: UserProfile | null) => {
    setCurrentState(u);
    try {
      if (u) localStorage.setItem("opsbrain-currentUserId", u.id);
      else    localStorage.removeItem("opsbrain-currentUserId");
    } catch { /* ignore */ }
  };

  return (
    <UserContext.Provider value={{ users, currentUser, setCurrentUser, loadingUsers }}>
      {children}
    </UserContext.Provider>
  );
}

export const useCurrentUser = () => useContext(UserContext);
