import { proxyPatch } from '@/lib/api/gateway';

export const dynamic = 'force-dynamic';

/** PATCH /api/rutas/:id/reasignar (BFF) — S4 R1→R2 (rutas:reasignar, solo ADMINISTRADOR). */
export async function PATCH(req: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return proxyPatch(`/api/rutas/${encodeURIComponent(id)}/reasignar`, req);
}
