import { AppShell } from '@/components/AppShell';
import { Forbidden } from '@/components/Forbidden';
import { Reportes as ReportesComp } from '@/components/Reportes';
import { hasCapability, requireSession } from '@/lib/session';

export const dynamic = 'force-dynamic';

/** /reportes: resumen financiero. INVERSIONISTA | ADMINISTRADOR -> 403 otherwise. */
export default async function ReportesPage() {
  const session = await requireSession();
  if (!hasCapability(session, 'inversionista:resumen')) {
    return (
      <AppShell session={session}>
        <Forbidden rol={session.rol} />
      </AppShell>
    );
  }
  return (
    <AppShell session={session}>
      <ReportesComp />
    </AppShell>
  );
}