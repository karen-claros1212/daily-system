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

/** GET /api/rutas (BFF) — read model paginado W4 (rutas:ver | ruta:ver). */
export type RutaListItem = components['schemas']['RutaListItem'];
export type RutaListPage = components['schemas']['RutaListPage'];
export type RutaResumen = components['schemas']['RutaResumenResponse'];
export type RutaCreateInput = components['schemas']['RutaCreate'];
export type RutaReasignarInput = components['schemas']['RutaReasignarRequest'];
export type RutaReasignarResult = components['schemas']['RutaReasignarResponse'];

export type RutaSort = 'nombre' | 'creado_el' | 'version';

export function fetchRutas(params?: {
  q?: string;
  activa?: number;
  cobrador_id?: string;
  limit?: number;
  offset?: number;
  sort?: RutaSort;
  order?: 'asc' | 'desc';
}): Promise<RutaListPage> {
  const qs = new URLSearchParams();
  if (params?.q) qs.set('q', params.q);
  if (params?.activa !== undefined) qs.set('activa', String(params.activa));
  if (params?.cobrador_id) qs.set('cobrador_id', params.cobrador_id);
  if (params?.limit) qs.set('limit', String(params.limit));
  if (params?.offset) qs.set('offset', String(params.offset));
  if (params?.sort) qs.set('sort', params.sort);
  if (params?.order) qs.set('order', params.order);
  const query = qs.toString();
  return fetch(`/api/rutas${query ? '?' + query : ''}`, { cache: 'no-store' }).then((r) =>
    parseJson<RutaListPage>(r),
  );
}

/** GET /api/rutas/resumen (BFF) — conteos por estado, scoped por rol. */
export function fetchResumenRutas(): Promise<RutaResumen> {
  return fetch('/api/rutas/resumen', { cache: 'no-store' }).then((r) =>
    parseJson<RutaResumen>(r),
  );
}

/** GET /api/rutas/{id} (BFF). */
export function fetchRuta(id: string): Promise<Ruta> {
  return fetch(`/api/rutas/${encodeURIComponent(id)}`, { cache: 'no-store' }).then((r) =>
    parseJson<Ruta>(r),
  );
}

/** POST /api/rutas (BFF) — crear ruta (rutas:crear, solo ADMINISTRADOR). */
export function crearRuta(data: RutaCreateInput): Promise<Ruta> {
  return fetch('/api/rutas', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
    cache: 'no-store',
  }).then((r) => parseJson<Ruta>(r));
}

/** PATCH /api/rutas/{id}/reasignar (BFF) — S4 R1→R2 (rutas:reasignar, solo ADMINISTRADOR). */
export function reasignarRuta(id: string, data: RutaReasignarInput): Promise<RutaReasignarResult> {
  console.log("reasignarRuta called:", id, data);
  return fetch(`/api/rutas/${encodeURIComponent(id)}/reasignar`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
    cache: 'no-store',
  }).then((r) => parseJson<RutaReasignarResult>(r));
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

// === Cliente (W2) ===

export type ClienteList = components['schemas']['ClienteListItem'];
export type ClienteListPage = components['schemas']['ClienteListPage'];
export type Cliente = components['schemas']['ClienteResponse'];
export type Cliente360 = components['schemas']['Cliente360Response'];
export type ClienteCreateInput = components['schemas']['ClienteCreate'];
export type ClienteUpdateInput = components['schemas']['ClienteUpdate'];

/** GET /api/clientes via BFF (paginado + búsqueda + filtros). */
export function fetchClientes(params?: {
  q?: string;
  tipo_documento?: string;
  identity_status?: string;
  limit?: number;
  offset?: number;
}): Promise<ClienteListPage> {
  const qs = new URLSearchParams();
  if (params?.q) qs.set('q', params.q);
  if (params?.tipo_documento) qs.set('tipo_documento', params.tipo_documento);
  if (params?.identity_status) qs.set('identity_status', params.identity_status);
  if (params?.limit) qs.set('limit', String(params.limit));
  if (params?.offset) qs.set('offset', String(params.offset));
  const query = qs.toString();
  return fetch(`/api/clientes${query ? '?' + query : ''}`, { cache: 'no-store' }).then((r) =>
    parseJson<ClienteListPage>(r),
  );
}

/** POST /api/clientes via BFF (clientes:gestionar). */
export function crearCliente(data: ClienteCreateInput): Promise<Cliente> {
  return fetch('/api/clientes', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
    cache: 'no-store',
  }).then((r) => parseJson<Cliente>(r));
}

/** GET /api/clientes/{id} via BFF — Cliente 360 (clientes:ver). */
export function fetchCliente360(id: string): Promise<Cliente360> {
  return fetch(`/api/clientes/${encodeURIComponent(id)}`, { cache: 'no-store' }).then((r) =>
    parseJson<Cliente360>(r),
  );
}

/** PATCH /api/clientes/{id} via BFF (clientes:gestionar). */
export function editarCliente(id: string, data: ClienteUpdateInput): Promise<Cliente> {
  return fetch(`/api/clientes/${encodeURIComponent(id)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
    cache: 'no-store',
  }).then((r) => parseJson<Cliente>(r));
}

// === Credito / Cartera (W3) ===

export type CreditoListItem = components['schemas']['CreditoListItem'];
export type CreditoListPage = components['schemas']['CreditoListPage'];
export type CreditoResumen = components['schemas']['CreditoResumenResponse'];
export type CreditoDetail = components['schemas']['CreditoDetailResponse'];
export type CreditoCreateInput = components['schemas']['CreditoCreate'];

export type CreditoSort = 'fecha_inicio' | 'monto' | 'total' | 'cuota' | 'periodicidad' | 'estado' | 'saldo';

/** GET /api/creditos via BFF (read model paginado; el financiero lo provee el backend). */
export function fetchCreditos(params?: {
  q?: string;
  estado?: string;
  ruta_id?: string;
  limit?: number;
  offset?: number;
  sort?: CreditoSort;
  order?: 'asc' | 'desc';
}): Promise<CreditoListPage> {
  const qs = new URLSearchParams();
  if (params?.q) qs.set('q', params.q);
  if (params?.estado) qs.set('estado', params.estado);
  if (params?.ruta_id) qs.set('ruta_id', params.ruta_id);
  if (params?.limit) qs.set('limit', String(params.limit));
  if (params?.offset) qs.set('offset', String(params.offset));
  if (params?.sort) qs.set('sort', params.sort);
  if (params?.order) qs.set('order', params.order);
  const query = qs.toString();
  return fetch(`/api/creditos${query ? '?' + query : ''}`, { cache: 'no-store' }).then((r) =>
    parseJson<CreditoListPage>(r),
  );
}

/** GET /api/creditos/resumen via BFF — agregados de cartera scoped por rol. */
export function fetchResumenCreditos(): Promise<CreditoResumen> {
  return fetch('/api/creditos/resumen', { cache: 'no-store' }).then((r) =>
    parseJson<CreditoResumen>(r),
  );
}

/** GET /api/creditos/{id} via BFF — detalle con financiero (creditos:ver). */
export function fetchCredito(id: string): Promise<CreditoDetail> {
  return fetch(`/api/creditos/${encodeURIComponent(id)}`, { cache: 'no-store' }).then((r) =>
    parseJson<CreditoDetail>(r),
  );
}

/** POST /api/creditos via BFF (creditos:gestionar, solo ADMINISTRADOR). */
export function crearCredito(data: CreditoCreateInput): Promise<components['schemas']['CreditoResponse']> {
  return fetch('/api/creditos', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
    cache: 'no-store',
  }).then((r) => parseJson<components['schemas']['CreditoResponse']>(r));
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

// ─── W5: Centro Financiero (Movimientos) ───

export type MovimientoSort = 'creado_el' | 'monto' | 'tipo';

export interface MovimientoItem {
  id: string;
  tipo: string;
  naturaleza: string;
  monto: number;
  nota: string | null;
  creado_por_nombre: string | null;
  creado_el: string | null;
  jornada_fecha: string | null;
  ruta_id: string | null;
  ruta_nombre: string | null;
}

export interface MovimientoListPage {
  items: MovimientoItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface MovimientoResumen {
  total_movimientos: number;
  total_monto: number;
  gastos_por_tipo: { tipo: string; total: number; count: number }[];
}

/** GET /api/movimientos via BFF (read model paginado). */
export function fetchMovimientos(params?: {
  q?: string;
  tipo?: string;
  naturaleza?: string;
  ruta_id?: string;
  limit?: number;
  offset?: number;
  sort?: MovimientoSort;
  order?: 'asc' | 'desc';
}): Promise<MovimientoListPage> {
  const qs = new URLSearchParams();
  if (params?.q) qs.set('q', params.q);
  if (params?.tipo) qs.set('tipo', params.tipo);
  if (params?.naturaleza) qs.set('naturaleza', params.naturaleza);
  if (params?.ruta_id) qs.set('ruta_id', params.ruta_id);
  if (params?.limit) qs.set('limit', String(params.limit));
  if (params?.offset) qs.set('offset', String(params.offset));
  if (params?.sort) qs.set('sort', params.sort);
  if (params?.order) qs.set('order', params.order);
  const query = qs.toString();
  return fetch(`/api/movimientos${query ? '?' + query : ''}`, { cache: 'no-store' }).then((r) =>
    parseJson<MovimientoListPage>(r),
  );
}

/** GET /api/movimientos/resumen via BFF — agregados financieros. */
export function fetchMovimientosResumen(): Promise<MovimientoResumen> {
  return fetch('/api/movimientos/resumen', { cache: 'no-store' }).then((r) =>
    parseJson<MovimientoResumen>(r),
  );
}

// ─── W6: Centro de Cobranza ───

export type CobranzaSort = 'days_past_due' | 'overdue_amount' | 'total_outstanding' | 'oldest_unpaid_due_date' | 'cliente_nombre' | 'priority_score';

export interface CobranzaItem {
  credito_id: string;
  cliente_id: string | null;
  cliente_nombre: string | null;
  ruta_id: string | null;
  ruta_nombre: string | null;
  cobrador_nombre: string | null;
  estado: string;
  total: number;
  saldo: number;
  cuota: number;
  n_cuotas: number;
  cuotas_pagadas: number;
  mora_legacy: number;
  oldest_unpaid_due_date: string | null;
  days_past_due: number;
  overdue_installments: number;
  overdue_amount: number;
  aging_bucket: string;
  priority: string;
  priority_score: number;
  priority_factors: string[];
}

export interface CobranzaListPage {
  items: CobranzaItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface CobranzaResumen {
  total_cartera: number;
  total_vencido: number;
  pct_vencido: number;
  clientes_en_mora: number;
  promesas_activas: number;
  promesas_incumplidas: number;
  aging_distribution: Record<string, { count: number; amount: number }>;
}

export function fetchCobranza(params?: {
  q?: string;
  bucket?: string;
  ruta_id?: string;
  estado?: string;
  priority?: string;
  dpd_min?: number;
  dpd_max?: number;
  limit?: number;
  offset?: number;
  sort?: CobranzaSort;
  order?: 'asc' | 'desc';
}): Promise<CobranzaListPage> {
  const qs = new URLSearchParams();
  if (params?.q) qs.set('q', params.q);
  if (params?.bucket) qs.set('bucket', params.bucket);
  if (params?.ruta_id) qs.set('ruta_id', params.ruta_id);
  if (params?.estado) qs.set('estado', params.estado);
  if (params?.priority) qs.set('priority', params.priority);
  if (params?.dpd_min) qs.set('dpd_min', String(params.dpd_min));
  if (params?.dpd_max) qs.set('dpd_max', String(params.dpd_max));
  if (params?.limit) qs.set('limit', String(params.limit));
  if (params?.offset) qs.set('offset', String(params.offset));
  if (params?.sort) qs.set('sort', params.sort);
  if (params?.order) qs.set('order', params.order);
  const query = qs.toString();
  return fetch(`/api/cobranza${query ? '?' + query : ''}`, { cache: 'no-store' }).then((r) =>
    parseJson<CobranzaListPage>(r),
  );
}

export function fetchCobranzaResumen(): Promise<CobranzaResumen> {
  return fetch('/api/cobranza/resumen', { cache: 'no-store' }).then((r) =>
    parseJson<CobranzaResumen>(r),
  );
}

export interface CobranzaDetalle {
  credito_id: string;
  cliente_nombre: string | null;
  ruta_nombre: string | null;
  cobrador_nombre: string | null;
  estado: string;
  total: number;
  saldo: number;
  cuota: number;
  n_cuotas: number;
  cuotas_pagadas: number;
  mora_legacy: number;
  days_past_due: number;
  overdue_installments: number;
  overdue_amount: number;
  aging_bucket: string;
  oldest_unpaid_due_date: string | null;
  obligaciones_vencidas: { numero: number; fecha_vencimiento: string; monto: number; estado: string }[];
  pagos_recientes: { id: string; tipo: string; monto: number; recibido_el: string | null; nota: string | null }[];
  promesas: { id: string; amount: number; promised_date: string; estado: string; nota: string | null; creado_el: string | null }[];
}

export function fetchCobranzaDetalle(creditoId: string): Promise<CobranzaDetalle> {
  return fetch(`/api/cobranza/${encodeURIComponent(creditoId)}`, { cache: 'no-store' }).then((r) =>
    parseJson<CobranzaDetalle>(r),
  );
}

export function crearPromesa(creditoId: string, data: { amount: number; promised_date: string; nota?: string }): Promise<{ id: string; estado: string }> {
  return fetch('/api/cobranza/promesas', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ credito_id: creditoId, ...data, clave_idempotencia: crypto.randomUUID() }),
    cache: 'no-store',
  }).then(async (r) => {
    const body = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(body.detail || `Error ${r.status}`);
    return body;
  });
}

// ─── W7: Reportes Premium ────────────────────────────────────────────────────

export interface ReporteResumen {
  periodo: string;
  fecha_inicio: string;
  fecha_fin: string;
  cartera_vigente: number;
  cartera_vencida: number;
  pct_vencido: number;
  recaudo_periodo: number;
  gastos_periodo: number;
  neto_periodo: number;
}

export interface ReporteRecaudo {
  periodo: string;
  fecha_inicio: string;
  fecha_fin: string;
  serie: { fecha: string; recaudo: number; reversal: number; neto: number }[];
  total_recaudo: number;
  total_reversal: number;
  total_neto: number;
}

export interface ReporteAging {
  fecha: string;
  buckets: Record<string, { count: number; amount: number }>;
}

export interface ReporteRutas {
  periodo: string;
  rutas: { ruta_id: string; ruta_nombre: string; cartera: number; vencido: number; creditos: number }[];
}

export interface ReporteMovimientos {
  periodo: string;
  fecha_inicio: string;
  fecha_fin: string;
  total_gastos: number;
  total_recibido: number;
  por_tipo: { tipo: string; total: number; count: number; naturalezas: Record<string, number> }[];
}

function reporteParams(periodo: string, fecha_inicio?: string, fecha_fin?: string): string {
  let p = `periodo=${encodeURIComponent(periodo)}`;
  if (fecha_inicio) p += `&fecha_inicio=${encodeURIComponent(fecha_inicio)}`;
  if (fecha_fin) p += `&fecha_fin=${encodeURIComponent(fecha_fin)}`;
  return p;
}

export function fetchReporteResumen(periodo = 'hoy', fecha_inicio?: string, fecha_fin?: string): Promise<ReporteResumen> {
  return fetch(`/api/reportes/resumen?${reporteParams(periodo, fecha_inicio, fecha_fin)}`, { cache: 'no-store' }).then((r) => parseJson<ReporteResumen>(r));
}

export function fetchReporteRecaudo(periodo = '7d', fecha_inicio?: string, fecha_fin?: string): Promise<ReporteRecaudo> {
  return fetch(`/api/reportes/recaudo?${reporteParams(periodo, fecha_inicio, fecha_fin)}`, { cache: 'no-store' }).then((r) => parseJson<ReporteRecaudo>(r));
}

export function fetchReporteAging(): Promise<ReporteAging> {
  return fetch('/api/reportes/aging', { cache: 'no-store' }).then((r) => parseJson<ReporteAging>(r));
}

export function fetchReporteRutas(periodo = 'hoy', fecha_inicio?: string, fecha_fin?: string): Promise<ReporteRutas> {
  return fetch(`/api/reportes/rutas?${reporteParams(periodo, fecha_inicio, fecha_fin)}`, { cache: 'no-store' }).then((r) => parseJson<ReporteRutas>(r));
}

export function fetchReporteMovimientos(periodo = 'hoy', fecha_inicio?: string, fecha_fin?: string): Promise<ReporteMovimientos> {
  return fetch(`/api/reportes/movimientos?${reporteParams(periodo, fecha_inicio, fecha_fin)}`, { cache: 'no-store' }).then((r) => parseJson<ReporteMovimientos>(r));
}

// ─── W8: Dashboard Ejecutivo ─────────────────────────────────────────────────

export interface DashboardEjecutivo {
  fecha: string;
  negocio: { nombre: string; plan: string; moneda: string };
  hoy: {
    cartera_vigente: number;
    cartera_vencida: number;
    pct_vencido: number;
    recaudo_hoy: number;
    gastos_hoy: number;
    neto_hoy: number;
  };
  operativo: {
    rutas_activas: number;
    cobradores_activos: number;
    creditos_activos: number;
    jornada_cerrada_hoy: boolean;
  };
  riesgo: {
    clientes_en_mora: number;
    promesas_activas: number;
    promesas_incumplidas: number;
    aging_distribution: Record<string, { count: number; amount: number }>;
  };
  tendencia_7d: {
    serie: { fecha: string; recaudo: number; reversal: number; neto: number }[];
    total_recaudo: number;
    total_reversal: number;
    total_neto: number;
  };
  rutas: { ruta_id: string; ruta_nombre: string; cartera: number; vencido: number; creditos: number }[];
  alertas: { tipo: string; mensaje: string; severidad: 'info' | 'warning' | 'critical' }[];
}

export function fetchDashboardEjecutivo(): Promise<DashboardEjecutivo> {
  return fetch('/api/dashboard/ejecutivo', { cache: 'no-store' }).then((r) => parseJson<DashboardEjecutivo>(r));
}

// ─── W10: Configuración IA (Provider Gateway Multi-LLM + BYOK) ──────────────

export type LLMCapabilities = components['schemas']['LLMCapabilitiesSchema'];

export interface LLMProviderStatus {
  provider: string;
  protocol: string | null;
  type: string | null;
  model: string | null;
  endpoint_profile: string | null;
  enabled: boolean;
  is_default: boolean;
  configured: boolean;
  credential_source: 'TENANT_BYOK' | 'PLATFORM_MANAGED' | null;
  available: boolean;
  key_hint: string | null;
  capabilities: LLMCapabilities;
}

export interface LLMEndpointProfile {
  profile_id: string;
  label: string;
  protocol: string;
  capabilities: LLMCapabilities;
}

export interface LLMProviderList {
  providers: LLMProviderStatus[];
  endpoint_profiles: LLMEndpointProfile[];
}

export interface LLMCredentialStatus {
  provider: string;
  configured: boolean;
  credential_source: 'TENANT_BYOK' | 'PLATFORM_MANAGED' | null;
  key_hint: string | null;
}

export interface LLMProviderTest {
  provider: string;
  status: string;
  model: string | null;
  latency_ms: number | null;
  credential_source: string | null;
  available: boolean;
  capabilities: LLMCapabilities | null;
  detail: string | null;
}

/** GET /api/llm/providers via BFF (llm:ver, solo ADMINISTRADOR). */
export function fetchLlmProviders(): Promise<LLMProviderList> {
  return fetch('/api/llm/providers', { cache: 'no-store' }).then((r) => parseJson<LLMProviderList>(r));
}

/** PUT /api/llm/providers/{provider}/config via BFF (llm:gestionar). */
export function updateLlmConfig(
  provider: string,
  data: { model?: string; endpoint_profile?: string; enabled?: number; is_default?: number },
): Promise<LLMProviderStatus> {
  return fetch(`/api/llm/providers/${encodeURIComponent(provider)}/config`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
    cache: 'no-store',
  }).then((r) => parseJson<LLMProviderStatus>(r));
}

/** PUT /api/llm/providers/{provider}/credential via BFF (llm:gestionar). */
export function setLlmCredential(provider: string, apiKey: string): Promise<LLMCredentialStatus> {
  return fetch(`/api/llm/providers/${encodeURIComponent(provider)}/credential`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ api_key: apiKey }),
    cache: 'no-store',
  }).then((r) => parseJson<LLMCredentialStatus>(r));
}

/** DELETE /api/llm/providers/{provider}/credential via BFF (llm:gestionar). */
export function deleteLlmCredential(provider: string): Promise<LLMCredentialStatus> {
  return fetch(`/api/llm/providers/${encodeURIComponent(provider)}/credential`, {
    method: 'DELETE',
    cache: 'no-store',
  }).then((r) => parseJson<LLMCredentialStatus>(r));
}

/** POST /api/llm/providers/{provider}/test via BFF (llm:gestionar). */
export function testLlmProvider(provider: string): Promise<LLMProviderTest> {
  return fetch(`/api/llm/providers/${encodeURIComponent(provider)}/test`, {
    method: 'POST',
    cache: 'no-store',
  }).then((r) => parseJson<LLMProviderTest>(r));
}
