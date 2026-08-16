import { proxyGet, proxyPost } from '@/lib/api/gateway';

export const dynamic = 'force-dynamic';

export async function GET(req: Request) {
  const url = new URL(req.url);
  const query = url.searchParams.toString();
  return proxyGet(`/api/rutas${query ? `?${query}` : ''}`);
}

export async function POST(req: Request) {
  return proxyPost('/api/rutas', req);
}