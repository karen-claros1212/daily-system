import { proxyGet, proxyPatch } from '@/lib/api/gateway';

export const dynamic = 'force-dynamic';

/**
 * GET /api/clientes/[id] — Cliente 360 (BFF).
 * Requiere clientes:ver (ADMINISTRADOR | COBRADOR scoped a su ruta).
 */
export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  return proxyGet(`/api/clientes/${encodeURIComponent(id)}`);
}

/**
 * PATCH /api/clientes/[id] — editar cliente (BFF).
 * Requiere clientes:gestionar (solo ADMINISTRADOR).
 */
export async function PATCH(
  request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  return proxyPatch(`/api/clientes/${encodeURIComponent(id)}`, request);
}
