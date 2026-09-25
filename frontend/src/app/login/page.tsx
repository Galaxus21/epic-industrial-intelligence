"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { BrainCircuit, Lock, User, AlertCircle, ArrowRight, Sparkles, Loader2 } from "lucide-react";
import { useCurrentUser, type UserProfile } from "@/lib/user-context";
import { roleLabel } from "@/lib/roles";

export default function LoginPage() {
  const router = useRouter();
  const { currentUser, loginUser } = useCurrentUser();
  const [employeeId, setEmployeeId] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [demoUsers, setDemoUsers] = useState<UserProfile[]>([]);

  // If already authenticated, redirect to root dashboard
  useEffect(() => {
    if (currentUser) {
      router.push("/");
    }
  }, [currentUser, router]);

  // Load available profiles for quick demo switching
  useEffect(() => {
    import("@/lib/api")
      .then(api => api.get<UserProfile[]>("/api/v1/users"))
      .then(data => setDemoUsers(data))
      .catch(() => {});
  }, []);

  const handleLogin = async (idToUse?: string) => {
    const targetId = idToUse ?? employeeId;
    if (!targetId.trim()) {
      setError("Please enter your Employee ID");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      await loginUser(targetId.trim(), password);
      router.push("/");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Authentication failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen w-full flex items-center justify-center bg-[#0a0a0a] p-4">
      <div className="w-full max-w-md bg-[#121212] border border-[#262626] rounded-2xl p-8 shadow-2xl">
        {/* Header */}
        <div className="flex items-center gap-3 mb-6">
          <div className="w-10 h-10 rounded-xl bg-amber-500/15 border border-amber-500/30 flex items-center justify-center">
            <BrainCircuit size={22} className="text-amber-400" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-[#f9f9f9] tracking-tight">EPIC Platform</h1>
            <p className="text-xs text-[#737373]">Enterprise Platform for Industrial Cognition</p>
          </div>
        </div>

        {error && (
          <div className="mb-5 p-3 rounded-lg bg-red-500/10 border border-red-500/25 flex items-center gap-2.5 text-red-400 text-xs">
            <AlertCircle size={15} className="flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <form
          onSubmit={e => {
            e.preventDefault();
            handleLogin();
          }}
          className="space-y-4"
        >
          <div>
            <label htmlFor="employee-id" className="block text-xs font-medium text-[#a3a3a3] mb-1.5">Employee ID</label>
            <div className="relative">
              <User size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-[#525252]" />
              <input
                id="employee-id"
                type="text"
                value={employeeId}
                onChange={e => setEmployeeId(e.target.value)}
                placeholder="e.g. EMP-001"
                aria-label="Employee ID"
                disabled={loading}
                className="w-full pl-9 pr-3 py-2 bg-[#1a1a1a] border border-[#2a2a2a] rounded-lg text-sm text-[#f9f9f9] placeholder-[#525252] focus:outline-none focus:border-amber-500/50 transition-colors"
              />
            </div>
          </div>

          <div>
            <label htmlFor="password" className="block text-xs font-medium text-[#a3a3a3] mb-1.5">
              Password <span className="text-[#525252] font-normal">(Optional in dev)</span>
            </label>
            <div className="relative">
              <Lock size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-[#525252]" />
              <input
                id="password"
                type="password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                placeholder="••••••••"
                aria-label="Password"
                disabled={loading}
                className="w-full pl-9 pr-3 py-2 bg-[#1a1a1a] border border-[#2a2a2a] rounded-lg text-sm text-[#f9f9f9] placeholder-[#525252] focus:outline-none focus:border-amber-500/50 transition-colors"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full mt-2 py-2.5 px-4 rounded-lg bg-amber-500 hover:bg-amber-400 text-black text-sm font-semibold flex items-center justify-center gap-2 transition-colors disabled:opacity-50"
          >
            {loading ? (
              <>
                <Loader2 size={16} className="animate-spin" />
                <span>Authenticating…</span>
              </>
            ) : (
              <>
                <span>Sign In</span>
                <ArrowRight size={15} />
              </>
            )}
          </button>
        </form>

        {/* Demo Quick-Login section */}
        {demoUsers.length > 0 && (
          <div className="mt-8 border-t border-[#262626] pt-5">
            <div className="flex items-center gap-1.5 text-xs text-[#737373] mb-3 uppercase tracking-wider font-semibold">
              <Sparkles size={13} className="text-amber-400" />
              <span>Demo Quick Sign-In</span>
            </div>
            <div className="grid grid-cols-2 gap-2 max-h-48 overflow-y-auto">
              {demoUsers.map(u => (
                <button
                  key={u.id}
                  type="button"
                  disabled={loading}
                  onClick={() => {
                    setEmployeeId(u.employee_id);
                    handleLogin(u.employee_id);
                  }}
                  className="p-2 rounded-lg bg-[#171717] hover:bg-[#212121] border border-[#262626] text-left transition-colors group"
                >
                  <p className="text-xs font-medium text-[#e5e5e5] group-hover:text-amber-400 truncate transition-colors">
                    {u.name}
                  </p>
                  <p className="text-[10px] text-[#737373] truncate">
                    {roleLabel[u.role] ?? u.role} · {u.employee_id}
                  </p>
                </button>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
