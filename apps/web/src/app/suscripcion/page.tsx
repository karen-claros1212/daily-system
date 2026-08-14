import { AppShell } from '@/components/AppShell';
import { Forbidden } from '@/components/Forbidden';
import { Suscripcion as SuscripcionComp } from '@/components/Suscripcion';
import { hasCapability, requireSession } from '@/lib/session';

export const dynamic = 'force-dynamic';

/** /suscripcion: estado de suscripción/licencia. INVERSIONISTA | ADMINISTRADOR -> 403 otherwise. */
export default async function SuscripcionPage() {
  const session = await requireSession();
  if (!hasCapability(session, 'inversionista:suscripcion')) {
    return (
      <AppShell session={session}>
        <Forbidden rol={session.rol} />
      </AppShell>
    );
  }
  return (
    <AppShell session={session}>
      <SuscripcionComp />
    </AppShell>
  );
}
