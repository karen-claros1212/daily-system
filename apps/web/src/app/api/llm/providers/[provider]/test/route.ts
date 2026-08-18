import { proxyPost } from '@/lib/api/gateway';

export const dynamic = 'force-dynamic';

/**
 * POST /api/llm/providers/[provider]/test — test de conexión (BFF).
 * Requiere llm:gestionar (SOLO ADMINISTRADOR). El backend emite una petición
 * mínima, controlada y sanitizada; el BFF conserva la respuesta tipada.
 */
export async function POST(_req: Request, { params }: { params: Promise<{ provider: string }> }) {
  const { provider } = await params;
  return proxyPost(`/api/llm/providers/${encodeURIComponent(provider)}/test`, _req);
}
