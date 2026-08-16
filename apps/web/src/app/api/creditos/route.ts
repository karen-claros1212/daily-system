import { proxyGet, proxyPost } from '@/lib/api/gateway';

export const dynamic = 'force-dynamic';

const SORT_ALLOWLIST = new Set([
  'fecha_inicio',
  'monto',
  'total',
  'cuota',
  'periodicidad',
  'estado',
  'saldo',
]);

/**
 * GET /api/creditos — listar créditos (read model) del negocio (BFF).
 * Requiere creditos:ver (ADMINISTRADOR | COBRADOR scoped a su ruta |
 * INVERSIONISTA con PII minimizada). El financiero viene del backend
 * (hoja_viva_service.resumen_creditos) — nunca se calcula en el browser.
 */
export async function GET(request: Request) {
  const url = new URL(request.url);
  const params = new URLSearchParams();
  const q = url.searchParams.get('q');
  const estado = url.searchParams.get('estado');
  const ruta_id = url.searchParams.get('ruta_id');
  const limit = url.searchParams.get('limit');
  const offset = url.searchParams.get('offset');
  let sort = url.searchParams.get('sort') ?? 'fecha_inicio';
  const order = url.searchParams.get('order') ?? 'desc';
  if (q) params.set('q', q);
  if (estado) params.set('estado', estado);
  if (ruta_id) params.set('ruta_id', ruta_id);
  if (limit) params.set('limit', limit);
  if (offset) params.set('offset', offset);
  if (!SORT_ALLOWLIST.has(sort)) sort = 'fecha_inicio';
  params.set('sort', sort);
  if (order === 'asc' || order === 'desc') params.set('order', order);
  const query = params.toString();
  return proxyGet(`/api/creditos${query ? '?' + query : ''}`);
}

/**
 * POST /api/creditos — crear crédito (BFF).
 * Requiere creditos:gestionar (solo ADMINISTRADOR). COBRADOR/INVERSIONISTA
 * reciben 403 tal cual lo emite el backend.
 */
export async function POST(request: Request) {
  return proxyPost('/api/creditos', request);
}
