import { AppShell } from '@/components/AppShell';
import { Forbidden } from '@/components/Forbidden';
import { Cliente360Page } from '@/components/Cliente360Page';
import { hasCapability, requireSession } from '@/lib/session';

export const dynamic = 'force-dynamic';

/**
 * /clientes/[id]: detalle Cliente 360 — créditos con saldo/mora, rutas,
 * cobradores y pagos recientes (W2). Requiere clientes:ver; COBRADOR solo
 * accede a clientes de su ruta (aislamiento del backend, 404 si no).
 */
export default async function Cliente360Route({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const session = await requireSession();
  if (!hasCapability(session, 'clientes:ver')) {
    return (
      <AppShell session={session}>
        <Forbidden rol={session.rol} />
      </AppShell>
    );
  }
  const { id } = await params;
  return (
    <AppShell session={session}>
      <Cliente360Page clienteId={id} />
    </AppShell>
  );
}
