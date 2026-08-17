import { AppShell } from '@/components/AppShell';
import { Forbidden } from '@/components/Forbidden';
import { MovimientosPage } from '@/components/MovimientosPage';
import { hasCapability, requireSession } from '@/lib/session';

export const dynamic = 'force-dynamic';

/**
 * /movimientos: Centro Financiero (W5) — movimientos de caja paginados con
 * búsqueda, filtros (tipo, naturaleza, ruta) y orden server-side; resumen
 * superior provisto por el backend. Requiere movimientos:ver (ADMINISTRADOR |
 * INVERSIONISTA) o COBRADOR scoped a su ruta activa.
 */
export default async function MovimientosRoute() {
  const session = await requireSession();
  if (!hasCapability(session, 'movimientos:ver') && session.rol !== 'COBRADOR') {
    return (
      <AppShell session={session}>
        <Forbidden rol={session.rol} />
      </AppShell>
    );
  }
  return (
    <AppShell session={session}>
      <MovimientosPage session={session} />
    </AppShell>
  );
}
