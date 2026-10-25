import { NextRequest, NextResponse } from 'next/server';
import { ACCESS_COOKIE, REFRESH_COOKIE, backendApiUrl, backendAuthUrl, clearSessionCookies, hasValidCsrf, setSessionCookies } from '@/lib/server-auth';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';
const MAX_BODY_BYTES = 50 * 1024 * 1024;
const EVIDENCE_STATIC_PATHS = new Set(['evidence/config', 'evidence/upload', 'evidence/search', 'evidence/events']);

function allowedPath(path: string): boolean {
  return path === 'research'
    || /^research\/[0-9a-f-]{36}(?:\/(?:events|report))?$/.test(path)
    || path === 'assistant/chat'
    || EVIDENCE_STATIC_PATHS.has(path)
    || /^evidence\/run\/[0-9a-f-]{36}$/.test(path)
    || /^evidence\/[A-Za-z0-9_-]{1,128}$/.test(path);
}

async function renew(refresh: string): Promise<Record<string, unknown> | null> {
  try {
    const response = await fetch(backendAuthUrl('refresh'), {
      method: 'POST', headers: { authorization: `Bearer ${refresh}` },
      cache: 'no-store', signal: AbortSignal.timeout(15_000),
    });
    if (!response.ok) return null;
    const value = await response.json() as Record<string, unknown>;
    return typeof value.session_token === 'string' && typeof value.refresh_token === 'string' ? value : null;
  } catch { return null; }
}

async function proxy(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const { path: segments } = await context.params;
  const path = (segments ?? []).join('/');
  if (!allowedPath(path)) return NextResponse.json({ error: 'API path is not permitted' }, { status: 404 });
  if (!['GET', 'POST', 'DELETE'].includes(request.method)) return NextResponse.json({ error: 'Method is not permitted' }, { status: 405 });
  if (process.env.NODE_ENV === 'production' && request.method !== 'GET' && !hasValidCsrf(request)) {
    return NextResponse.json({ error: 'CSRF verification failed' }, { status: 403 });
  }

  let access = request.cookies.get(ACCESS_COOKIE)?.value;
  const refresh = request.cookies.get(REFRESH_COOKIE)?.value;
  let renewed: Record<string, unknown> | null = null;
  if (!access && refresh) {
    renewed = await renew(refresh);
    if (renewed) access = String(renewed.session_token);
  }
  if (!access && process.env.NODE_ENV === 'production') return NextResponse.json({ error: 'Sign-in required' }, { status: 401 });

  const declared = Number(request.headers.get('content-length') ?? 0);
  if (declared > MAX_BODY_BYTES) return NextResponse.json({ error: 'Request body is too large' }, { status: 413 });
  const headers = new Headers();
  const contentType = request.headers.get('content-type');
  const filename = request.headers.get('x-filename');
  if (contentType) headers.set('content-type', contentType);
  if (filename) headers.set('x-filename', filename.slice(0, 255));
  if (access) headers.set('authorization', `Bearer ${access}`);

  let body: ArrayBuffer | undefined;
  if (request.method !== 'GET') {
    body = await request.arrayBuffer();
    if (body.byteLength > MAX_BODY_BYTES) return NextResponse.json({ error: 'Request body is too large' }, { status: 413 });
  }
  const url = `${backendApiUrl(path)}${request.nextUrl.search}`;
  const send = (token: string | undefined) => {
    if (token) headers.set('authorization', `Bearer ${token}`);
    else headers.delete('authorization');
    return fetch(url, { method: request.method, headers, body, cache: 'no-store', signal: AbortSignal.timeout(320_000) });
  };
  let upstream: Response;
  try {
    upstream = await send(access);
    if (upstream.status === 401 && refresh && !renewed) {
      renewed = await renew(refresh);
      if (renewed) {
        access = String(renewed.session_token);
        upstream = await send(access);
      }
    }
  } catch {
    return NextResponse.json({ error: 'Backend service is unavailable' }, { status: 503 });
  }

  const responseHeaders = new Headers({
    'cache-control': 'no-store',
    'content-type': upstream.headers.get('content-type') ?? 'application/json',
  });
  const disposition = upstream.headers.get('content-disposition');
  if (disposition) responseHeaders.set('content-disposition', disposition);
  const response = new NextResponse(await upstream.arrayBuffer(), { status: upstream.status, headers: responseHeaders });
  if (renewed) {
    setSessionCookies(response, {
      session_token: String(renewed.session_token),
      refresh_token: String(renewed.refresh_token),
      expires_in: Number(renewed.expires_in) || 1800,
    });
  } else if (upstream.status === 401 && refresh) {
    clearSessionCookies(response);
  }
  return response;
}

export const GET = proxy;
export const POST = proxy;
export const DELETE = proxy;
