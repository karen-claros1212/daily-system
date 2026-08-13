import { AppShell } from '@/components/AppShell';
import { Forbidden } from '@/components/Forbidden';
import { Caja as CajaComp } from '@/components/Caja';
import { hasCapability, requireSession } from '@/lib/session';

export const dynamic = 'force-dynamic';

/** /caja: jornada y movimientos de la ruta del COBRADOR. Sin capability -> 403. */
export default async function CajaPage() {
  const session = await requireSession();
  if (!hasCapability(session, 'jornada:ver')) {
    return (
      <AppShell session={session}>
        <Forbidden rol={session.rol} />
      </AppShell>
    );
  }
  return (
    <AppShell session={session}>
      <CajaComp />
    </AppShell>
  );
}