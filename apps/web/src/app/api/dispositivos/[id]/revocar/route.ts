import { proxyPost } from '@/lib/api/gateway';

export const dynamic = 'force-dynamic';

/** POST /api/dispositivos/{id}/revocar via BFF (ADMINISTRADOR). */
export async function POST(_req: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return proxyPost(`/api/dispositivos/${encodeURIComponent(id)}/revocar`, _req);
}
