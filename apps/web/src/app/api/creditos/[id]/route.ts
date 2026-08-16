import { proxyGet } from '@/lib/api/gateway';

export const dynamic = 'force-dynamic';

/**
 * GET /api/creditos/[id] — detalle de crédito con financiero (BFF).
 * Requiere creditos:ver. COBRADOR fuera de su ruta activa recibe 404 (sin
 * revelar existencia); INVERSIONISTA recibe cliente_nombre/cliente_id null.
 */
export async function GET(
  _request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  return proxyGet(`/api/creditos/${encodeURIComponent(id)}`);
}
