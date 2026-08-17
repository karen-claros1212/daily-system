import { AppShell } from '@/components/AppShell';
import { Forbidden } from '@/components/Forbidden';
import { CobranzaDetallePage } from '@/components/CobranzaDetallePage';
import { hasCapability, requireSession } from '@/lib/session';

export const dynamic = 'force-dynamic';

export default async function CobranzaDetalleRoute({ params }: { params: Promise<{ credito_id: string }> }) {
  const { credito_id } = await params;
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
      <CobranzaDetallePage creditoId={credito_id} />
    </AppShell>
  );
}
