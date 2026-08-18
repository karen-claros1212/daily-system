import { proxyGet } from '@/lib/api/gateway';

export const dynamic = 'force-dynamic';

/**
 * GET /api/llm/providers/[provider] — estado de un provider (BFF).
 * Requiere llm:ver (SOLO ADMINISTRADOR).
 */
export async function GET(_req: Request, { params }: { params: Promise<{ provider: string }> }) {
  const { provider } = await params;
  return proxyGet(`/api/llm/providers/${encodeURIComponent(provider)}`);
}
