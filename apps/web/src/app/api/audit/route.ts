import { NextResponse } from 'next/server';
import { proxyGet } from '@/lib/api/gateway';

export const dynamic = 'force-dynamic';

/**
 * GET /api/audit — consultar logs de auditoria (BFF).
 * Solo ADMINISTRADOR.
 */
export async function GET(request: Request) {
  const url = new URL(request.url);
  const params = new URLSearchParams();
  const action = url.searchParams.get('action');
  const entity_type = url.searchParams.get('entity_type');
  const actor_id = url.searchParams.get('actor_id');
  const since = url.searchParams.get('since');
  const limit = url.searchParams.get('limit');
  if (action) params.set('action', action);
  if (entity_type) params.set('entity_type', entity_type);
  if (actor_id) params.set('actor_id', actor_id);
  if (since) params.set('since', since);
  if (limit) params.set('limit', limit);
  const query = params.toString();
  return proxyGet(`/api/audit${query ? '?' + query : ''}`);
}
