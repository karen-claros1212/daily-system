
import { proxyGet, proxyPatch } from '@/lib/api/gateway';

export const dynamic = 'force-dynamic';

/**
 * GET /api/usuarios/[id] — obtener usuario (BFF).
 * Solo ADMINISTRADOR.
 */
export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  return proxyGet(`/api/usuarios/${encodeURIComponent(id)}`);
}

/**
 * PATCH /api/usuarios/[id] — editar usuario (BFF).
 * Solo ADMINISTRADOR.
 */
export async function PATCH(
  request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  return proxyPatch(`/api/usuarios/${encodeURIComponent(id)}`, request);
}
