/**
 * Auth store — React context for the current user + token.
 *
 * Persists the token in localStorage. On mount, if a token exists, fetches /me to validate it.
 */

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { ApiError, clearToken, getToken, setToken } from "@/services/apiClient";
import { authService, type User } from "@/services/authService";

// ============== CONTEXT SHAPE ==============

type AuthContextValue = {
  user: User | null;
  token: string | null;
  isLoading: boolean; // initial /me fetch on mount
  error: string | null;
  login: (email: string, password: string) => Promise<User>;
  signup: (email: string, password: string, full_name: string, trial?: boolean) => Promise<number>;
  loginWithGoogle: (google_id_token: string) => Promise<User>;
  logout: () => void;
  clearError: () => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

// ============== PROVIDER ==============

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setTokenState] = useState<string | null>(() => getToken());
  const [isLoading, setIsLoading] = useState<boolean>(() => getToken() !== null);
  const [error, setError] = useState<string | null>(null);

  // On mount: if a token is in storage, validate it by fetching /me.
  useEffect(() => {
    const stored = getToken();
    if (!stored) {
      setIsLoading(false);
      return;
    }
    let cancelled = false;
    authService
      .me()
      .then((u) => {
        if (cancelled) return;
        setUser(u);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        // Token is invalid or expired — clear it.
        clearToken();
        setTokenState(null);
        setUser(null);
        if (err instanceof ApiError) {
          setError(err.message);
        }
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    setError(null);
    const result = await authService.login(email, password);
    setToken(result.access_token);
    setTokenState(result.access_token);
    setUser(result.user);
    return result.user;
  }, []);

  const signup = useCallback(async (email: string, password: string, full_name: string, trial: boolean = false) => {
    setError(null);
    const result = await authService.signup(email, password, full_name, trial);
    return result.user_id;
  }, []);

  const loginWithGoogle = useCallback(async (google_id_token: string) => {
    setError(null);
    const result = await authService.googleAuth(google_id_token);
    setToken(result.access_token);
    setTokenState(result.access_token);
    setUser(result.user);
    return result.user;
  }, []);

  const logout = useCallback(() => {
    clearToken();
    setTokenState(null);
    setUser(null);
    setError(null);
  }, []);

  const clearError = useCallback(() => setError(null), []);

  const value = useMemo<AuthContextValue>(
    () => ({ user, token, isLoading, error, login, signup, loginWithGoogle, logout, clearError }),
    [user, token, isLoading, error, login, signup, loginWithGoogle, logout, clearError],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

// ============== HOOK ==============

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used inside <AuthProvider>");
  }
  return ctx;
}
