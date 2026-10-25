'use client';

import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react';
import { AlertTriangle, Loader2 } from 'lucide-react';

export type AdminRole = 'ADMIN' | 'SUPER_ADMIN' | 'RESEARCHER' | 'ANALYST' | 'VIEWER';

export interface AdminUser {
  id: string;
  email: string;
  name: string;
  role: AdminRole;
  createdAt: string;
  lastLogin: string;
}

export interface AuthState {
  user: AdminUser | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  error: string | null;
}

interface AuthContextType extends AuthState {
  login: (email: string, password: string, totpCode?: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshSession: () => Promise<void>;
  clearError: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);
const ROLE_HIERARCHY: Record<AdminRole, number> = {
  VIEWER: 1, ANALYST: 2, RESEARCHER: 3, ADMIN: 4, SUPER_ADMIN: 5,
};

export function hasPermission(userRole: AdminRole, requiredRole: AdminRole): boolean {
  return ROLE_HIERARCHY[userRole] >= ROLE_HIERARCHY[requiredRole];
}

function toUser(input: unknown): AdminUser | null {
  if (!input || typeof input !== 'object') return null;
  const user = input as Record<string, unknown>;
  const role = String(user.role ?? '').toUpperCase() as AdminRole;
  if (!(role in ROLE_HIERARCHY) || typeof user.email !== 'string') return null;
  return {
    id: String(user.id ?? user.user_id ?? ''),
    email: user.email,
    name: String(user.name ?? 'Administrator'),
    role,
    createdAt: String(user.created_at ?? user.createdAt ?? ''),
    lastLogin: String(user.last_login ?? user.lastLogin ?? ''),
  };
}

async function responseError(response: Response): Promise<string> {
  const data = await response.json().catch(() => null) as { error?: string; detail?: string } | null;
  return data?.error ?? data?.detail ?? `Authentication request failed (${response.status})`;
}

function readCsrfCookie(): string {
  if (typeof document === 'undefined') return '';
  const prefix = 'artha_admin_csrf=';
  const item = document.cookie.split('; ').find((value) => value.startsWith(prefix));
  return item ? decodeURIComponent(item.slice(prefix.length)) : '';
}

export function AdminAuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({
    user: null, isLoading: true, isAuthenticated: false, error: null,
  });

  const clearError = useCallback(() => setState((previous) => ({ ...previous, error: null })), []);

  const refreshSession = useCallback(async () => {
    try {
      const response = await fetch('/api/auth/me', { method: 'GET', credentials: 'same-origin', cache: 'no-store' });
      if (!response.ok) {
        setState({ user: null, isLoading: false, isAuthenticated: false, error: null });
        return;
      }
      const data = await response.json() as { user?: unknown };
      const user = toUser(data.user);
      setState({ user, isLoading: false, isAuthenticated: Boolean(user), error: user ? null : 'Invalid user session' });
    } catch {
      setState({ user: null, isLoading: false, isAuthenticated: false, error: 'Authentication service is unavailable' });
    }
  }, []);

  useEffect(() => { void refreshSession(); }, [refreshSession]);

  const login = useCallback(async (email: string, password: string, totpCode?: string) => {
    setState((previous) => ({ ...previous, isLoading: true, error: null }));
    try {
      const response = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'same-origin',
        body: JSON.stringify({ email, password, ...(totpCode ? { totp_code: totpCode } : {}) }),
      });
      if (!response.ok) throw new Error(await responseError(response));
      const data = await response.json() as { user?: unknown };
      const user = toUser(data.user);
      if (!user) throw new Error('Authentication service returned an invalid user');
      setState({ user, isLoading: false, isAuthenticated: true, error: null });
    } catch (error) {
      setState({ user: null, isLoading: false, isAuthenticated: false, error: error instanceof Error ? error.message : 'Sign-in failed' });
      throw error;
    }
  }, []);

  const logout = useCallback(async () => {
    const csrf = readCsrfCookie();
    try {
      const response = await fetch('/api/auth/logout', {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'X-CSRF-Token': csrf },
      });
      if (!response.ok) throw new Error(await responseError(response));
      setState({ user: null, isLoading: false, isAuthenticated: false, error: null });
    } catch (error) {
      setState((previous) => ({ ...previous, error: error instanceof Error ? error.message : 'Sign-out failed' }));
      throw error;
    }
  }, []);

  return (
    <AuthContext.Provider value={{ ...state, login, logout, refreshSession, clearError }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAdminAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAdminAuth must be used within AdminAuthProvider');
  return context;
}

export function useAdminRole(requiredRole: AdminRole) {
  const { user, isAuthenticated } = useAdminAuth();
  return Boolean(isAuthenticated && user && hasPermission(user.role, requiredRole));
}

export function AdminOnly({ children, requiredRole = 'ADMIN' }: { children: ReactNode; requiredRole?: AdminRole }) {
  const { user, isAuthenticated, isLoading } = useAdminAuth();
  if (isLoading) {
    return <div className="flex h-64 items-center justify-center"><Loader2 className="h-8 w-8 animate-spin text-admin-neon-green" /></div>;
  }
  if (!isAuthenticated || !user || !hasPermission(user.role, requiredRole)) {
    return <div className="admin-card p-8 text-center"><AlertTriangle className="mx-auto mb-4 h-12 w-12 text-admin-amber" /><h3 className="mb-2 text-lg font-medium text-admin-text-primary">Access denied</h3><p className="text-admin-text-secondary">This section requires the {requiredRole} role or higher.</p></div>;
  }
  return <>{children}</>;
}
