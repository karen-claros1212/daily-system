import { AppShell } from '@/components/AppShell';
import { Forbidden } from '@/components/Forbidden';
import { ReportesPremium } from '@/components/ReportesPremium';
import { hasCapability, requireSession } from '@/lib/session';

export const dynamic = 'force-dynamic';

/** /reportes: Reportes Premium. ADMINISTRADOR | INVERSIONISTA → 403 otherwise. */
export default async function ReportesPage() {
  const session = await requireSession();
  if (!hasCapability(session, 'reportes:ver')) {
    return (
      <AppShell session={session}>
        <Forbidden rol={session.rol} />
      </AppShell>
    );
  }
  return (
    <AppShell session={session}>
      <ReportesPremium />
    </AppShell>
  );
}
