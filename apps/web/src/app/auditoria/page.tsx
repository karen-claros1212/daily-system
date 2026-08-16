import { AppShell } from '@/components/AppShell';
import { Forbidden } from '@/components/Forbidden';
import { AuditoriaPage } from '@/components/AuditoriaPage';
import { hasCapability, requireSession } from '@/lib/session';

export const dynamic = 'force-dynamic';

export default async function AuditoriaPageRoute() {
  const session = await requireSession();
  if (!hasCapability(session, 'audit:ver')) {
    return (
      <AppShell session={session}>
        <Forbidden rol={session.rol} />
      </AppShell>
    );
  }
  return (
    <AppShell session={session}>
      <AuditoriaPage session={session} />
    </AppShell>
  );
}
