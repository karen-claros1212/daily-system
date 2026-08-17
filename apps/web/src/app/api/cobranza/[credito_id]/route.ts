import { proxyGet } from '@/lib/api/gateway';

export const dynamic = 'force-dynamic';

export async function GET(_request: Request, { params }: { params: Promise<{ credito_id: string }> }) {
  const { credito_id } = await params;
  return proxyGet(`/api/cobranza/${credito_id}`);
}
