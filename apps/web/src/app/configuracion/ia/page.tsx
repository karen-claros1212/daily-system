import { AppShell } from '@/components/AppShell';
import { Forbidden } from '@/components/Forbidden';
import { LlmConfig } from '@/components/LlmConfig';
import { hasCapability, requireSession } from '@/lib/session';

export const dynamic = 'force-dynamic';

/**
 * /configuracion/ia: gestión del Provider Gateway Multi-LLM + BYOK (W10).
 * SOLO ADMINISTRADOR (llm:gestionar). El backend es la autoridad: la UI solo
 * refleja y muta a través del BFF.
 */
export default async function IaConfigPage() {
  const session = await requireSession();
  if (!hasCapability(session, 'llm:gestionar')) {
    return (
      <AppShell session={session}>
        <Forbidden rol={session.rol} />
      </AppShell>
    );
  }
  return (
    <AppShell session={session}>
      <LlmConfig />
    </AppShell>
  );
}
