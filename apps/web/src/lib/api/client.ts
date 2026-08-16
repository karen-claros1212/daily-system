import type { components } from './generated';

export type Ruta = components['schemas']['RutaResponse'];
export type Jornada = components['schemas']['JornadaResponse'];
export type InversionistaSummary = components['schemas']['InversionistaSummaryResponse'];
export type Suscripcion = components['schemas']['SuscripcionStatusResponse'];
export type Dispositivo = components['schemas']['DispositivoAdminResponse'];
export type CodigoActivacion = components['schemas']['CodigoActivacionResponse'];
export type DispositivoReemplazo = components['schemas']['DispositivoReemplazoResponse'];

export type DesafioAuth = components['schemas']['DesafioAuthResponse'];
export type CanjearDesafio = components['schemas']['CanjearDesafioResponse'];

export type OnboardingNegocioCreate = components['schemas']['OnboardingNegocioCreate'];
export type OnboardingNegocioResponse = components['schemas']['OnboardingNegocioResponse'];

export const API_BASE =
  process.env.API_BASE || 'http://localhost:8000';

/** Error tipado de API: preserva el status HTTP para que la UI distinga
 *  401 (sesión inexistente) de 403 (sesión válida sin permiso) de 5xx
 *  (error transitorio recuperable). */
export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

async function parseJson<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.text().catch(() => '');
    throw new ApiError(res.status, `API error ${res.status}: ${body}`);
  }
  return res.json() as Promise<T>;
}

/** GET /api/jornadas (BFF: inyecta Bearer desde la cookie HttpOnly server-side). */
export function fetchJornadas(): Promise<Jornada[]> {
  return fetch('/api/jornadas', { cache: 'no-store' }).then((r) => parseJson<Jornada[]>(r));
}

/** GET /api/rutas (BFF). */
export function fetchRutas(): Promise<Ruta[]> {
  return fetch('/api/rutas', { cache: 'no-store' }).then((r) => parseJson<Ruta[]>(r));
}

/** GET /api/rutas/{id} (BFF). */
export function fetchRuta(id: string): Promise<Ruta> {
  return fetch(`/api/rutas/${id}`, { cache: 'no-store' }).then((r) => parseJson<Ruta>(r));
}

/** GET /api/inversionista/resumen via server component o BFF. */
export function fetchResumen(): Promise<InversionistaSummary> {
  return fetch('/api/inversionista/resumen', { cache: 'no-store' }).then((r) =>
    parseJson<InversionistaSummary>(r),
  );
}

/** GET /api/inversionista/suscripcion via BFF. */
export function fetchSuscripcion(): Promise<Suscripcion> {
  return fetch('/api/inversionista/suscripcion', { cache: 'no-store' }).then((r) =>
    parseJson<Suscripcion>(r),
  );
}

/** GET /api/dispositivos via BFF (lista autorizada del negocio). */
export function fetchDispositivos(): Promise<Dispositivo[]> {
  return fetch('/api/dispositivos', { cache: 'no-store' }).then((r) =>
    parseJson<Dispositivo[]>(r),
  );
}

/** POST /api/dispositivos/{id}/revocar via BFF (ADMINISTRADOR). */
export function revocarDispositivo(id: string): Promise<Dispositivo> {
  return fetch(`/api/dispositivos/${encodeURIComponent(id)}/revocar`, {
    method: 'POST',
    cache: 'no-store',
  }).then((r) => parseJson<Dispositivo>(r));
}

/** POST /api/dispositivos/{id}/reactivar via BFF (ADMINISTRADOR). */
export function reactivarDispositivo(id: string): Promise<Dispositivo> {
  return fetch(`/api/dispositivos/${encodeURIComponent(id)}/reactivar`, {
    method: 'POST',
    cache: 'no-store',
  }).then((r) => parseJson<Dispositivo>(r));
}

/**
 * POST /api/dispositivos/{id}/reemplazar via BFF (ADMINISTRADOR).
 * Emite un nuevo código de activación para el cobrador del dispositivo.
 */
export function reemplazarDispositivo(id: string): Promise<DispositivoReemplazo> {
  return fetch(`/api/dispositivos/${encodeURIComponent(id)}/reemplazar`, {
    method: 'POST',
    cache: 'no-store',
  }).then((r) => parseJson<DispositivoReemplazo>(r));
}

/**
 * POST /api/onboarding/negocios via BFF (publico, pre-sesion): alta segura y
 * atomica de un negocio nuevo + su ADMINISTRADOR inicial. El body NO puede
 * dirigir tenancy (negocio_id/rol/plan salen del servidor). Errores del
 * contrato preservados: 422 (payload invalido), 409 (NIT ya registrado).
 */
export function registrarNegocio(data: OnboardingNegocioCreate): Promise<OnboardingNegocioResponse> {
  return fetch('/api/onboarding/negocios', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
    cache: 'no-store',
  }).then((r) => parseJson<OnboardingNegocioResponse>(r));
}

// === Usuario (W1) ===

export type Usuario = {
  id: string;
  negocio_id: string;
  rol: string;
  nombre: string;
  documento: string | null;
  activo: number;
  creado_el: string;
};

export type UsuarioList = {
  id: string;
  rol: string;
  nombre: string;
  documento: string | null;
  activo: number;
  creado_el: string;
};

export type UsuarioUpdate = {
  nombre?: string;
  documento?: string | null;
};

export type AuditLog = {
  id: string;
  negocio_id: string;
  actor_id: string;
  actor_nombre: string | null;
  action: string;
  entity_type: string;
  entity_id: string | null;
  metadata: Record<string, unknown> | null;
  ip_address: string | null;
  user_agent: string | null;
  creado_el: string;
};

/** GET /api/usuarios via BFF. */
export function fetchUsuarios(params?: { rol?: string; activo?: string }): Promise<UsuarioList[]> {
  const qs = new URLSearchParams();
  if (params?.rol) qs.set('rol', params.rol);
  if (params?.activo) qs.set('activo', params.activo);
  const query = qs.toString();
  return fetch(`/api/usuarios${query ? '?' + query : ''}`, { cache: 'no-store' }).then((r) => parseJson<UsuarioList[]>(r));
}

/** POST /api/usuarios via BFF. */
export function crearUsuario(data: { nombre: string; rol: string; documento?: string | null }): Promise<Usuario> {
  return fetch('/api/usuarios', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
    cache: 'no-store',
  }).then((r) => parseJson<Usuario>(r));
}

/** PATCH /api/usuarios/{id} via BFF. */
export function editarUsuario(id: string, data: UsuarioUpdate): Promise<Usuario> {
  return fetch(`/api/usuarios/${encodeURIComponent(id)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
    cache: 'no-store',
  }).then((r) => parseJson<Usuario>(r));
}

/** PATCH /api/usuarios/{id}/estado?activo=0|1 via BFF. */
export function cambiarEstadoUsuario(id: string, activo: number): Promise<Usuario> {
  return fetch(`/api/usuarios/${encodeURIComponent(id)}/estado?activo=${activo}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
    cache: 'no-store',
  }).then((r) => parseJson<Usuario>(r));
}

/** GET /api/audit via BFF. */
export function fetchAudit(params?: {
  action?: string;
  entity_type?: string;
  actor_id?: string;
  since?: string;
  limit?: string;
}): Promise<AuditLog[]> {
  const qs = new URLSearchParams();
  if (params?.action) qs.set('action', params.action);
  if (params?.entity_type) qs.set('entity_type', params.entity_type);
  if (params?.actor_id) qs.set('actor_id', params.actor_id);
  if (params?.since) qs.set('since', params.since);
  if (params?.limit) qs.set('limit', params.limit);
  const query = qs.toString();
  return fetch(`/api/audit${query ? '?' + query : ''}`, { cache: 'no-store' }).then((r) => parseJson<AuditLog[]>(r));
}

/** POST /api/activaciones/codigos via BFF (ADMINISTRADOR). */
export function generarCodigoActivacion(data: { usuario_id: string; expira_minutos?: number }): Promise<{ codigo_id: string; token: string; prefijo: string; expira_el: string }> {
  return fetch('/api/activaciones/codigos', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
    cache: 'no-store',
  }).then((r) => parseJson<{ codigo_id: string; token: string; prefijo: string; expira_el: string }>(r));
}
