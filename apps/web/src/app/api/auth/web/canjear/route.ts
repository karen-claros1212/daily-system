import { NextRequest, NextResponse } from 'next/server';
import { API_BASE } from '@/lib/api/client';

export const dynamic = 'force-dynamic';

/**
 * Paso 2 del login Web: canjea el codigo de activacion y resuelve PRIMER
 * desafio de sesion en una sola tanda.
 *
 * contRATO real:
 *   1. POST /api/activaciones/canjear {intento_id, firma}
 *      -> {dispositivo_id, credencial_bootstrap, expira_el}  (public)
 *   2. POST /api/auth/device/desafio   Bearer: credencial_bootstrap
 *      -> {challenge_id, nonce, expira_el, environment}
 *
 * La credencial_bootstrap NUNCA sale del server: se usa aqui, en memoria, y
 * se descarta. El browser recibe solo el challenge de sesion para firmar con
 * su clave privada local.
 *
 * Un canje de activacion consumido/reintentado (replay de intento_id) devuelve
 * 409/400 tal cual lo propaga el backend; el BFF no maquilla.
 */
export async function POST(req: NextRequest) {
  const body = await req.json().catch(() => ({})) as {
    intento_id?: string;
    firma?: string;
  };
  if (!body.intento_id || !body.firma) {
    return NextResponse.json(
      { detail: 'intento_id y firma son requeridos' },
      { status: 422 },
    );
  }

  try {
    // 1. Canje de activacion (publico): emite credencial_bootstrap.
    const canjeRes = await fetch(`${API_BASE}/api/activaciones/canjear`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        intento_id: body.intento_id,
        firma: body.firma,
      }),
      cache: 'no-store',
    });
    const canje = await canjeRes.json().catch(() => ({}));
    if (!canjeRes.ok) {
      return NextResponse.json(canje, { status: canjeRes.status });
    }
    const bootstrap = String((canje as { credencial_bootstrap?: string }).credencial_bootstrap ?? '');
    if (!bootstrap) {
      return NextResponse.json(
        { detail: 'Respuesta inválida del backend (sin bootstrap)' },
        { status: 502 },
      );
    }

    // 2. Primer desafio de sesion autenticado con bootstrap (en memoria).
    const desRes = await fetch(`${API_BASE}/api/auth/device/desafio`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${bootstrap}`,
      },
      body: '{}',
      cache: 'no-store',
    });
    const desafio = await desRes.json().catch(() => ({}));
    if (!desRes.ok) {
      return NextResponse.json(desafio, { status: desRes.status });
    }

    void bootstrap; // solo en memoria; nunca en la respuesta
    return NextResponse.json({
      dispositivo_id: (canje as { dispositivo_id?: string }).dispositivo_id ?? '',
      negocio_id: (canje as { negocio_id?: string }).negocio_id ?? '',
      // usuario_id es canónico (cualquier rol); cobrador_id se mantiene como
      // alias legado para compatibilidad de consumidores.
      usuario_id: (canje as { usuario_id?: string }).usuario_id ??
        (canje as { cobrador_id?: string }).cobrador_id ?? '',
      cobrador_id: (canje as { cobrador_id?: string }).cobrador_id ??
        (canje as { usuario_id?: string }).usuario_id ?? '',
      expira_el: (canje as { expira_el?: string }).expira_el ?? '',
      challenge_id: (desafio as { challenge_id?: string }).challenge_id ?? '',
      nonce: (desafio as { nonce?: string }).nonce ?? '',
      challenge_expira_el: (desafio as { expira_el?: string }).expira_el ?? '',
      environment: (desafio as { environment?: string }).environment ?? '',
    });
  } catch {
    return NextResponse.json({ detail: 'Gateway error', status: 'error' }, { status: 502 });
  }
}