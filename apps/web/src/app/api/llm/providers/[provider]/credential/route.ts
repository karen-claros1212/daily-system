import { proxyDelete, proxyPut } from '@/lib/api/gateway';

export const dynamic = 'force-dynamic';

/**
 * PUT /api/llm/providers/[provider]/credential — set BYOK (BFF).
 * Requiere llm:gestionar (SOLO ADMINISTRADOR). La clave viaja en el body y se
 * cifra en el backend (SecretStore); el BFF no la persiste ni la loguea.
 */
export async function PUT(req: Request, { params }: { params: Promise<{ provider: string }> }) {
  const { provider } = await params;
  return proxyPut(`/api/llm/providers/${encodeURIComponent(provider)}/credential`, req);
}

/**
 * DELETE /api/llm/providers/[provider]/credential — eliminar BYOK (BFF).
 * Requiere llm:gestionar (SOLO ADMINISTRADOR).
 */
export async function DELETE(_req: Request, { params }: { params: Promise<{ provider: string }> }) {
  const { provider } = await params;
  return proxyDelete(`/api/llm/providers/${encodeURIComponent(provider)}/credential`);
}
