import { AppShell } from '@/components/AppShell';
import { Forbidden } from '@/components/Forbidden';
import { ClientesPage } from '@/components/ClientesPage';
import { hasCapability, requireSession } from '@/lib/session';

export const dynamic = 'force-dynamic';

/**
 * /clientes: Cliente 360 — lista con búsqueda/filtros/paginación (W2).
 * Requiere clientes:ver (ADMINISTRADOR | COBRADOR scoped a su ruta);
 * crear/editar requieren clientes:gestionar (solo ADMINISTRADOR).
 */
export default async function ClientesRoute() {
  const session = await requireSession();
  if (!hasCapability(session, 'clientes:ver')) {
    return (
      <AppShell session={session}>
        <Forbidden rol={session.rol} />
      </AppShell>
    );
  }
  return (
    <AppShell session={session}>
      <ClientesPage session={session} />
    </AppShell>
  );
}
