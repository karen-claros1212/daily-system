import { proxyPost } from '@/lib/api/gateway';

export const dynamic = 'force-dynamic';

export async function POST(request: Request, { params }: { params: Promise<{ promesa_id: string }> }) {
  const { promesa_id } = await params;
  return proxyPost(`/api/cobranza/promesas/${promesa_id}/cumplir`, request);
}
