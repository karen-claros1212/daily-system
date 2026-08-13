import { NextResponse } from 'next/server';
import { API_BASE } from '@/lib/api/client';
import { sessionToken } from '@/lib/api/gateway';

export const dynamic = 'force-dynamic';

/**
 * Renovacion de sesion: obtiene un nuevo desafio de sesion usando la cookie
 * httpOnly daily_admin_token como credencial de sesion (el browser NUNCA ve
 * el JWT; el BFF lo lee de la cookie y lo inyecta como Bearer).
 *
 * 1. POST /api/auth/device/desafio   Bearer: <JWT de la cookie>
 *    -> {challenge_id, nonce, expira_el, environment}
 *
 * Devuelve ademas el device_id para que el browser firme el payload
 * daily-auth-v1. Sin cookie -> 401 (se propaga tal cual).
 */
export async function POST() {
  const token = await sessionToken();
  if (!token) {
    return NextResponse.json(
      { detail: 'Credencial de sesion (Bearer JWT o bootstrap) requerida' },
      { status: 401 },
    );
  }

  try {
    const res = await fetch(`${API_BASE}/api/auth/device/desafio`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: '{}',
      cache: 'no-store',
    });
    const payload = await res.json().catch(() => ({}));
    if (!res.ok) {
      return NextResponse.json(payload, { status: res.status });
    }
    return NextResponse.json({
      challenge_id: (payload as { challenge_id?: string }).challenge_id ?? '',
      nonce: (payload as { nonce?: string }).nonce ?? '',
      expira_el: (payload as { expira_el?: string }).expira_el ?? '',
      environment: (payload as { environment?: string }).environment ?? '',
      device_id: deviceIdFromToken(token),
    });
  } catch {
    return NextResponse.json({ detail: 'Gateway error', status: 'error' }, { status: 502 });
  }
}

/** Extrae device_id del payload del JWT (sin validar firma; solo claims). */
function deviceIdFromToken(token: string): string {
  try {
    const parts = token.split('.');
    if (parts.length !== 3) return '';
    const payload = parts[1];
    let b64 = payload.replace(/-/g, '+').replace(/_/g, '/');
    while (b64.length % 4 !== 0) b64 += '=';
    const json = JSON.parse(atob(b64));
    return String(json.device_id ?? '');
  } catch {
    return '';
  }
}