import { NextResponse } from 'next/server';
import { proxyPost } from '@/lib/api/gateway';

export const dynamic = 'force-dynamic';

/**
 * PATCH /api/usuarios/[id]/estado — activar/desactivar usuario (BFF).
 * Solo ADMINISTRADOR.
 */
export async function PATCH(
  request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  return proxyPost(`/api/usuarios/${encodeURIComponent(id)}/estado`, request);
}
