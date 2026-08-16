import { NextResponse } from 'next/server';
import { proxyGet, proxyPost } from '@/lib/api/gateway';

export const dynamic = 'force-dynamic';

/**
 * GET /api/usuarios — listar usuarios del negocio (BFF).
 * Solo ADMINISTRADOR.
 */
export async function GET(request: Request) {
  const url = new URL(request.url);
  const rol = url.searchParams.get('rol') ?? undefined;
  const activo = url.searchParams.get('activo') ?? undefined;
  const params = new URLSearchParams();
  if (rol) params.set('rol', rol);
  if (activo) params.set('activo', activo);
  const query = params.toString();
  return proxyGet(`/api/usuarios${query ? '?' + query : ''}`);
}

/**
 * POST /api/usuarios — crear usuario (BFF).
 * Solo ADMINISTRADOR.
 */
export async function POST(request: Request) {
  return proxyPost('/api/usuarios', request);
}
