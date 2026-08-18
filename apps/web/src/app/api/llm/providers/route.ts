import { proxyGet } from '@/lib/api/gateway';

export const dynamic = 'force-dynamic';

/**
 * GET /api/llm/providers — catálogo de los 6 providers + estado (BFF).
 * Requiere llm:ver (SOLO ADMINISTRADOR). El browser nunca toca el backend
 * directo; el BFF conserva la autoridad del contrato (401/403 tal cual).
 */
export async function GET() {
  return proxyGet('/api/llm/providers');
}
