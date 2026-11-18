import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { api, onUnauthorized, type Me } from "../api";

interface AuthState { me: Me | null; checking: boolean; refresh: () => Promise<void>; logout: () => Promise<void> }
const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [checking, setChecking] = useState(true);
  const refresh = useCallback(async () => {
    try { setMe(await api.me()); } catch { setMe(null); } finally { setChecking(false); }
  }, []);
  const logout = useCallback(async () => { await api.logout(); setMe(null); }, []);
  useEffect(() => { void refresh(); }, [refresh]);
  useEffect(() => onUnauthorized(() => setMe(null)), []);
  return <AuthContext.Provider value={{ me, checking, refresh, logout }}>{children}</AuthContext.Provider>;
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth outside AuthProvider");
  return ctx;
}
