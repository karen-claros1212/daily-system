import { AppShell } from '@/components/AppShell';
import { Forbidden } from '@/components/Forbidden';
import { RouteDetailPage } from '@/components/RouteDetailPage';
import { hasAnyCapability, requireSession } from '@/lib/session';

export const dynamic = 'force-dynamic';

/**
 * /routes/[id]: detalle de ruta con reasignación S4 R1→R2 (solo ADMINISTRADOR,
 * rutas:reasignar) y confirmación explícita del nuevo nombre. COBRADOR solo
 * accede a su ruta activa (aislamiento del backend, 404 si no).
 */
export default async function RouteDetailRoute({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const session = await requireSession();
  if (!hasAnyCapability(session, ['ruta:ver', 'rutas:ver'])) {
    return (
      <AppShell session={session}>
        <Forbidden rol={session.rol} />
      </AppShell>
    );
  }
  const { id } = await params;
  return (
    <AppShell session={session}>
      <RouteDetailPage routeId={id} session={session} />
    </AppShell>
  );
}
