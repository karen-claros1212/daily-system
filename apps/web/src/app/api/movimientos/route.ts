import { proxyGet } from '@/lib/api/gateway';

export const dynamic = 'force-dynamic';

const SORT_ALLOWLIST = new Set(['creado_el', 'monto', 'tipo']);
const ORDER_ALLOWLIST = new Set(['asc', 'desc']);

/**
 * GET /api/movimientos — listar movimientos (read model web) del negocio (BFF).
 * Requiere movimientos:ver (ADMINISTRADOR | INVERSIONISTA | COBRADOR scoped).
 * Proxies a /api/movimientos/web del backend.
 *
 * Contrato sort/order: si el valor no está en el allowlist, se devuelve 422
 * (no se convierte silenciosamente a un valor válido).
 */
export async function GET(request: Request) {
  const url = new URL(request.url);
  const params = new URLSearchParams();
  const q = url.searchParams.get('q');
  const tipo = url.searchParams.get('tipo');
  const naturaleza = url.searchParams.get('naturaleza');
  const ruta_id = url.searchParams.get('ruta_id');
  const limit = url.searchParams.get('limit');
  const offset = url.searchParams.get('offset');
  const sort = url.searchParams.get('sort') ?? 'creado_el';
  const order = url.searchParams.get('order') ?? 'desc';
  if (q) params.set('q', q);
  if (tipo) params.set('tipo', tipo);
  if (naturaleza) params.set('naturaleza', naturaleza);
  if (ruta_id) params.set('ruta_id', ruta_id);
  if (limit) params.set('limit', limit);
  if (offset) params.set('offset', offset);
  params.set('sort', sort);
  params.set('order', order);
  const query = params.toString();
  return proxyGet(`/api/movimientos/web${query ? '?' + query : ''}`);
}
