import { NextResponse } from 'next/server';
import { sessionToken } from '@/lib/api/gateway';
import { API_BASE } from '@/lib/api/client';

export const dynamic = 'force-dynamic';

/**
 * GET /api/auth/me (BFF) — identidad canonica de la sesion.
 *
 * Lee la cookie httpOnly daily_admin_token y la inyecta como Bearer hacia
 * /api/auth/me del backend. El browser NUNCA ve el JWT: la identidad sale del
 * backend (rol derivado de la DB en cada request), nunca del metodo de login
 * ni de un claim legible por el cliente.
 *
 * Sin cookie -> 401 (se propaga tal cual, sin fabricar identidad).
 * Con cookie pero rol/tenancy invalido -> el backend ya devuelve 401 here.
 */
export async function GET() {
  const token = await sessionToken();
  if (!token) {
    return NextResponse.json(
      { detail: 'Credencial de sesion (Bearer JWT) requerida' },
      { status: 401 },
    );
  }

  try {
    const res = await fetch(`${API_BASE}/api/auth/me`, {
      method: 'GET',
      headers: {
        Authorization: `Bearer ${token}`,
      },
      cache: 'no-store',
    });
    const payload = await res.json().catch(() => ({}));
    return NextResponse.json(payload, { status: res.status });
  } catch {
    return NextResponse.json(
      { detail: 'Gateway error', status: 'error' },
      { status: 502 },
    );
  }
}