import { proxyGet } from '@/lib/api/gateway';

export const dynamic = 'force-dynamic';

const SORT_ALLOWLIST = new Set(['creado_el', 'monto', 'tipo']);

/**
 * GET /api/movimientos — listar movimientos (read model web) del negocio (BFF).
 * Requiere movimientos:ver (ADMINISTRADOR | INVERSIONISTA) o COBRADOR scoped.
 * Proxies a /api/movimientos/web del backend.
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
  let sort = url.searchParams.get('sort') ?? 'creado_el';
  const order = url.searchParams.get('order') ?? 'desc';
  if (q) params.set('q', q);
  if (tipo) params.set('tipo', tipo);
  if (naturaleza) params.set('naturaleza', naturaleza);
  if (ruta_id) params.set('ruta_id', ruta_id);
  if (limit) params.set('limit', limit);
  if (offset) params.set('offset', offset);
  if (!SORT_ALLOWLIST.has(sort)) sort = 'creado_el';
  params.set('sort', sort);
  if (order === 'asc' || order === 'desc') params.set('order', order);
  const query = params.toString();
  return proxyGet(`/api/movimientos/web${query ? '?' + query : ''}`);
}
