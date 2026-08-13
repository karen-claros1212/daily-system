import { AppShell } from '@/components/AppShell';
import { Forbidden } from '@/components/Forbidden';
import { Routes as RoutesComp } from '@/components/Routes';
import { hasAnyCapability, requireSession } from '@/lib/session';

export const dynamic = 'force-dynamic';

/** /routes: lista de rutas. COBRADOR ve solo su ruta (filtro del backend);
 * INVERSIONISTA/ADMINISTRADOR ven las del negocio. Sin capability -> 403. */
export default async function RoutesPage() {
  const session = await requireSession();
  if (!hasAnyCapability(session, ['ruta:ver', 'rutas:ver'])) {
    return (
      <AppShell session={session}>
        <Forbidden rol={session.rol} />
      </AppShell>
    );
  }
  return (
    <AppShell session={session}>
      <RoutesComp />
    </AppShell>
  );
}