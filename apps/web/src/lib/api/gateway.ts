import { NextResponse } from 'next/server';
import { cookies } from 'next/headers';
import { API_BASE } from './client';

export const SESSION_COOKIE = 'daily_admin_token';

export function isProduction() {
  return process.env.NODE_ENV === 'production';
}

export function cookieMaxAge(expiraEl?: string): number {
  if (!expiraEl) return 86400;
  const expires = new Date(expiraEl).getTime();
  if (Number.isNaN(expires)) return 86400;
  return Math.max(1, Math.round((expires - Date.now()) / 1000));
}

export async function sessionToken(): Promise<string | null> {
  const store = await cookies();
  return store.get(SESSION_COOKIE)?.value ?? null;
}

export function unauthorized() {
  return NextResponse.json({ detail: 'Unauthorized' }, { status: 401 });
}

/** Forward a server-to-server GET al backend, inyectando Bearer desde la cookie HttpOnly. */
export async function proxyGet(path: string): Promise<NextResponse> {
  const token = await sessionToken();
  if (!token) return unauthorized();
  try {
    const res = await fetch(`${API_BASE}${path}`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: 'no-store',
    });
    const body = await res.json().catch(() => ({}));
    return NextResponse.json(body, { status: res.status });
  } catch {
    return NextResponse.json({ detail: 'Gateway error', status: 'error' }, { status: 502 });
  }
}

/**
 * Forward a server-to-server POST al backend, inyectando Bearer desde la cookie
 * HttpOnly y el body (JSON) del request entrante. El browser nunca toca el
 * backend directo; el BFF conserva la autoridad del contrato (401/403/404 tal
 * cual los emite el backend, sin maquillar).
 */
export async function proxyPost(path: string, req: Request): Promise<NextResponse> {
  const token = await sessionToken();
  if (!token) return unauthorized();
  const body = await req.json().catch(() => ({}));
  try {
    const res = await fetch(`${API_BASE}${path}`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
      cache: 'no-store',
    });
    const resBody = await res.json().catch(() => ({}));
    return NextResponse.json(resBody, { status: res.status });
  } catch {
    return NextResponse.json({ detail: 'Gateway error', status: 'error' }, { status: 502 });
  }
}

/**
 * Forward server-to-server POST SIN Bearer (endpoints publicos de pre-sesion,
 * p. ej. POST /api/onboarding/negocios). El browser nunca toca el backend
 * directo; el BFF conserva la autoridad del contrato (422/409 tal cual los
 * emite el backend).
 */
export async function proxyPostPublic(path: string, req: Request): Promise<NextResponse> {
  const body = await req.json().catch(() => ({}));
  try {
    const res = await fetch(`${API_BASE}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      cache: 'no-store',
    });
    const resBody = await res.json().catch(() => ({}));
    return NextResponse.json(resBody, { status: res.status });
  } catch {
    return NextResponse.json({ detail: 'Gateway error', status: 'error' }, { status: 502 });
  }
}