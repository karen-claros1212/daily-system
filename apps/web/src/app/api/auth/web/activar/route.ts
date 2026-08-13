import { NextRequest, NextResponse } from 'next/server';
import { API_BASE } from '@/lib/api/client';

export const dynamic = 'force-dynamic';

/**
 * Paso 1 del login Web: solicita el desafio de activacion (contrato real).
 *   1. /api/activaciones/desafio -> {token, clave_publica} -> DesafioResponse
 *
 * Público en el backend, como el contrato exige. El BFF NO añade credencial
 * alguna: el desafio de activacion no requiere Bearer (el contrato lo define
 * publico), el de SESION si (lo resuelve /web/canjear con bootstrap).
 */
export async function POST(req: NextRequest) {
  const body = await req.json().catch(() => ({})) as {
    token?: string;
    clave_publica?: string;
  };
  if (!body.token || !body.clave_publica) {
    return NextResponse.json(
      { detail: 'token y clave_publica son requeridos' },
      { status: 422 },
    );
  }

  try {
    const res = await fetch(`${API_BASE}/api/activaciones/desafio`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        token: body.token,
        clave_publica: body.clave_publica,
        modelo: 'web',
        plataforma: 'web',
      }),
      cache: 'no-store',
    });
    const payload = await res.json().catch(() => ({}));
    return NextResponse.json(payload, { status: res.status });
  } catch {
    return NextResponse.json({ detail: 'Gateway error', status: 'error' }, { status: 502 });
  }
}