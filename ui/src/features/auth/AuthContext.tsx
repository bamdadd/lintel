import {
  createContext,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import { customInstance } from '@/shared/api/client';

export interface AuthUser {
  user_id: string;
  name: string;
  email: string;
  role: string;
}

interface AuthTokens {
  access_token: string;
  refresh_token: string;
}

export interface AuthContextValue {
  user: AuthUser | null;
  token: string | null;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

export const AuthContext = createContext<AuthContextValue | null>(null);

const TOKEN_KEY = 'lintel_access_token';
const REFRESH_KEY = 'lintel_refresh_token';

function getStoredToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

function getStoredRefreshToken(): string | null {
  return localStorage.getItem(REFRESH_KEY);
}

function storeTokens(access: string, refresh: string) {
  localStorage.setItem(TOKEN_KEY, access);
  localStorage.setItem(REFRESH_KEY, refresh);
}

function clearTokens() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(REFRESH_KEY);
}

/** Parse JWT exp claim (seconds since epoch) */
function getTokenExpiry(token: string): number | null {
  try {
    const payload = JSON.parse(atob(token.split('.')[1]));
    return typeof payload.exp === 'number' ? payload.exp : null;
  } catch {
    return null;
  }
}

async function fetchWithAuth<T>(url: string, token: string): Promise<T> {
  return customInstance<T>(url, {
    headers: { Authorization: `Bearer ${token}` },
  });
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [token, setToken] = useState<string | null>(getStoredToken);
  const [isLoading, setIsLoading] = useState(!!getStoredToken());
  const refreshTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const scheduleRefresh = useCallback((accessToken: string) => {
    if (refreshTimerRef.current) clearTimeout(refreshTimerRef.current);
    const exp = getTokenExpiry(accessToken);
    if (!exp) return;
    // Refresh 60s before expiry, minimum 5s from now
    const msUntilRefresh = Math.max((exp * 1000 - Date.now()) - 60_000, 5_000);
    refreshTimerRef.current = setTimeout(async () => {
      const refreshToken = getStoredRefreshToken();
      if (!refreshToken) return;
      try {
        const res = await customInstance<{ data: AuthTokens }>('/api/v1/auth/refresh', {
          method: 'POST',
          body: JSON.stringify({ refresh_token: refreshToken }),
        });
        storeTokens(res.data.access_token, res.data.refresh_token);
        setToken(res.data.access_token);
        scheduleRefresh(res.data.access_token);
      } catch {
        // Refresh failed — force logout
        clearTokens();
        setToken(null);
        setUser(null);
      }
    }, msUntilRefresh);
  }, []);

  const logout = useCallback(() => {
    if (refreshTimerRef.current) clearTimeout(refreshTimerRef.current);
    clearTokens();
    setToken(null);
    setUser(null);
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const res = await customInstance<{ data: AuthTokens }>('/api/v1/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });
    storeTokens(res.data.access_token, res.data.refresh_token);
    setToken(res.data.access_token);

    const meRes = await fetchWithAuth<{ data: AuthUser }>('/api/v1/auth/me', res.data.access_token);
    setUser(meRes.data);
    scheduleRefresh(res.data.access_token);
  }, [scheduleRefresh]);

  // On mount, if we have a stored token, fetch current user
  useEffect(() => {
    if (!token) {
      setIsLoading(false);
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const meRes = await fetchWithAuth<{ data: AuthUser }>('/api/v1/auth/me', token);
        if (!cancelled) {
          setUser(meRes.data);
          scheduleRefresh(token);
        }
      } catch {
        if (!cancelled) {
          clearTokens();
          setToken(null);
          setUser(null);
        }
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const value = useMemo<AuthContextValue>(
    () => ({ user, token, isLoading, login, logout }),
    [user, token, isLoading, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
