import { proxyPost } from '@/lib/api/gateway';

export const dynamic = 'force-dynamic';

export async function POST(request: Request) {
  return proxyPost('/api/cobranza/promesas', request);
}
