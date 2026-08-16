
import { proxyPost } from '@/lib/api/gateway';

export const dynamic = 'force-dynamic';

/**
 * POST /api/activaciones/codigos — generar código de activación (BFF).
 * Solo ADMINISTRADOR.
 *
 * Reenvía el body al backend (/api/activaciones/codigos) que valida:
 *   - ctx.is_admin() -> 403 si no es admin
 *   - usuario_id existe y pertenece al negocio -> 404/409
 *   - genera código de un solo uso -> 201
 */
export async function POST(request: Request) {
  return proxyPost('/api/activaciones/codigos', request);
}
