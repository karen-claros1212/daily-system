import { proxyGet } from '@/lib/api/gateway';

export const dynamic = 'force-dynamic';

export async function GET(request: Request) {
  const url = new URL(request.url);
  const periodo = url.searchParams.get('periodo') ?? 'hoy';
  const fecha_inicio = url.searchParams.get('fecha_inicio');
  const fecha_fin = url.searchParams.get('fecha_fin');
  let path = `/api/reportes/rutas?periodo=${periodo}`;
  if (fecha_inicio) path += `&fecha_inicio=${fecha_inicio}`;
  if (fecha_fin) path += `&fecha_fin=${fecha_fin}`;
  return proxyGet(path);
}
