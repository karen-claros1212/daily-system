import { proxyGet } from '@/lib/api/gateway';

export const dynamic = 'force-dynamic';

/** GET /api/dispositivos via BFF (lista autorizada del negocio, scoped al ctx). */
export async function GET() {
  return proxyGet('/api/dispositivos');
}
