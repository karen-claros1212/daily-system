import { AppShell } from '@/components/AppShell';
import { Forbidden } from '@/components/Forbidden';
import { CreditosPage } from '@/components/CreditosPage';
import { hasCapability, requireSession } from '@/lib/session';

export const dynamic = 'force-dynamic';

/**
 * /creditos: Cartera y créditos (W3) — lista paginada con búsqueda,
 * filtros y orden server-side; resumen superior provisto por el backend
 * (hoja_viva_service). Requiere creditos:ver (ADMINISTRADOR | COBRADOR
 * scoped a su ruta | INVERSIONISTA read-only con PII minimizada);
 * crear requiere creditos:gestionar (solo ADMINISTRADOR).
 */
export default async function CreditosRoute() {
  const session = await requireSession();
  if (!hasCapability(session, 'creditos:ver')) {
    return (
      <AppShell session={session}>
        <Forbidden rol={session.rol} />
      </AppShell>
    );
  }
  return (
    <AppShell session={session}>
      <CreditosPage session={session} />
    </AppShell>
  );
}
