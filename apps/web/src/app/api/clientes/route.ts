import { proxyGet, proxyPost } from '@/lib/api/gateway';

export const dynamic = 'force-dynamic';

/**
 * GET /api/clientes — listar clientes del negocio (BFF).
 * Requiere clientes:ver (ADMINISTRADOR | COBRADOR scoped a su ruta).
 */
export async function GET(request: Request) {
  const url = new URL(request.url);
  const params = new URLSearchParams();
  const q = url.searchParams.get('q');
  const tipo_documento = url.searchParams.get('tipo_documento');
  const identity_status = url.searchParams.get('identity_status');
  const limit = url.searchParams.get('limit');
  const offset = url.searchParams.get('offset');
  if (q) params.set('q', q);
  if (tipo_documento) params.set('tipo_documento', tipo_documento);
  if (identity_status) params.set('identity_status', identity_status);
  if (limit) params.set('limit', limit);
  if (offset) params.set('offset', offset);
  const query = params.toString();
  return proxyGet(`/api/clientes${query ? '?' + query : ''}`);
}

/**
 * POST /api/clientes — crear cliente (BFF).
 * Requiere clientes:gestionar (solo ADMINISTRADOR).
 */
export async function POST(request: Request) {
  return proxyPost('/api/clientes', request);
}
