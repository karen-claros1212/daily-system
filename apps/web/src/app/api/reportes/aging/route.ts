import { proxyGet } from '@/lib/api/gateway';

export const dynamic = 'force-dynamic';

export async function GET() {
  return proxyGet('/api/reportes/aging');
}
