import { proxyGet } from '@/lib/api/gateway';

export const dynamic = 'force-dynamic';

/**
 * GET /api/movimientos/resumen — resumen financiero (BFF).
 * Proxies a /api/movimientos/resumen del backend.
 */
export async function GET() {
  return proxyGet('/api/movimientos/resumen');
}
