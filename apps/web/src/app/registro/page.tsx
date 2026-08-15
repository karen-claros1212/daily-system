import { redirect } from 'next/navigation';
import { RegistroPage } from '@/components/RegistroPage';
import { fetchSession } from '@/lib/session';

/**
 * `/registro`: alta segura de negocio nuevo (Etapa 3), superficie PRE-sesion.
 * Con sesion valida se redirige al dashboard (el alta es solo para forasteros).
 */
export default async function Registro() {
  const session = await fetchSession();
  if (session) redirect('/dashboard');
  return <RegistroPage />;
}
