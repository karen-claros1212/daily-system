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