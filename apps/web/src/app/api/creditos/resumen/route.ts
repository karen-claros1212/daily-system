import { proxyGet } from '@/lib/api/gateway';

export const dynamic = 'force-dynamic';

/**
 * GET /api/creditos/resumen — agregados de cartera scoped por rol (BFF).
 * Requiere creditos:ver. Los agregados (saldo_total_cartera, en_mora) se
 * calculan SOLO en el backend (hoja_viva_service.resumen_creditos); el panel
 * los consume como data, nunca los deriva en el browser.
 */
export async function GET() {
  return proxyGet('/api/creditos/resumen');
}
