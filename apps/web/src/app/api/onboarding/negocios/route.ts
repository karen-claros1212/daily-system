import { proxyPostPublic } from '@/lib/api/gateway';

export const dynamic = 'force-dynamic';

/** POST /api/onboarding/negocios via BFF (publico, pre-sesion, sin Bearer). */
export async function POST(req: Request) {
  return proxyPostPublic('/api/onboarding/negocios', req);
}
