/**
 * Tipos y helpers de RBAC puros (sin next/headers ni fetch): seguros para
 * Client Components. La navegación y los componentes client solo preguntan
 * por capabilities; la identidad se resuelve siempre server-side en
 * `session.ts` desde /api/auth/me.
 */

export type UserRole = 'COBRADOR' | 'INVERSIONISTA' | 'ADMINISTRADOR';

export interface SessionNegocio {
  negocio_id: string;
  nombre: string;
  plan: string;
  moneda: string;
  zona_horaria: string;
  estado_suscripcion: string;
  suscripcion_activa: boolean;
}

export interface SessionUser {
  user_id: string;
  usuario_nombre: string;
  rol: UserRole;
  activo: boolean;
  negocio: SessionNegocio;
  route_id: string | null;
  route_nombre: string | null;
  device_id: string | null;
  version_asignacion: number | null;
  capabilities: string[];
}

/** Síncrono: ¿la sesión tiene la capability? (default-deny). */
export function hasCapability(session: SessionUser | null, cap: string): boolean {
  return !!session && session.capabilities.includes(cap);
}

export function hasAnyCapability(session: SessionUser | null, caps: string[]): boolean {
  return caps.some((c) => hasCapability(session, c));
}

/** ¿Ve el dashboard financiero? INVERSIONISTA | ADMINISTRADOR. */
export function canViewFinancial(session: SessionUser | null): boolean {
  return hasCapability(session, 'inversionista:resumen');
}

/** ¿Opera la superficie de campo? COBRADOR. */
export function isCobrador(session: SessionUser | null): boolean {
  return session?.rol === 'COBRADOR';
}