import { proxyPut } from '@/lib/api/gateway';

export const dynamic = 'force-dynamic';

/**
 * PUT /api/llm/providers/[provider]/config — config no secreta (BFF).
 * Requiere llm:gestionar (SOLO ADMINISTRADOR).
 */
export async function PUT(req: Request, { params }: { params: Promise<{ provider: string }> }) {
  const { provider } = await params;
  return proxyPut(`/api/llm/providers/${encodeURIComponent(provider)}/config`, req);
}
