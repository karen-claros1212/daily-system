import { proxyGet, proxyPost } from '@/lib/api/gateway';

export const dynamic = 'force-dynamic';

const SORT_ALLOWLIST = new Set(['days_past_due', 'overdue_amount', 'total_outstanding', 'oldest_unpaid_due_date', 'cliente_nombre', 'priority_score']);

export async function GET(request: Request) {
  const url = new URL(request.url);
  const params = new URLSearchParams();
  const q = url.searchParams.get('q');
  const bucket = url.searchParams.get('bucket');
  const ruta_id = url.searchParams.get('ruta_id');
  const estado = url.searchParams.get('estado');
  const priority = url.searchParams.get('priority');
  const dpd_min = url.searchParams.get('dpd_min');
  const dpd_max = url.searchParams.get('dpd_max');
  const limit = url.searchParams.get('limit');
  const offset = url.searchParams.get('offset');
  const sort = url.searchParams.get('sort') ?? 'days_past_due';
  const order = url.searchParams.get('order') ?? 'desc';
  if (q) params.set('q', q);
  if (bucket) params.set('bucket', bucket);
  if (ruta_id) params.set('ruta_id', ruta_id);
  if (estado) params.set('estado', estado);
  if (priority) params.set('priority', priority);
  if (dpd_min) params.set('dpd_min', dpd_min);
  if (dpd_max) params.set('dpd_max', dpd_max);
  if (limit) params.set('limit', limit);
  if (offset) params.set('offset', offset);
  params.set('sort', sort);
  params.set('order', order);
  const query = params.toString();
  return proxyGet(`/api/cobranza/web${query ? '?' + query : ''}`);
}
