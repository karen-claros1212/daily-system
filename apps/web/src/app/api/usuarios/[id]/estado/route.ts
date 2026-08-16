
import { proxyPatch } from '@/lib/api/gateway';

export const dynamic = 'force-dynamic';

/**
 * PATCH /api/usuarios/[id]/estado — activar/desactivar usuario (BFF).
 * Solo ADMINISTRADOR.
 * Reenvia el query param activo (0|1) al backend.
 */
export async function PATCH(
  request: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  const url = new URL(request.url);
  const activo = url.searchParams.get('activo');
  return proxyPatch(
    `/api/usuarios/${encodeURIComponent(id)}/estado?activo=${activo}`,
    request,
  );
}
