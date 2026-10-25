import { NextRequest, NextResponse } from 'next/server';
import { ACCESS_COOKIE, REFRESH_COOKIE, fetchBackend, setSessionCookies } from '@/lib/server-auth';

export const runtime = 'nodejs';

export async function GET(request: NextRequest) {
  let access = request.cookies.get(ACCESS_COOKIE)?.value;
  const refresh = request.cookies.get(REFRESH_COOKIE)?.value;
  let response: Response | null = null;
  if (access) {
    try {
      response = await fetchBackend('me', { headers: { authorization: `Bearer ${access}` } });
    } catch {
      return NextResponse.json({ error: 'Authentication service is unavailable' }, { status: 503 });
    }
  }

  let renewed: Record<string, unknown> | null = null;
  if ((!response || response.status === 401) && refresh) {
    try {
      const refreshed = await fetchBackend('refresh', {
        method: 'POST',
        headers: { authorization: `Bearer ${refresh}` },
      });
      if (refreshed.ok) renewed = await refreshed.json() as Record<string, unknown>;
    } catch {
      return NextResponse.json({ error: 'Authentication service is unavailable' }, { status: 503 });
    }
    if (renewed && typeof renewed.session_token === 'string' && typeof renewed.refresh_token === 'string') {
      access = renewed.session_token;
      try {
        response = await fetchBackend('me', { headers: { authorization: `Bearer ${access}` } });
      } catch {
        return NextResponse.json({ error: 'Authentication service is unavailable' }, { status: 503 });
      }
    }
  }

  if (!response?.ok) {
    const unauthenticated = NextResponse.json({ error: 'Not authenticated' }, { status: 401 });
    unauthenticated.cookies.delete(ACCESS_COOKIE);
    unauthenticated.cookies.delete(REFRESH_COOKIE);
    unauthenticated.cookies.delete('artha_admin_csrf');
    return unauthenticated;
  }

  const data = await response.json().catch(() => null);
  const result = NextResponse.json(data);
  if (renewed && typeof renewed.session_token === 'string' && typeof renewed.refresh_token === 'string') {
    setSessionCookies(result, {
      session_token: renewed.session_token,
      refresh_token: renewed.refresh_token,
      expires_in: Number(renewed.expires_in) || 1800,
    });
  }
  return result;
}
