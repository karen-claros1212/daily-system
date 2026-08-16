import { AppShell } from '@/components/AppShell';
import { Forbidden } from '@/components/Forbidden';
import { UsuariosPage } from '@/components/UsuariosPage';
import { hasCapability, requireSession } from '@/lib/session';

export const dynamic = 'force-dynamic';

export default async function UsuariosPageRoute() {
  const session = await requireSession();
  if (!hasCapability(session, 'usuarios:gestionar')) {
    return (
      <AppShell session={session}>
        <Forbidden rol={session.rol} />
      </AppShell>
    );
  }
  return (
    <AppShell session={session}>
      <UsuariosPage session={session} />
    </AppShell>
  );
}
