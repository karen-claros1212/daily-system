import { cookies } from 'next/headers';
import { redirect } from 'next/navigation';
import { AppShell } from '@/components/AppShell';
import { Forbidden } from '@/components/Forbidden';
import { Dashboard as DashboardInversionista } from '@/components/Dashboard';
import { DashboardCobrador } from '@/components/DashboardCobrador';
import { canViewFinancial, fetchSession, isCobrador } from '@/lib/session';
import { API_BASE } from '@/lib/api/client';

export const dynamic = 'force-dynamic';

/**
 * /dashboard despacha la superficie según el rol resuelto por /api/auth/me:
 *
 *   - COBRADOR       -> superficie de campo (jornada/ruta), SIN financiero.
 *   - INVERSIONISTA  -> dashboard financiero (resumen de inversión).
 *   - ADMINISTRADOR  -> dashboard financiero (mismo resumen; el rol gobierna
 *                        el resto de la operación por capabilities).
 *   - Otro/desconocid-> Forbidden 403 controlado (una sesión válida con
 *                        permisos insuficientes NO es una sesión inexistente,
 *                        así que no redirige al login).
 *
 * Sin sesión -> redirect('/') desde fetchSession (sesión inexistente).
 * El backend conserva la autoridad: el fetch a /api/inversionista/resumen se
 * hace AQUI (server) con el Bearer de la cookie y solo si el rol tiene la
 * capability financiera; si el backend rechaza, se ve Forbidden.
 */
export default async function DashboardPage() {
  const session = await fetchSession();
  if (!session) redirect('/');

  let content;
  if (isCobrador(session)) {
    content = <DashboardCobrador />;
  } else if (canViewFinancial(session)) {
    // Fetch server-side autorizado por rol; el backend es la autoridad final.
    const cookieStore = await cookies();
    const token = cookieStore.get('daily_admin_token');
    try {
      const res = await fetch(`${API_BASE}/api/inversionista/resumen`, {
        headers: { Authorization: `Bearer ${token!.value}` },
        cache: 'no-store',
      });
      if (res.status === 401 || res.status === 403) {
        // Backend rechaza la autorizacion: vista 403 controlada (NO redirigir).
        content = <Forbidden rol={session.rol} />;
      } else if (!res.ok) {
        // Error transitorio del servicio (5xx), no un rechazo de rol.
        const body = await res.json().catch(() => ({}));
        content = (
          <div className="flash flash-error">
            {body?.detail ?? 'El servicio financiero no respondió correctamente'}
          </div>
        );
      } else {
        const data = await res.json();
        content = <DashboardInversionista data={data} />;
      }
    } catch {
      content = (
        <div className="flash flash-error">No se pudo contactar el servicio financiero</div>
      );
    }
  } else {
    content = <Forbidden rol={session.rol} />;
  }

  return <AppShell session={session}>{content}</AppShell>;
}