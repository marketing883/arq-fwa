"use client";

import { createContext, useContext, useState, useEffect, useCallback, ReactNode } from "react";
import { usePathname, useRouter } from "next/navigation";

export interface AuthUser {
  id: number;
  email: string;
  full_name: string;
  role: string;
  permissions: string[];
}

interface AuthState {
  user: AuthUser | null;
  token: string | null;
  refreshToken: string | null;
  isAuthenticated: boolean;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  hasPermission: (perm: string) => boolean;
}

const AuthContext = createContext<AuthState>({
  user: null,
  token: null,
  refreshToken: null,
  isAuthenticated: false,
  loading: true,
  login: async () => {},
  logout: () => {},
  hasPermission: () => false,
});

export function useAuth() {
  return useContext(AuthContext);
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "/api";
const STORAGE_KEY = "arq_auth";

function loadStored(): { token: string; refreshToken: string; user: AuthUser } | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

function saveStored(token: string, refreshToken: string, user: AuthUser) {
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify({ token, refreshToken, user }));
}

function clearStored() {
  sessionStorage.removeItem(STORAGE_KEY);
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [refreshToken, setRefreshToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();
  const pathname = usePathname();

  // Restore session on mount
  useEffect(() => {
    const stored = loadStored();
    if (stored) {
      setToken(stored.token);
      setRefreshToken(stored.refreshToken);
      setUser(stored.user);
    }
    setLoading(false);
  }, []);

  // Redirect unauthenticated users to login
  useEffect(() => {
    if (!loading && !user && pathname !== "/login") {
      router.replace("/login");
    }
  }, [loading, user, pathname, router]);

  const login = useCallback(async (email: string, password: string) => {
    const res = await fetch(`${API_BASE}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail || "Login failed");
    }
    const data = await res.json();
    setToken(data.access_token);
    setRefreshToken(data.refresh_token || null);
    setUser(data.user);
    saveStored(data.access_token, data.refresh_token || "", data.user);
    router.replace("/");
  }, [router]);

  const logout = useCallback(() => {
    if (refreshToken) {
      fetch(`${API_BASE}/auth/logout?refresh_token=${refreshToken}`, { method: "POST" }).catch(() => {});
    }
    setToken(null);
    setRefreshToken(null);
    setUser(null);
    clearStored();
    router.replace("/login");
  }, [refreshToken, router]);

  const hasPermission = useCallback((perm: string) => {
    return user?.permissions?.includes(perm) ?? false;
  }, [user]);

  return (
    <AuthContext.Provider value={{
      user,
      token,
      refreshToken,
      isAuthenticated: !!user,
      loading,
      login,
      logout,
      hasPermission,
    }}>
      {children}
    </AuthContext.Provider>
  );
}
