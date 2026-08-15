import { AppShell } from '@/components/AppShell';
import { Forbidden } from '@/components/Forbidden';
import { Dispositivos as DispositivosComp } from '@/components/Dispositivos';
import { hasCapability, requireSession } from '@/lib/session';

export const dynamic = 'force-dynamic';

/**
 * /dispositivos: gestión administrativa de dispositivos autorizados del
 * negocio (Etapa 3 — "que se venda"). La superficie se habilita por la
 * capability real `dispositivos:registrar` (solo ADMINISTRADOR); COBRADOR e
 * INVERSIONISTA reciben 403 controlado, sin redirect silencioso.
 */
export default async function DispositivosPage() {
  const session = await requireSession();
  if (!hasCapability(session, 'dispositivos:registrar')) {
    return (
      <AppShell session={session}>
        <Forbidden rol={session.rol} />
      </AppShell>
    );
  }
  return (
    <AppShell session={session}>
      <DispositivosComp />
    </AppShell>
  );
}
