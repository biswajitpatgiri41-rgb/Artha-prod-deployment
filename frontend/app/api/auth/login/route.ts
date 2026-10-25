import { NextRequest, NextResponse } from 'next/server';
import { backendAuthUrl, setSessionCookies } from '@/lib/server-auth';

export const runtime = 'nodejs';

export async function POST(request: NextRequest) {
  let input: unknown;
  try { input = await request.json(); } catch { return NextResponse.json({ error: 'Invalid request body' }, { status: 400 }); }
  if (!input || typeof input !== 'object') return NextResponse.json({ error: 'Invalid request body' }, { status: 400 });
  const body = input as Record<string, unknown>;
  if (typeof body.email !== 'string' || typeof body.password !== 'string' || body.email.length > 320 || body.password.length > 1024) {
    return NextResponse.json({ error: 'Email and password are required' }, { status: 400 });
  }
  if (body.totp_code !== undefined && (typeof body.totp_code !== 'string' || !/^\d{6}$/.test(body.totp_code))) {
    return NextResponse.json({ error: 'Enter a valid six-digit authenticator code' }, { status: 400 });
  }
  let upstream: Response;
  try {
    upstream = await fetch(backendAuthUrl('login'), {
      method: 'POST', headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ email: body.email, password: body.password, totp_code: body.totp_code }),
      cache: 'no-store', signal: AbortSignal.timeout(15_000),
    });
  } catch {
    return NextResponse.json({ error: 'Authentication service is unavailable' }, { status: 503 });
  }
  const session = await upstream.json().catch(() => null) as Record<string, unknown> | null;
  if (!upstream.ok || !session || typeof session.session_token !== 'string' || typeof session.refresh_token !== 'string') {
    const status = [400, 401, 403, 429, 503].includes(upstream.status) ? upstream.status : 502;
    return NextResponse.json({ error: status === 401 ? 'Invalid credentials or authenticator code' : 'Sign-in could not be completed' }, { status });
  }
  const response = NextResponse.json({ user: session.user });
  setSessionCookies(response, {
    session_token: session.session_token, refresh_token: session.refresh_token,
    expires_in: Number(session.expires_in) || 1800,
  });
  return response;
}
