import { randomBytes, timingSafeEqual } from 'node:crypto';
import { NextRequest, NextResponse } from 'next/server';

export const ACCESS_COOKIE = 'artha_admin_access';
export const REFRESH_COOKIE = 'artha_admin_refresh';
export const CSRF_COOKIE = 'artha_admin_csrf';

export function backendAuthUrl(path: string): string {
  const base = (process.env.BACKEND_INTERNAL_URL || process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000').replace(/\/+$/, '');
  return `${base}/api/admin/auth/${path.replace(/^\/+/, '')}`;
}

export function setSessionCookies(response: NextResponse, session: { session_token: string; refresh_token: string; expires_in: number }): void {
  const secure = process.env.NODE_ENV === 'production';
  const maxAge = Math.max(60, Math.min(Number(session.expires_in) || 1800, 86400));
  response.cookies.set(ACCESS_COOKIE, session.session_token, {
    httpOnly: true, secure, sameSite: 'lax', path: '/', maxAge,
  });
  response.cookies.set(REFRESH_COOKIE, session.refresh_token, {
    httpOnly: true, secure, sameSite: 'lax', path: '/', maxAge: 7 * 86400,
  });
  response.cookies.set(CSRF_COOKIE, randomBytes(32).toString('base64url'), {
    httpOnly: false, secure, sameSite: 'lax', path: '/', maxAge,
  });
}

export function clearSessionCookies(response: NextResponse): void {
  const secure = process.env.NODE_ENV === 'production';
  for (const name of [ACCESS_COOKIE, REFRESH_COOKIE, CSRF_COOKIE]) {
    response.cookies.set(name, '', { httpOnly: name !== CSRF_COOKIE, secure, sameSite: 'lax', path: '/', maxAge: 0 });
  }
}

export function hasValidCsrf(request: NextRequest): boolean {
  const cookie = request.cookies.get(CSRF_COOKIE)?.value ?? '';
  const header = request.headers.get('x-csrf-token') ?? '';
  if (!cookie || !header) return false;
  const left = Buffer.from(cookie);
  const right = Buffer.from(header);
  return left.length === right.length && timingSafeEqual(left, right);
}

export async function fetchBackend(path: string, init: RequestInit = {}): Promise<Response> {
  return fetch(backendAuthUrl(path), {
    ...init,
    cache: 'no-store',
    signal: AbortSignal.timeout(15_000),
  });
}
