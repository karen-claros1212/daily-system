import { cookies } from 'next/headers';
import { redirect } from 'next/navigation';
import { AppShell } from '@/components/AppShell';
import { Forbidden } from '@/components/Forbidden';
import { DashboardInversionista } from '@/components/DashboardInversionista';
import { DashboardCobrador } from '@/components/DashboardCobrador';
import { DashboardEjecutivo } from '@/components/DashboardEjecutivo';
import { canViewFinancial, fetchSession, hasCapability, isCobrador } from '@/lib/session';
import { API_BASE, type InversionistaSummary } from '@/lib/api/client';

export const dynamic = 'force-dynamic';

/**
 * /dashboard despacha la superficie según el rol resuelto por /api/auth/me:
 *
 *   - COBRADOR       -> superficie de campo (jornada/ruta), SIN financiero.
 *   - ADMINISTRADOR  -> Dashboard Ejecutivo (W8): KPIs del día, tendencia 7d,
 *                       concentración de riesgo, alertas. Capability
 *                       dashboard:ejecutivo (solo ADMIN en W8).
 *   - INVERSIONISTA  -> DashboardInversionista (W9): snapshot financiero
 *                       read-only (KPIs, tendencia 7d, riesgo, exposición por
 *                       ruta, promesas). Capability inversionista:resumen.
 *   - Otro/desconocid-> Forbidden 403 controlado (una sesión válida con
 *                        permisos insuficientes NO es una sesión inexistente,
 *                        así que no redirige al login).
 *
 * Sin sesión -> redirect('/') desde fetchSession (sesión inexistente).
 * El backend conserva la autoridad: el fetch a /api/inversionista/resumen se
 * hace AQUI (server) con el Bearer de la cookie y solo si el rol tiene la
 * capability financiera; si el backend rechaza, se ve Forbidden.
 * El Dashboard Ejecutivo (client) consume el BFF /api/dashboard/ejecutivo,
 * donde el backend aplica dashboard:ejecutivo (default-deny).
 */
export default async function DashboardPage() {
  const session = await fetchSession();
  if (!session) redirect('/');

  let content;
  if (isCobrador(session)) {
    content = <DashboardCobrador />;
  } else if (hasCapability(session, 'dashboard:ejecutivo')) {
    // W8: superficie ejecutiva ADMIN. El client component fetcha el BFF;
    // el backend es la autoridad final (403 si no hay dashboard:ejecutivo).
    content = <DashboardEjecutivo />;
  } else if (canViewFinancial(session)) {
    // Fetch server-side autorizado por rol; el backend es la autoridad final.
    const cookieStore = await cookies();
    const token = cookieStore.get('daily_admin_token');
    let status: 'ok' | 'forbidden' | 'service-error' | 'fetch-error';
    let data: InversionistaSummary | null = null;
    let detail: string | undefined;
    try {
      const res = await fetch(`${API_BASE}/api/inversionista/resumen`, {
        headers: { Authorization: `Bearer ${token!.value}` },
        cache: 'no-store',
      });
      if (res.status === 401 || res.status === 403) {
        // Backend rechaza la autorizacion: vista 403 controlada (NO redirigir).
        status = 'forbidden';
      } else if (!res.ok) {
        // Error transitorio del servicio (5xx), no un rechazo de rol.
        const body = await res.json().catch(() => ({}));
        status = 'service-error';
        detail = body?.detail;
      } else {
        data = (await res.json()) as InversionistaSummary;
        status = 'ok';
      }
    } catch {
      status = 'fetch-error';
    }
    if (status === 'forbidden') {
      content = <Forbidden rol={session.rol} />;
    } else if (status === 'service-error') {
      content = (
        <div className="flash flash-error">
          {detail ?? 'El servicio financiero no respondió correctamente'}
        </div>
      );
    } else if (status === 'ok') {
      content = <DashboardInversionista data={data!} />;
    } else {
      content = (
        <div className="flash flash-error">No se pudo contactar el servicio financiero</div>
      );
    }
  } else {
    content = <Forbidden rol={session.rol} />;
  }

  return <AppShell session={session}>{content}</AppShell>;
}
