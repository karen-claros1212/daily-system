import { proxyPost } from '@/lib/api/gateway';

export const dynamic = 'force-dynamic';

/** POST /api/activaciones/codigos via BFF (ADMINISTRADOR). */
export async function POST(req: Request) {
  return proxyPost('/api/activaciones/codigos', req);
}
