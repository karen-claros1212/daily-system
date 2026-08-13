import { NextRequest, NextResponse } from 'next/server';
import { API_BASE } from '@/lib/api/client';

export const dynamic = 'force-dynamic';

export async function POST(req: NextRequest) {
  const body = await req.json().catch(() => ({}) as Record<string, unknown>);
  try {
    const res = await fetch(`${API_BASE}/api/auth/device/desafio`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body ?? {}),
      cache: 'no-store',
    });
    const payload = await res.json().catch(() => ({}));
    return NextResponse.json(payload, { status: res.status });
  } catch {
    return NextResponse.json({ detail: 'Gateway error', status: 'error' }, { status: 502 });
  }
}