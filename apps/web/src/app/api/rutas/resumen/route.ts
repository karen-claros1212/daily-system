import { proxyGet } from '@/lib/api/gateway';

export const dynamic = 'force-dynamic';

/** GET /api/rutas/resumen (BFF) — conteos por estado (rutas:ver | ruta:ver). */
export async function GET() {
  return proxyGet('/api/rutas/resumen');
}
