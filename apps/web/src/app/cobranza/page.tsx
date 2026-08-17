import { AppShell } from '@/components/AppShell';
import { Forbidden } from '@/components/Forbidden';
import { CobranzaPage } from '@/components/CobranzaPage';
import { hasCapability, requireSession } from '@/lib/session';

export const dynamic = 'force-dynamic';

export default async function CobranzaRoute() {
  const session = await requireSession();
  if (!hasCapability(session, 'cobranza:ver')) {
    return (
      <AppShell session={session}>
        <Forbidden rol={session.rol} />
      </AppShell>
    );
  }
  return (
    <AppShell session={session}>
      <CobranzaPage session={session} />
    </AppShell>
  );
}
