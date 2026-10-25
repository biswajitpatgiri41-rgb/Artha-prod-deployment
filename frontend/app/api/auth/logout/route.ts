import { NextRequest, NextResponse } from 'next/server';
import { ACCESS_COOKIE, backendAuthUrl, clearSessionCookies, hasValidCsrf } from '@/lib/server-auth';

export const runtime = 'nodejs';

export async function POST(request: NextRequest) {
  if (!hasValidCsrf(request)) return NextResponse.json({ error: 'CSRF verification failed' }, { status: 403 });
  const access = request.cookies.get(ACCESS_COOKIE)?.value;
  if (access) {
    let upstream: Response;
    try {
      upstream = await fetch(backendAuthUrl('logout'), {
        method: 'POST', headers: { authorization: `Bearer ${access}` },
        cache: 'no-store', signal: AbortSignal.timeout(15_000),
      });
    } catch {
      return NextResponse.json({ error: 'Authentication service is unavailable; session was not cleared' }, { status: 503 });
    }
    if (!upstream.ok && upstream.status !== 401) return NextResponse.json({ error: 'Could not revoke the current session' }, { status: 503 });
  }
  const response = NextResponse.json({ ok: true });
  clearSessionCookies(response);
  return response;
}
