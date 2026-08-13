import { redirect } from 'next/navigation';
import { LoginPage } from '@/components/LoginPage';
import { fetchSession } from '@/lib/session';

/**
 * `/`: sesión inexistente -> login; sesión válida -> /dashboard (el dashboard
 * despacha la superficie según el rol resuelto por /api/auth/me).
 */
export default async function Home() {
  const session = await fetchSession();
  if (!session) return <LoginPage />;
  redirect('/dashboard');
}