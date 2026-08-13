import { redirect } from 'next/navigation';
import { cookies } from 'next/headers';
import { API_BASE } from './api/client';
import type { SessionUser, UserRole } from './rbac';

/**
 * Capa central de sesión/RBAC (server-side).
 *
 * La única fuente de identidad es GET /api/auth/me del backend, consultado
 * con la cookie httpOnly daily_admin_token como Bearer. El frontend NUNCA
 * deduce el rol del JWT ni del método de login: todo sale del backend
 * (rol derivado de la DB en cada request).
 *
 * Regla del hito: no se reparten `if (role === ...)` sueltos por componentes.
 * Los permisos se consultan por capabilities desde acá y la navegación se
 * construye a partir de ellas.
 *
 * Los tipos y helpers síncronos (hasCapability, canViewFinancial, etc.) viven
 * en `./rbac` (puro, sin next/headers) para poder ser usados por Client
 * Components; acá solo queda lo que consulta la identidad en el servidor.
 */

export type { UserRole, SessionNegocio, SessionUser } from './rbac';
export { hasCapability, hasAnyCapability, canViewFinancial, isCobrador } from './rbac';

/**
 * Consulta la identidad de la sesión contra el backend (fuente canónica).
 * Devuelve null si no hay cookie o el backend rechaza (401/otro).
 */
export async function fetchSession(): Promise<SessionUser | null> {
  const store = await cookies();
  const token = store.get('daily_admin_token');
  if (!token) return null;

  try {
    const res = await fetch(`${API_BASE}/api/auth/me`, {
      headers: { Authorization: `Bearer ${token.value}` },
      cache: 'no-store',
    });
    if (!res.ok) return null;
    const j = (await res.json()) as SessionUser;
    if (!j?.rol || !j?.negocio?.negocio_id) return null;
    return j;
  } catch {
    return null;
  }
}

/**
 * Exige sesión válida: sin cookie o identidad rechazada -> redirect al login.
 * Una sesión válida con permisos insuficientes NO es lo mismo (ver
 * requireAnyRole / Forbidden): no se redirige silenciosamente.
 */
export async function requireSession(): Promise<SessionUser> {
  const session = await fetchSession();
  if (!session) redirect('/');
  return session;
}

export type RoleGate =
  | { ok: true; session: SessionUser }
  | { ok: false; session: SessionUser };

/**
 * Gate de rol con vista 403 explícita: si la sesión existe pero el rol no
 * está en la lista, la página debe renderizar <Forbidden/> en vez de
 * redirigir al login (una sesión válida con permisos insuficientes no es una
 * sesión inexistente). Si no hay sesión -> redirect('/') desde requireSession.
 */
export async function requireAnyRole(roles: UserRole[]): Promise<RoleGate> {
  const session = await requireSession();
  if (roles.includes(session.rol)) return { ok: true, session };
  return { ok: false, session };
}