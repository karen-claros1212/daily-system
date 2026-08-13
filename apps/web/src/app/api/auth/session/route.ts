import { NextRequest, NextResponse } from 'next/server';
import { API_BASE } from '@/lib/api/client';
import { SESSION_COOKIE, cookieMaxAge, isProduction } from '@/lib/api/gateway';

export const dynamic = 'force-dynamic';

export async function POST(req: NextRequest) {
  const body = await req.json().catch(() => ({}) as Record<string, unknown>);
  const challengeId = String(body.challenge_id ?? body.desafio_id ?? '');
  const firma = String(body.firma ?? '');

  if (!challengeId || !firma) {
    return NextResponse.json({ detail: 'challenge_id y firma son requeridos' }, { status: 422 });
  }

  try {
    const res = await fetch(`${API_BASE}/api/auth/device/canjear`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ challenge_id: challengeId, firma }),
      cache: 'no-store',
    });

    const payload = await res.json().catch(() => ({}));

    if (!res.ok) {
      return NextResponse.json(payload, { status: res.status });
    }

    const token = String(payload.token ?? '');
    if (!token) {
      return NextResponse.json({ detail: 'Respuesta inválida del backend' }, { status: 502 });
    }

    const response = NextResponse.json({ ok: true });
    response.cookies.set(SESSION_COOKIE, token, {
      httpOnly: true,
      secure: isProduction(),
      sameSite: 'lax',
      path: '/',
      maxAge: cookieMaxAge(String(payload.expira_el ?? '')),
    });
    return response;
  } catch {
    return NextResponse.json({ detail: 'Gateway error', status: 'error' }, { status: 502 });
  }
}