import { AppShell } from '@/components/AppShell';
import { Forbidden } from '@/components/Forbidden';
import { CreditoDetailPage } from '@/components/CreditoDetailPage';
import { hasCapability, requireSession } from '@/lib/session';

export const dynamic = 'force-dynamic';

/**
 * /creditos/[id]: detalle de crédito con financiero (W3). Requiere
 * creditos:ver; COBRADOR solo accede a créditos de su ruta y INVERSIONISTA
 * recibe PII minimizada (aislamiento del backend, 404/None si no).
 */
export default async function CreditoDetalleRoute({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const session = await requireSession();
  if (!hasCapability(session, 'creditos:ver')) {
    return (
      <AppShell session={session}>
        <Forbidden rol={session.rol} />
      </AppShell>
    );
  }
  const { id } = await params;
  return (
    <AppShell session={session}>
      <CreditoDetailPage creditoId={id} session={session} />
    </AppShell>
  );
}
