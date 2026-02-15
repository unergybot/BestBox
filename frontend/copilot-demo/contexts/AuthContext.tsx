"use client";

import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

interface User {
  username: string;
  role: string;
}

interface AuthContextType {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  logout: () => void;
  checkAuth: () => void;
}

function readAuthFromStorage(): { token: string | null; user: User | null } {
  if (typeof window === "undefined") {
    return { token: null, user: null };
  }

  const savedToken = localStorage.getItem("admin_jwt_token") || localStorage.getItem("admin_token");
  const savedRole = localStorage.getItem("admin_role");
  if (!savedToken) {
    return { token: null, user: null };
  }

  const payload = decodeJwtPayload(savedToken);
  if (!payload || isTokenExpired(payload)) {
    localStorage.removeItem("admin_jwt_token");
    localStorage.removeItem("admin_role");
    localStorage.removeItem("admin_user");
    return { token: null, user: null };
  }

  const username =
    (typeof payload.username === "string" && payload.username) ||
    (typeof payload.sub === "string" && payload.sub) ||
    "user";
  const roleFromToken = typeof payload.role === "string" ? payload.role : undefined;
  const role = savedRole || roleFromToken || "viewer";
  return { token: savedToken, user: { username, role } };
}

const AuthContext = createContext<AuthContextType>({
  user: null,
  token: null,
  isAuthenticated: false,
  logout: () => {},
  checkAuth: () => {},
});

function decodeJwtPayload(token: string): Record<string, unknown> | null {
  try {
    const payload = token.split(".")[1];
    if (!payload) return null;
    const normalized = payload.replace(/-/g, "+").replace(/_/g, "/");
    const padded = normalized.padEnd(Math.ceil(normalized.length / 4) * 4, "=");
    const decoded = atob(padded);
    return JSON.parse(decoded) as Record<string, unknown>;
  } catch {
    return null;
  }
}

function isTokenExpired(payload: Record<string, unknown> | null): boolean {
  if (!payload) return true;
  const exp = payload.exp;
  if (typeof exp !== "number") return false;
  return Date.now() >= exp * 1000;
}

export function useAuth() {
  return useContext(AuthContext);
}

interface AuthProviderProps {
  children: React.ReactNode;
}

export function AuthProvider({ children }: AuthProviderProps) {
  const [initialAuth] = useState(() => readAuthFromStorage());
  const [user, setUser] = useState<User | null>(initialAuth.user);
  const [token, setToken] = useState<string | null>(initialAuth.token);

  const logout = useCallback(() => {
    if (typeof window === "undefined") return;
    localStorage.removeItem("admin_jwt_token");
    localStorage.removeItem("admin_role");
    localStorage.removeItem("admin_user");
    setUser(null);
    setToken(null);
  }, []);

  const checkAuth = useCallback(() => {
    const current = readAuthFromStorage();
    if (!current.token || !current.user) {
      logout();
      return;
    }
    setToken(current.token);
    setUser(current.user);
  }, [logout]);

  useEffect(() => {
    if (typeof window === "undefined") return;

    const handleStorageChange = (event: StorageEvent) => {
      if (event.key === "admin_jwt_token" || event.key === "admin_role" || event.key === "admin_token") {
        checkAuth();
      }
    };

    window.addEventListener("storage", handleStorageChange);
    return () => window.removeEventListener("storage", handleStorageChange);
  }, [checkAuth]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const handleAuthExpired = () => logout();
    window.addEventListener("auth-expired", handleAuthExpired);
    return () => window.removeEventListener("auth-expired", handleAuthExpired);
  }, [logout]);

  const value = useMemo(
    () => ({
      user,
      token,
      isAuthenticated: Boolean(user && token),
      logout,
      checkAuth,
    }),
    [user, token, logout, checkAuth],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}