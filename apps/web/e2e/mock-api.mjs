// Mock del contrato REAL del backend — NO es un mock permisivo.
//
// Reimplementa las reglas de contrato que el backend impone (sin acceso al
// backend real en E2E UI):
//   - /api/activaciones/desafio   (publico): valida token no-vacio + SPKI
//   - /api/activaciones/canjear   (publico): valida firma ECDSA-DER del payload
//     daily-v1 contra el SPKI registrado en el desafio; emite bootstrap
//   - /api/auth/device/desafio    EXIGE Bearer (bootstrap o JWT mock) -> 401 sin el
//   - /api/auth/device/canjear    valida firma daily-auth-v1, single-use (409),
//     expiracion (410), emite token
//
// Firma: WebCrypto produce raw (P1363); el backend verifica DER (ASN.1). Este
// mock verifica la firma en formato DER, como el backend productivo.

import http from 'node:http';
import crypto from 'node:crypto';

const HTML = { 'Content-Type': 'application/json' };

function json(res, status, body) {
  res.writeHead(status, HTML);
  res.end(JSON.stringify(body));
}

function bearerToken(req) {
  const auth = req.headers['authorization'] || '';
  return auth.replace(/^Bearer\s+/i, '');
}

// ─── estado del mock ────────────────────────────────────────────────────────
// intento_id -> { spki, nonce, expira, consumed, resultado }
const desafiosActivacion = new Map();
// challenge_id -> { nonce, expira, consumido, device_id }
const desafiosSesion = new Map();
// device_id -> { spki, public_key_hash, rol, usuario_id, negocio_id, ruta_id }
const dispositivos = new Map();
// codigo -> device_id (bootstrap emitido)
const bootstrap = new Map();

// ─── alta de negocios (Etapa 3, contrato real OnboardingNegocioResponse) ────
// Replica la frontera de registro publica del backend:
//   - body NO admite negocio_id/rol/plan/estado_suscripcion (extra=forbid -> 422)
//   - NIT normalizado (trim, vacio -> null) + conflicto -> 409
//   - crea negocio con los defaults reales del modelo (CO/COP/basic/al_dia) y
//     un ADMINISTRADOR inicial + codigo de activacion de un solo uso.
// El store es mutable y se resetea explicitamente via /api/_test/reset-onboarding.
const onboardingNegocios = new Map(); // nit -> nombre (conflictos de NIT)

// ─── W1: usuarios del negocio ────────────────────────────────────────────────
const USUARIOS_MOCK = [
  {
    id: 'adm-11111111-1111-4111-8111-111111111111',
    negocio_id: 'n1',
    rol: 'ADMINISTRADOR',
    nombre: 'Admin Principal',
    documento: '1234567890',
    activo: 1,
    creado_el: new Date(Date.now() - 90 * 86400000).toISOString(),
  },
  {
    id: 'cob-22222222-2222-4222-8222-222222222222',
    negocio_id: 'n1',
    rol: 'COBRADOR',
    nombre: 'Carlos Cobrador',
    documento: '9876543210',
    activo: 1,
    creado_el: new Date(Date.now() - 60 * 86400000).toISOString(),
  },
  {
    id: 'inv-33333333-3333-4333-8333-333333333333',
    negocio_id: 'n1',
    rol: 'INVERSIONISTA',
    nombre: 'Maria Inversionista',
    documento: '5555666677',
    activo: 1,
    creado_el: new Date(Date.now() - 30 * 86400000).toISOString(),
  },
  {
    id: 'cob-44444444-4444-4444-8444-444444444444',
    negocio_id: 'n1',
    rol: 'COBRADOR',
    nombre: 'Ana Inactiva',
    documento: '1111222233',
    activo: 0,
    creado_el: new Date(Date.now() - 120 * 86400000).toISOString(),
  },
];

// ─── W2: clientes del negocio ────────────────────────────────────────────────
// Replica el contrato Cliente 360: lista paginada (ClienteListPage), detalle
// (Cliente360Response) y edicion (ClienteUpdate con extra=forbid). El store es
// mutable (crear/editar lo modifican) y el reset entre tests es EXPLICITO via
// POST /api/_test/reset-clientes.
const CLIENTES_FIXTURE = [
  {
    id: 'cli-11111111-1111-4111-8111-111111111111',
    negocio_id: 'n1',
    tipo_documento: 'CC',
    documento_normalizado: '1000000001',
    identity_status: 'VERIFIED',
    primer_apellido: 'Torres',
    segundo_apellido: 'Rojas',
    nombres: 'Ana María',
    telefono_1: '3001234567',
    telefono_2: '3019876543',
    direccion: 'Calle 10 # 5-20',
    barrio: 'Palermo',
    ciudad: 'Bogotá',
    ocupacion: 'Independiente',
    creado_el: new Date(Date.now() - 400 * 86400000).toISOString(),
    creditos: [
      {
        id: 'cred-11111111-1111-4111-8111-111111111111',
        estado: 'ACTIVO',
        cuota: 100000,
        n_cuotas: 12,
        monto: 1000000,
        total: 1200000,
        periodicidad: 'DIARIA',
        fecha_inicio: '2026-07-01',
        saldo: 800000,
        mora_legacy: 5,
        pico: 1200000,
        cuotas_pagadas: 4,
        ruta_id: 'r1',
        ruta_nombre: 'Ruta Centro',
        cobrador_nombre: 'Carlos Cobrador',
      },
    ],
    pagos: [
      {
        id: 'pag-11111111-1111-4111-8111-111111111111',
        credito_id: 'cred-11111111-1111-4111-8111-111111111111',
        tipo: 'PAGO',
        monto: 100000,
        nota: 'Abono',
        recibido_el_servidor: new Date(Date.now() - 86400000).toISOString(),
      },
    ],
  },
  {
    id: 'cli-22222222-2222-4222-8222-222222222222',
    negocio_id: 'n1',
    tipo_documento: 'CC',
    documento_normalizado: '1000000002',
    identity_status: 'PROVISIONAL',
    primer_apellido: 'Gómez',
    segundo_apellido: null,
    nombres: 'Luis Fernando',
    telefono_1: '3002223344',
    telefono_2: null,
    direccion: 'Carrera 8 # 15-40',
    barrio: 'Teusaquillo',
    ciudad: 'Bogotá',
    ocupacion: 'Empleado',
    creado_el: new Date(Date.now() - 30 * 86400000).toISOString(),
    creditos: [
      {
        id: 'cred-22222222-2222-4222-8222-222222222222',
        estado: 'ACTIVO',
        cuota: 50000,
        n_cuotas: 10,
        monto: 500000,
        total: 500000,
        periodicidad: 'SEMANAL',
        fecha_inicio: '2026-08-01',
        saldo: 500000,
        mora_legacy: 0,
        pico: 500000,
        cuotas_pagadas: 0,
        ruta_id: 'r1',
        ruta_nombre: 'Ruta Centro',
        cobrador_nombre: 'Carlos Cobrador',
      },
    ],
    pagos: [],
  },
  {
    id: 'cli-33333333-3333-4333-8333-333333333333',
    negocio_id: 'n1',
    tipo_documento: 'CE',
    documento_normalizado: '2000000001',
    identity_status: 'POSSIBLE_DUPLICATE',
    primer_apellido: 'Ruiz',
    segundo_apellido: 'Pérez',
    nombres: 'Marta Elena',
    telefono_1: '3105556677',
    telefono_2: null,
    direccion: 'Av 30 # 12-88',
    barrio: 'Villa Nueva',
    ciudad: 'Medellín',
    ocupacion: null,
    creado_el: new Date(Date.now() - 10 * 86400000).toISOString(),
    creditos: [
      {
        id: 'cred-33333333-3333-4333-8333-333333333333',
        estado: 'ACTIVO',
        cuota: 80000,
        n_cuotas: 8,
        monto: 640000,
        total: 640000,
        periodicidad: 'DIARIA',
        fecha_inicio: '2026-07-15',
        saldo: 640000,
        mora_legacy: 0,
        pico: 640000,
        cuotas_pagadas: 0,
        ruta_id: 'r2',
        ruta_nombre: 'Ruta Sur',
        cobrador_nombre: 'Pedro Surero',
      },
    ],
    pagos: [],
  },
  {
    id: 'cli-44444444-4444-4444-8444-444444444444',
    negocio_id: 'n1',
    tipo_documento: 'CC',
    documento_normalizado: '1000000003',
    identity_status: 'VERIFIED',
    primer_apellido: 'Vargas',
    segundo_apellido: null,
    nombres: 'Sofía Isabel',
    telefono_1: '3009998877',
    telefono_2: null,
    direccion: null,
    barrio: null,
    ciudad: 'Bogotá',
    ocupacion: 'Estudiante',
    creado_el: new Date(Date.now() - 5 * 86400000).toISOString(),
    creditos: [],
    pagos: [],
  },
];

const CLIENTES_MOCK = CLIENTES_FIXTURE.map((c) => JSON.parse(JSON.stringify(c)));

function clienteListDTO(c) {
  return {
    id: c.id,
    tipo_documento: c.tipo_documento,
    documento_normalizado: c.documento_normalizado,
    identity_status: c.identity_status,
    primer_apellido: c.primer_apellido,
    segundo_apellido: c.segundo_apellido,
    nombres: c.nombres,
    telefono_1: c.telefono_1,
    ciudad: c.ciudad,
    creditos_activos: c.creditos.filter((cr) => cr.estado === 'ACTIVO').length,
    creado_el: c.creado_el,
  };
}

function clienteResponseDTO(c) {
  return {
    id: c.id,
    negocio_id: c.negocio_id,
    tipo_documento: c.tipo_documento,
    documento_normalizado: c.documento_normalizado,
    identity_status: c.identity_status,
    primer_apellido: c.primer_apellido,
    segundo_apellido: c.segundo_apellido,
    nombres: c.nombres,
    telefono_1: c.telefono_1,
    telefono_2: c.telefono_2,
    direccion: c.direccion,
    barrio: c.barrio,
    ciudad: c.ciudad,
    ocupacion: c.ocupacion,
    creado_el: c.creado_el,
  };
}

function cliente360DTO(c) {
  return {
    ...clienteResponseDTO(c),
    creditos: c.creditos,
    pagos_recientes: c.pagos.slice(0, 10),
    saldo_total: c.creditos
      .filter((cr) => cr.estado === 'ACTIVO')
      .reduce((acc, cr) => acc + cr.saldo, 0),
  };
}

function clienteEnRuta(c, routeId) {
  return c.creditos.some((cr) => cr.ruta_id === routeId);
}

function resetClientes() {
  // Re-seed desde el fixture inicial (deep clone): nada mutable sobrevive.
  const seed = CLIENTES_FIXTURE.map((c) => JSON.parse(JSON.stringify(c)));
  CLIENTES_MOCK.length = 0;
  CLIENTES_MOCK.push(...seed);
}

// ─── W3/W4: read model de cartera (deriva de CLIENTES_MOCK) ────────────────
// Replica el contrato CreditoListItem/CreditoDetailResponse: el financiero
// (saldo/mora/pico/cuotas_pagadas) viene del fixture, como en el backend
// viene de hoja_viva_service. INVERSIONISTA -> PII minimizada.
//
// W4: rutas administrables (RutaListItem/RutaListPage/RutaResumenResponse/
// RutaResponse). Store mutable (crear/reasignar lo modifican) con reset
// test-only POST /api/_test/reset-rutas. Los nombres r1='Ruta Centro' y
// r2='Ruta Sur' son coherentes con las sesiones COBRADOR y con CLIENTES_MOCK
// (la sesión COBRADOR está asignada a r1 'Ruta Centro').
const RUTAS_FIXTURE = [
  { id: 'r1', nombre: 'Ruta Centro', cobrador_id: 'u1', cobrador_nombre: 'Carlos M.', activa: 1, version: 1, negocio_id: 'n1', creado_el: new Date(Date.now() - 40 * 86400000).toISOString() },
  { id: 'r2', nombre: 'Ruta Sur', cobrador_id: 'u2', cobrador_nombre: 'Ana P.', activa: 0, version: 2, negocio_id: 'n1', creado_el: new Date(Date.now() - 35 * 86400000).toISOString() },
];

const RUTAS_MOCK = [];

function seedRutas() {
  RUTAS_MOCK.length = 0;
  RUTAS_MOCK.push(...RUTAS_FIXTURE.map((r) => JSON.parse(JSON.stringify(r))));
}
seedRutas();

function resetRutas() {
  seedRutas();
}

function rutaMock(id) {
  return RUTAS_MOCK.find((r) => r.id === id) ?? { id, nombre: '', cobrador_nombre: null };
}

// Envelope de lista (contrato RutaListPage): items con ruta_id (NO id), igual
// que el backend. `activa` se serializa 0/1 (entero, como en el modelo).
function rutaListItem(r) {
  return {
    ruta_id: r.id,
    nombre: r.nombre,
    cobrador_id: r.cobrador_id,
    cobrador_nombre: r.cobrador_nombre,
    activa: r.activa,
    version: r.version,
    creado_el: r.creado_el,
  };
}

function nombreCliente(c) {
  return [c.nombres, c.primer_apellido, c.segundo_apellido].filter(Boolean).join(' ').trim() || null;
}

function creditoListDTO(c, cr, mostrarPii) {
  return {
    id: cr.id,
    cliente_id: mostrarPii ? c.id : null,
    cliente_nombre: mostrarPii ? nombreCliente(c) : null,
    ruta_id: cr.ruta_id,
    ruta_nombre: cr.ruta_nombre ?? rutaMock(cr.ruta_id).nombre,
    cobrador_nombre: cr.cobrador_nombre ?? rutaMock(cr.ruta_id).cobrador_nombre,
    estado: cr.estado,
    cuota: cr.cuota,
    n_cuotas: cr.n_cuotas,
    monto: cr.monto,
    total: cr.total,
    periodicidad: cr.periodicidad,
    fecha_inicio: cr.fecha_inicio,
    saldo: cr.saldo,
    mora: cr.mora_legacy,
    pico: cr.pico,
    cuotas_pagadas: cr.cuotas_pagadas,
    creado_el: c.creado_el,
  };
}

function creditosFlatten(mostrarPii) {
  const out = [];
  for (const c of CLIENTES_MOCK) {
    if (c.negocio_id !== 'n1') continue;
    for (const cr of c.creditos) out.push(creditoListDTO(c, cr, mostrarPii));
  }
  return out;
}

const CREDITO_SORTS = new Set([
  'fecha_inicio', 'monto', 'total', 'cuota', 'periodicidad', 'estado', 'saldo',
]);

const CREDITO_PERIODICIDADES = new Set(['DIARIO', 'SEMANAL', 'QUINCENAL', 'UNICA']);

// ─── W1: audit logs ──────────────────────────────────────────────────────────
const AUDIT_MOCK = [
  {
    id: uuid(),
    negocio_id: 'n1',
    actor_id: 'adm-11111111-1111-4111-8111-111111111111',
    action: 'USUARIO_CREADO',
    entity_type: 'USUARIO',
    entity_id: 'cob-22222222-2222-4222-8222-222222222222',
    metadata: { rol: 'COBRADOR', documento: '9876543210' },
    ip_address: '192.168.1.100',
    user_agent: 'Mozilla/5.0',
    creado_el: new Date(Date.now() - 60 * 86400000).toISOString(),
  },
  {
    id: uuid(),
    negocio_id: 'n1',
    actor_id: 'adm-11111111-1111-4111-8111-111111111111',
    action: 'USUARIO_CREADO',
    entity_type: 'USUARIO',
    entity_id: 'inv-33333333-3333-4333-8333-333333333333',
    metadata: { rol: 'INVERSIONISTA', documento: '5555666677' },
    ip_address: '192.168.1.100',
    user_agent: 'Mozilla/5.0',
    creado_el: new Date(Date.now() - 30 * 86400000).toISOString(),
  },
  {
    id: uuid(),
    negocio_id: 'n1',
    actor_id: 'adm-11111111-1111-4111-8111-111111111111',
    action: 'USUARIO_DESATIVADO',
    entity_type: 'USUARIO',
    entity_id: 'cob-44444444-4444-4444-8444-444444444444',
    metadata: { razon: 'baja voluntaria' },
    ip_address: '192.168.1.100',
    user_agent: 'Mozilla/5.0',
    creado_el: new Date(Date.now() - 15 * 86400000).toISOString(),
  },
  {
    id: uuid(),
    negocio_id: 'n1',
    actor_id: 'adm-11111111-1111-4111-8111-111111111111',
    action: 'CODIGO_ACTIVACION_GENERADO',
    entity_type: 'USUARIO',
    entity_id: 'cob-22222222-2222-4222-8222-222222222222',
    metadata: { prefijo: 'Xz8R4pQ2', expira_minutos: 60 },
    ip_address: '192.168.1.100',
    user_agent: 'Mozilla/5.0',
    creado_el: new Date(Date.now() - 5 * 3600000).toISOString(),
  },
];

function seedOnboarding() {
  onboardingNegocios.clear();
  onboardingNegocios.set('900123456', 'Negocio Existente');
}

function normalizarNit(v) {
  if (typeof v !== 'string') return v;
  const t = v.trim();
  return t || null;
}

function validarAlta(body) {
  const errors = [];
  if (typeof body.nombre !== 'string' || !body.nombre.trim()) errors.push('nombre');
  if (typeof body.nombre === 'string' && body.nombre.trim().length > 255) errors.push('nombre');
  // HARDENING: el contrato publico limita nit/documento a 50 (422, nunca 500),
  // igual que los validadores del backend (Field max_length).
  if (typeof body.nit === 'string' && body.nit.trim().length > 50) errors.push('nit');
  const adm = body.administrador;
  if (!adm || typeof adm !== 'object' || typeof adm.nombre !== 'string' || !adm.nombre.trim()) {
    errors.push('administrador.nombre');
  }
  if (adm && typeof adm.nombre === 'string' && adm.nombre.trim().length > 255) errors.push('administrador.nombre');
  if (adm && typeof adm.documento === 'string' && adm.documento.trim().length > 50) errors.push('administrador.documento');
  const permitidos = new Set(['nombre', 'nit', 'administrador']);
  for (const k of Object.keys(body)) if (!permitidos.has(k)) errors.push(k);
  if (adm && typeof adm === 'object') {
    const permitidosAdm = new Set(['nombre', 'documento']);
    for (const k of Object.keys(adm)) if (!permitidosAdm.has(k)) errors.push(`administrador.${k}`);
  }
  return errors;
}

function altaNegocio(body) {
  const nombre = body.nombre.trim();
  const nit = normalizarNit(body.nit);
  if (nit && onboardingNegocios.has(nit)) {
    return { status: 409, detail: 'El NIT ya esta registrado' };
  }
  const negocio_id = uuid();
  const admin_id = uuid();
  if (nit) onboardingNegocios.set(nit, nombre);
  const ahora = Date.now();
  const token = randomToken();
  const creadoEl = new Date(ahora).toISOString();
  return {
    status: 201,
    body: {
      negocio: {
        id: negocio_id,
        nombre,
        nit: nit ?? null,
        pais: 'CO',
        moneda: 'COP',
        plan: 'basic',
        estado_suscripcion: 'al_dia',
        creado_el: creadoEl,
      },
      administrador: {
        id: admin_id,
        negocio_id,
        rol: 'ADMINISTRADOR',
        nombre: body.administrador.nombre.trim(),
        documento: typeof body.administrador.documento === 'string' && body.administrador.documento.trim()
          ? body.administrador.documento.trim()
          : null,
        activo: 1,
        creado_el: creadoEl,
      },
      codigo_activacion: {
        codigo_id: uuid(),
        token,
        prefijo: token.slice(0, 8),
        expira_el: rfc3339(ahora + 10 * 60 * 1000),
      },
      siguiente_paso: 'activar_codigo',
    },
  };
}

// códigos de activación por rol (contrato real: src/rbac.ROLES).
//
// Cada código está ligado a un usuario objetivo y su rol. El canje de activación
// daily-v1 -> canje emite la credencial bootstrap del DISPOSITIVO del objetivo;
// el rol se deriva del objetivo (como el backend en activacion_service.
// _rol_usuario), NUNCA del cliente ni del token.
//   - COBRADOR: exige ruta activa única (H3); la ruta viaja en el código.
//   - INVERSIONISTA / ADMINISTRADOR: no requieren ruta (dispositivo propio).
// El mock NO es permisivo: un código COBRADOR sin ruta -> 401 del canje, como
// el backend (H3 fail-closed). Rol desconocido -> 409 (default-deny).
const ACTIVATION_TOKENS = new Map([
  // COBRADOR con ruta única — usado por auth-contract.spec.ts y el flujo real.
  ['test-activation-code', { rol: 'COBRADOR', usuario_id: 'c1', negocio_id: 'n1', ruta_id: 'r1', ruta_nombre: 'Ruta Centro' }],
  // Códigos por rol (Commit 4: los 3 roles atraviesan el flujo real de dispositivo).
  ['test-cobrador-code', { rol: 'COBRADOR', usuario_id: 'c1', negocio_id: 'n1', ruta_id: 'r1', ruta_nombre: 'Ruta Centro' }],
  ['test-inversor-code', { rol: 'INVERSIONISTA', usuario_id: 'u_inv', negocio_id: 'n1', ruta_id: null, ruta_nombre: null }],
  ['test-admin-code', { rol: 'ADMINISTRADOR', usuario_id: 'u_admin', negocio_id: 'n1', ruta_id: null, ruta_nombre: null }],
  // Código que emite un intento YA vencido, para probar el 410 del contrato.
  ['test-expired-code', { rol: 'COBRADOR', usuario_id: 'c1', negocio_id: 'n1', ruta_id: 'r1', ruta_nombre: 'Ruta Centro', vencido: true }],
]);

// JWT de sesión pre-emitido para tests de conveniencia. El flujo real de
// dispositivo emite tokens aleatorios por dispositivo (abajo); estos aliases
// estables preservan los specs que inyectan el token directamente
// (rbac-roles.spec.ts), siempre con rol derivado de la "DB" del mock.
const MOCK_JWT = 'mock-jwt-token';            // alias COBRADOR estable
const MOCK_JWT_EXPIRED = 'mock-jwt-expired';  // alias de desafío vencido

// ─── RBAC (replica fiel de src/rbac.py) ─────────────────────────────────────
// El mock NO es permisivo: deriva el rol del token y aplica las mismas reglas
// que el backend. El flujo de dispositivo (daily-v1 / daily-auth-v1) emite el
// rol del usuario objetivo del código (como el backend): un código COBRADOR
// produce una sesión COBRADOR (ruta requerida, H3); INVERSIONISTA/ADMIN un
// dispositivo propio sin ruta. Rol desconocido -> 409 (default-deny).
const ROL_CAPABILITIES = {
  COBRADOR: [
    'jornada:ver', 'jornada:abrir', 'jornada:cerrar',
    'ruta:ver', 'movimientos:ver', 'movimientos:registrar', 'pagos:registrar', 'sync:ver',
    'clientes:ver', 'creditos:ver',
    'cobranza:ver', 'promesas:ver', 'promesas:crear', 'promesas:actualizar',
  ],
  INVERSIONISTA: [
    'inversionista:resumen', 'inversionista:suscripcion',
    'jornadas:ver', 'rutas:ver', 'creditos:ver', 'movimientos:ver',
    'cobranza:ver', 'reportes:ver',
  ],
  ADMINISTRADOR: [
    'inversionista:resumen', 'inversionista:suscripcion',
    'jornadas:ver', 'rutas:ver', 'rutas:crear', 'rutas:reasignar',
    'creditos:ver', 'creditos:gestionar', 'movimientos:ver',
    'codigos:crear', 'dispositivos:registrar',
    'usuarios:ver', 'usuarios:gestionar', 'audit:ver',
    'clientes:ver', 'clientes:gestionar',
    'cobranza:ver', 'cobranza:gestionar',
    'promesas:ver', 'promesas:crear', 'promesas:actualizar',
    'reportes:ver', 'dashboard:ejecutivo',
  ],
};

function capabilities(rol) {
  return ROL_CAPABILITIES[rol] ?? [];
}

// "DB" del mock: token de sesión -> identidad (rol derivado, nunca del token).
// Los aliases estables preservan los specs que inyectan el token directamente;
// el flujo de dispositivo emite tokens aleatorios por dispositivo (abajo).
const SESIONES = new Map([
  ['test-token', { user_id: 'u_inv', usuario_nombre: 'Inversor Test', rol: 'INVERSIONISTA', device_id: null, route_id: null, route_nombre: null }],
  ['mock-custom', { user_id: 'u_inv', usuario_nombre: 'Inversor Test', rol: 'INVERSIONISTA', device_id: null, route_id: null, route_nombre: null, custom: true }],
  ['mock-empty', { user_id: 'u_inv', usuario_nombre: 'Inversor Test', rol: 'INVERSIONISTA', device_id: null, route_id: null, route_nombre: null, empty: true }],
  ['mock-error', { user_id: 'u_inv', usuario_nombre: 'Inversor Test', rol: 'INVERSIONISTA', device_id: null, route_id: null, route_nombre: null, error: true }],
  // Variantes de estado de suscripción (Etapa 3): fieles al contrato real
  // (SuscripcionStatusResponse). El rol nunca cambia; solo el negocio.
  ['mock-vencida', { user_id: 'u_inv', usuario_nombre: 'Inversor Test', rol: 'INVERSIONISTA', device_id: null, route_id: null, route_nombre: null, vencida: true }],
  ['mock-sin-suscripcion', { user_id: 'u_inv', usuario_nombre: 'Inversor Test', rol: 'INVERSIONISTA', device_id: null, route_id: null, route_nombre: null, sinSuscripcion: true }],
  // Alias COBRADOR estable (emitido por el flujo de dispositivo, rol COBRADOR).
  [MOCK_JWT, { user_id: 'u1', usuario_nombre: 'Cobrador Mock', rol: 'COBRADOR', device_id: 'mock-device', route_id: 'r1', route_nombre: 'Ruta Centro' }],
  // Alias para probar un desafío de sesión vencido (410).
  [MOCK_JWT_EXPIRED, { user_id: 'u1', usuario_nombre: 'Cobrador Mock', rol: 'COBRADOR', device_id: 'mock-device', route_id: 'r1', route_nombre: 'Ruta Centro' }],
  // ADMINISTRADOR: la identidad que derivaría la DB para un admin del negocio.
  ['mock-admin', { user_id: 'u_admin', usuario_nombre: 'Admin Mock', rol: 'ADMINISTRADOR', device_id: null, route_id: null, route_nombre: null }],
  // Variantes de gestión de dispositivos (Etapa 3): rol ADMIN sin cambios.
  ['mock-admin-empty', { user_id: 'u_admin', usuario_nombre: 'Admin Mock', rol: 'ADMINISTRADOR', device_id: null, route_id: null, route_nombre: null, sinDispositivos: true }],
  ['mock-admin-error', { user_id: 'u_admin', usuario_nombre: 'Admin Mock', rol: 'ADMINISTRADOR', device_id: null, route_id: null, route_nombre: null, error: true }],
  ['mock-admin-401', { user_id: 'u_admin', usuario_nombre: 'Admin Mock', rol: 'ADMINISTRADOR', device_id: null, route_id: null, route_nombre: null, dispositivos401: true }],
  // Cobrador code alias — necesario para sesionDe() lookup en tests E2E
  ['test-cobrador-code', { user_id: 'c1', usuario_nombre: 'Carlos Cobrador', rol: 'COBRADOR', device_id: 'mock-device', route_id: 'r1', route_nombre: 'Ruta Centro' }],
]);

function sesionDe(token) {
  return SESIONES.get(token) ?? null;
}

function randomToken() {
  return crypto.randomBytes(32).toString('base64url');
}

// Emite un token con forma de JWT (header.payload.sig) cuyo payload lleva el
// device_id (como el token real). El mock no valida firmas, pero el BFF
// `/api/auth/web/desafio` extrae device_id decodificando el payload; usar este
// formato mantiene el mock fiel a la autoridad del token real sin ser permisivo.
function emitSessionToken(deviceId, device) {
  const b64 = (obj) => Buffer.from(JSON.stringify(obj)).toString('base64url');
  const header = b64({ alg: 'ES256', typ: 'JWT' });
  const payload = b64({
    iss: 'daily-mock',
    sub: device.usuario_id ?? 'u1',
    negocio_id: device.negocio_id ?? 'n1',
    device_id: deviceId,
  });
  return `${header}.${payload}.${randomToken()}`;
}

function uuid() {
  return crypto.randomUUID();
}

function publicKeyHash(spkiBase64) {
  return crypto.createHash('sha256').update(Buffer.from(spkiBase64, 'base64')).digest('hex');
}

// ─── dispositivos administrativos (Etapa 3, contrato DispositivoAdminResponse) ──
// Replica el estado que el backend conserva por negocio: estado ACTIVE /
// REVOKED / REPLACED, activo 0/1, fechas y modelo/plataforma. Los IDs son
// UUIDs estables por negocio (como el contrato).
//
// El store interno conserva TODOS los campos del modelo, pero la superficie
// (GET list y las acciones) devuelve SOLO el DTO admin minimizado: jamás se
// exponen huella, public_key_hash, algoritmo_clave, negocio_id ni autorizado_por
// (RBAC review — el mock replica el DTO del backend, no es mas permisivo).
//
// El store es mutable (revocar/reactivar/reemplazar lo modifican) y las
// mutaciones PERSISTEN entre GETs dentro del mismo test: el mock NO se
// re-siembra en cada GET (la persistencia es fiel al backend). El reset
// entre tests es EXPLICITO y test-only: POST /api/_test/reset-dispositivos
// (lo llama un beforeEach de los specs de dispositivos).
const DISPOSITIVOS_FIXTURE = [
  {
    id: 'dev-11111111-1111-4111-8111-111111111111',
    negocio_id: 'n1',
    usuario_id: 'u1',
    huella: null,
    public_key_hash: null,
    algoritmo_clave: 'ES256',
    estado: 'ACTIVE',
    modelo: 'Galaxy A54',
    plataforma: 'android',
    autorizado_por: 'u_admin',
    autorizado_el: new Date(Date.now() - 40 * 24 * 3600 * 1000).toISOString(),
    revocado_el: null,
    ultima_validacion_servidor: new Date(Date.now() - 2 * 3600 * 1000).toISOString(),
    activo: 1,
    creado_el: new Date(Date.now() - 40 * 24 * 3600 * 1000).toISOString(),
  },
  {
    id: 'dev-22222222-2222-4222-8222-222222222222',
    negocio_id: 'n1',
    usuario_id: 'u2',
    huella: null,
    public_key_hash: null,
    algoritmo_clave: 'ES256',
    estado: 'REVOKED',
    modelo: 'iPhone 12',
    plataforma: 'ios',
    autorizado_por: 'u_admin',
    autorizado_el: new Date(Date.now() - 90 * 24 * 3600 * 1000).toISOString(),
    revocado_el: new Date(Date.now() - 10 * 24 * 3600 * 1000).toISOString(),
    ultima_validacion_servidor: new Date(Date.now() - 12 * 24 * 3600 * 1000).toISOString(),
    activo: 0,
    creado_el: new Date(Date.now() - 90 * 24 * 3600 * 1000).toISOString(),
  },
  {
    id: 'dev-33333333-3333-4333-8333-333333333333',
    negocio_id: 'n1',
    usuario_id: 'u3',
    huella: null,
    public_key_hash: null,
    algoritmo_clave: 'ES256',
    estado: 'REPLACED',
    modelo: 'Redmi Note 12',
    plataforma: 'android',
    autorizado_por: 'u_admin',
    autorizado_el: new Date(Date.now() - 120 * 24 * 3600 * 1000).toISOString(),
    revocado_el: new Date(Date.now() - 20 * 24 * 3600 * 1000).toISOString(),
    ultima_validacion_servidor: new Date(Date.now() - 25 * 24 * 3600 * 1000).toISOString(),
    activo: 0,
    creado_el: new Date(Date.now() - 120 * 24 * 3600 * 1000).toISOString(),
  },
  {
    // Mismo cobrador que el ACTIVE (u1): permite ejercitar en la UI el 409 de
    // reactivar ("ya tiene otro dispositivo activo") sin tocar la respuesta.
    id: 'dev-44444444-4444-4444-8444-444444444444',
    negocio_id: 'n1',
    usuario_id: 'u1',
    huella: null,
    public_key_hash: null,
    algoritmo_clave: 'ES256',
    estado: 'REVOKED',
    modelo: 'Moto G84',
    plataforma: 'android',
    autorizado_por: 'u_admin',
    autorizado_el: new Date(Date.now() - 200 * 24 * 3600 * 1000).toISOString(),
    revocado_el: new Date(Date.now() - 30 * 24 * 3600 * 1000).toISOString(),
    ultima_validacion_servidor: new Date(Date.now() - 31 * 24 * 3600 * 1000).toISOString(),
    activo: 0,
    creado_el: new Date(Date.now() - 200 * 24 * 3600 * 1000).toISOString(),
  },
];

function seedDispositivosAdmin() {
  dispositivosAdmin.clear();
  for (const d of DISPOSITIVOS_FIXTURE) dispositivosAdmin.set(d.id, { ...d });
}

const dispositivosAdmin = new Map();

function listaDispositivos() {
  return Array.from(dispositivosAdmin.values()).map(toAdminDTO);
}

/** DTO administrativo minimizado: la superficie web jamas recibe secretos
 *  (huella, public_key_hash, algoritmo_clave) ni tenancy interno (negocio_id,
 *  autorizado_por). Espeja DispositivoAdminResponse del backend. */
function toAdminDTO(dev) {
  return {
    id: dev.id,
    usuario_id: dev.usuario_id,
    estado: dev.estado,
    modelo: dev.modelo,
    plataforma: dev.plataforma,
    autorizado_el: dev.autorizado_el,
    revocado_el: dev.revocado_el,
    ultima_validacion_servidor: dev.ultima_validacion_servidor,
    activo: dev.activo,
    creado_el: dev.creado_el,
  };
}

function nuevoDispositivo(data) {
  const dev = {
    id: uuid(),
    negocio_id: 'n1',
    usuario_id: null,
    huella: data.huella ?? null,
    public_key_hash: null,
    algoritmo_clave: 'ES256',
    estado: 'ACTIVE',
    modelo: data.modelo ?? null,
    plataforma: data.plataforma ?? null,
    autorizado_por: 'u_admin',
    autorizado_el: new Date().toISOString(),
    revocado_el: null,
    ultima_validacion_servidor: new Date().toISOString(),
    activo: 1,
    creado_el: new Date().toISOString(),
  };
  dispositivosAdmin.set(dev.id, dev);
  return dev;
}

function parseSpki(spkiBase64) {
  return crypto.createPublicKey({
    key: Buffer.from(spkiBase64, 'base64'),
    format: 'der',
    type: 'spki',
  });
}

// W6: Promesas mock (module scope para persistir entre requests)
const PROMESAS_MOCK = [];

const server = http.createServer(async (req, res) => {
  console.log(`[mock-api] ${req.method} ${req.url}`);
  const url = new URL(req.url, `http://${req.headers.host}`);
  const path = url.pathname;
  let raw = '';
  for await (const chunk of req) raw += chunk;
  let body = {};
  try { body = raw ? JSON.parse(raw) : {}; } catch { /* malformed */ }

  // ── auth/me (identidad canónica de la sesión) ────────────────────────────
  if (req.method === 'GET' && path === '/api/auth/me') {
    const token = bearerToken(req);
    const sesion = sesionDe(token);
    if (!sesion) return json(res, 401, { detail: 'Credencial de sesion (Bearer JWT) requerida' });
    return json(res, 200, {
      user_id: sesion.user_id,
      usuario_nombre: sesion.usuario_nombre,
      rol: sesion.rol,
      activo: true,
      negocio: {
        negocio_id: 'n1',
        nombre: 'Test Negocio',
        plan: 'basic',
        moneda: 'COP',
        zona_horaria: 'America/Bogota',
        estado_suscripcion: 'al_dia',
        suscripcion_activa: true,
      },
      route_id: sesion.route_id ?? null,
      route_nombre: sesion.route_nombre ?? null,
      device_id: sesion.device_id ?? (sesion.rol === 'COBRADOR' ? 'mock-device' : null),
      version_asignacion: sesion.rol === 'COBRADOR' ? 1 : null,
      capabilities: capabilities(sesion.rol),
    });
  }

  // ── data endpoints (protegidos por RBAC igual que el backend) ────────────
  if (req.method === 'GET' && path === '/api/inversionista/resumen') {
    const token = bearerToken(req);
    const sesion = sesionDe(token);
    if (!sesion) return json(res, 401, { detail: 'Unauthorized' });
    // Fail-closed, igual que inversionista.py: COBRADOR NO tiene la capability.
    if (!capabilities(sesion.rol).includes('inversionista:resumen')) {
      return json(res, 403, { detail: 'Forbidden: el rol COBRADOR no puede ver el resumen de inversion' });
    }
    if (token === 'mock-empty') return json(res, 200, { portfolio: {}, negocio_nombre: 'Empty', plan: 'basic', moneda: 'COP' });
    if (token === 'mock-error') return json(res, 500, { detail: 'Mock internal error' });
    if (token === 'mock-custom') return json(res, 200, { portfolio: { rutas_activas: 5, cobradores_activos: 2, total_creditos_activos: 50, cartera_neta: 10000000, recaudo_hoy: 800000, jornada_cerrada_hoy: true }, negocio_nombre: 'Test Negocio', plan: 'basic', moneda: 'COP' });
    return json(res, 200, { portfolio: { rutas_activas: 3, cobradores_activos: 2, total_creditos_activos: 50, cartera_neta: 5000000, recaudo_hoy: 800000, jornada_cerrada_hoy: true }, negocio_nombre: 'Test Negocio', plan: 'basic', moneda: 'COP' });
  }

  // ── GET /api/inversionista/suscripcion (Etapa 3, contrato real) ───────────
  // Replica SuscripcionStatusResponse y las reglas de inversionista.py:
  //   - solo INVERSIONISTA | ADMINISTRADOR (403 fail-closed para COBRADOR)
  //   - 200 { negocio_id, estado_suscripcion, plan, paid_through_at, activa }
  //   - activa = estado_suscripcion == 'al_dia' && (paid_through_at null o futuro)
  // El estado se deriva del negocio del mock, NUNCA del token/cliente.
  if (req.method === 'GET' && path === '/api/inversionista/suscripcion') {
    const token = bearerToken(req);
    const sesion = sesionDe(token);
    if (!sesion) return json(res, 401, { detail: 'Unauthorized' });
    if (!capabilities(sesion.rol).includes('inversionista:suscripcion')) {
      return json(res, 403, { detail: 'Forbidden: el rol no puede ver la suscripcion' });
    }
    if (token === 'mock-error') return json(res, 500, { detail: 'Mock internal error' });
    if (sesion.vencida) {
      return json(res, 200, {
        negocio_id: 'n1',
        estado_suscripcion: 'vencida',
        plan: 'basic',
        paid_through_at: new Date(Date.now() - 24 * 3600 * 1000).toISOString(),
        activa: false,
      });
    }
    if (sesion.sinSuscripcion) {
      return json(res, 200, {
        negocio_id: 'n1',
        estado_suscripcion: 'sin_suscripcion',
        plan: 'basic',
        paid_through_at: null,
        activa: false,
      });
    }
    return json(res, 200, {
      negocio_id: 'n1',
      estado_suscripcion: 'al_dia',
      plan: 'basic',
      paid_through_at: new Date(Date.now() + 30 * 24 * 3600 * 1000).toISOString(),
      activa: true,
    });
  }

  // ── reset test-only (fuera del contrato productivo) ────────────────────────
  // El mock NO se re-siembra en cada GET: las mutaciones persisten dentro de
  // cada test. El reset entre tests es EXPLICITO y lo invoca un beforeEach de
  // los specs (persistencia fiel al backend, sin seed por GET).
  if (req.method === 'POST' && path === '/api/_test/reset-dispositivos') {
    seedDispositivosAdmin();
    return json(res, 200, { ok: true });
  }
  if (req.method === 'POST' && path === '/api/_test/reset-onboarding') {
    seedOnboarding();
    return json(res, 200, { ok: true });
  }
  if (req.method === 'POST' && path === '/api/_test/reset-clientes') {
    resetClientes();
    return json(res, 200, { ok: true });
  }
  if (req.method === 'POST' && path === '/api/_test/reset-creditos') {
    resetClientes();
    return json(res, 200, { ok: true });
  }
  if (req.method === 'POST' && path === '/api/_test/reset-rutas') {
    resetRutas();
    return json(res, 200, { ok: true });
  }

  // ── W3: GET /api/creditos/resumen (agregados scoped, creditos:ver) ─────────
  if (req.method === 'GET' && path === '/api/creditos/resumen') {
    const token = bearerToken(req);
    const ses = sesionDe(token);
    if (!ses) return json(res, 401, { detail: 'Credencial de sesion requerida' });
    if (!capabilities(ses.rol).includes('creditos:ver')) {
      return json(res, 403, { detail: 'No autorizado para creditos:ver' });
    }
    let filas = creditosFlatten(true);
    if (ses.rol === 'COBRADOR') filas = filas.filter((f) => f.ruta_id === ses.route_id);
    const activos = filas.filter((f) => f.estado === 'ACTIVO');
    return json(res, 200, {
      total_creditos: filas.length,
      activos: activos.length,
      saldo_total_cartera: activos.reduce((acc, f) => acc + f.saldo, 0),
      en_mora: activos.filter((f) => f.mora > 0).length,
    });
  }

  // ── W3: GET /api/creditos (read model paginado, creditos:ver) ──────────────
  if (req.method === 'GET' && path === '/api/creditos') {
    const token = bearerToken(req);
    const ses = sesionDe(token);
    if (!ses) return json(res, 401, { detail: 'Credencial de sesion requerida' });
    if (!capabilities(ses.rol).includes('creditos:ver')) {
      return json(res, 403, { detail: 'No autorizado para creditos:ver' });
    }

    const query = new URL(req.url, 'http://localhost').searchParams;
    const q = query.get('q');
    const estado = query.get('estado');
    const ruta_id = query.get('ruta_id');
    const limit = Math.min(parseInt(query.get('limit') || '50', 10) || 50, 100);
    const offset = parseInt(query.get('offset') || '0', 10) || 0;
    const sort = query.get('sort') || 'fecha_inicio';
    const order = query.get('order') || 'desc';
    if (!CREDITO_SORTS.has(sort)) return json(res, 422, { detail: `sort no permitido: ${sort}` });
    if (order !== 'asc' && order !== 'desc') return json(res, 422, { detail: 'order debe ser asc o desc' });

    // INVERSIONISTA: read-only con PII minimizada; q no aplica (busca sobre PII).
    const mostrarPii = ses.rol !== 'INVERSIONISTA';
    let filas = creditosFlatten(mostrarPii);

    if (ses.rol === 'COBRADOR') {
      filas = filas.filter((f) => f.ruta_id === ses.route_id);
      if (ruta_id && ruta_id !== ses.route_id) {
        return json(res, 404, { detail: 'Créditos no encontrados' });
      }
    } else if (ruta_id) {
      filas = filas.filter((f) => f.ruta_id === ruta_id);
    }

    if (estado) filas = filas.filter((f) => f.estado === estado);
    if (q && mostrarPii) {
      const term = q.trim().toLowerCase();
      filas = filas.filter((f) => (f.cliente_nombre || '').toLowerCase().includes(term));
    }

    const total = filas.length;
    const rev = order === 'desc';
    const key = (f) => f[sort] ?? '';
    filas.sort((a, b) => {
      const av = key(a);
      const bv = key(b);
      if (av < bv) return rev ? 1 : -1;
      if (av > bv) return rev ? -1 : 1;
      return 0;
    });
    const items = filas.slice(offset, offset + limit);
    return json(res, 200, { items, total, limit, offset });
  }

  // ── W3: POST /api/creditos (crear, SOLO creditos:gestionar) ────────────────
  if (req.method === 'POST' && path === '/api/creditos') {
    const token = bearerToken(req);
    const ses = sesionDe(token);
    if (!ses) return json(res, 401, { detail: 'Credencial de sesion requerida' });
    if (!capabilities(ses.rol).includes('creditos:gestionar')) {
      return json(res, 403, { detail: 'No autorizado para creditos:gestionar' });
    }

    const permitidos = new Set([
      'cliente_id', 'ruta_id', 'cuota', 'n_cuotas', 'monto', 'fecha_inicio', 'periodicidad',
    ]);
    for (const k of Object.keys(body)) if (!permitidos.has(k)) {
      return json(res, 422, { detail: `Campo no permitido: ${k}` });
    }

    const cliente = CLIENTES_MOCK.find((c) => c.id === body.cliente_id && c.negocio_id === 'n1');
    if (!cliente) return json(res, 404, { detail: 'Cliente no encontrado' });
    const ruta = RUTAS_MOCK.find((r) => r.id === body.ruta_id);
    if (!ruta) return json(res, 404, { detail: 'Ruta no encontrada' });

    if (!Number.isInteger(body.cuota) || body.cuota <= 0) return json(res, 422, { detail: 'cuota invalida' });
    if (!Number.isInteger(body.n_cuotas) || body.n_cuotas <= 0) return json(res, 422, { detail: 'n_cuotas invalido' });
    if (!Number.isInteger(body.monto) || body.monto <= 0) return json(res, 422, { detail: 'monto invalido' });
    if (!body.fecha_inicio || !/^\d{4}-\d{2}-\d{2}$/.test(body.fecha_inicio)) {
      return json(res, 422, { detail: 'fecha_inicio invalida' });
    }
    const periodicidad = body.periodicidad ?? 'DIARIO';
    if (!CREDITO_PERIODICIDADES.has(periodicidad)) return json(res, 422, { detail: 'periodicidad invalida' });

    const total = body.cuota * body.n_cuotas;
    const nuevo = {
      id: uuid(),
      estado: 'ACTIVO',
      cuota: body.cuota,
      n_cuotas: body.n_cuotas,
      monto: body.monto,
      total,
      periodicidad,
      fecha_inicio: body.fecha_inicio,
      saldo: total,
      mora_legacy: 0,
      pico: total,
      cuotas_pagadas: 0,
      ruta_id: ruta.id,
      ruta_nombre: ruta.nombre,
      cobrador_nombre: ruta.cobrador_nombre,
    };
    cliente.creditos.push(nuevo);
    return json(res, 201, {
      id: nuevo.id,
      negocio_id: 'n1',
      cliente_id: cliente.id,
      ruta_id: ruta.id,
      cuota: nuevo.cuota,
      n_cuotas: nuevo.n_cuotas,
      monto: nuevo.monto,
      total: nuevo.total,
      periodicidad: nuevo.periodicidad,
      fecha_inicio: nuevo.fecha_inicio,
      estado: nuevo.estado,
      tasa_efectiva_anual: null,
      residuo_redondeo: 0,
      version: 1,
      creado_el: new Date().toISOString(),
    });
  }

  // ── W3: GET /api/creditos/:id (detalle, creditos:ver) ─────────────────────
  if (req.method === 'GET' && path.startsWith('/api/creditos/')) {
    const token = bearerToken(req);
    const ses = sesionDe(token);
    if (!ses) return json(res, 401, { detail: 'Credencial de sesion requerida' });
    if (!capabilities(ses.rol).includes('creditos:ver')) {
      return json(res, 403, { detail: 'No autorizado para creditos:ver' });
    }

    const id = path.split('/').pop();
    const mostrarPii = ses.rol !== 'INVERSIONISTA';
    const fila = creditosFlatten(mostrarPii).find((f) => f.id === id);
    if (!fila) return json(res, 404, { detail: 'Crédito no encontrado' });
    if (ses.rol === 'COBRADOR' && fila.ruta_id !== ses.route_id) {
      return json(res, 404, { detail: 'Crédito no encontrado' });
    }
    return json(res, 200, { ...fila, negocio_id: 'n1' });
  }

  // ── W5: GET /api/movimientos/web (read model paginado, movimientos:ver) ────
  const MOVIMIENTOS_MOCK = [
    { id: 'mov-1', negocio_id: 'n1', jornada_id: 'j1', tipo: 'GASOLINA', naturaleza: 'GASTO', monto: 50000, nota: 'Gasolina ruta centro', clave_idempotencia: 'w5-1', creado_por: 'u-cob1', creado_por_nombre: 'Carlos M.', creado_el: '2026-08-16T08:00:00Z', jornada_fecha: '2026-08-16', ruta_id: 'r1', ruta_nombre: 'Ruta Centro' },
    { id: 'mov-2', negocio_id: 'n1', jornada_id: 'j1', tipo: 'OFICINA', naturaleza: 'GASTO', monto: 20000, nota: 'Material oficina', clave_idempotencia: 'w5-2', creado_por: 'u-cob1', creado_por_nombre: 'Carlos M.', creado_el: '2026-08-16T09:00:00Z', jornada_fecha: '2026-08-16', ruta_id: 'r1', ruta_nombre: 'Ruta Centro' },
    { id: 'mov-3', negocio_id: 'n1', jornada_id: 'j1', tipo: 'RECIBIDO', naturaleza: 'CUENTA_POR_COBRAR', monto: 100000, nota: 'Cobro cliente A', clave_idempotencia: 'w5-3', creado_por: 'u-cob1', creado_por_nombre: 'Carlos M.', creado_el: '2026-08-16T10:00:00Z', jornada_fecha: '2026-08-16', ruta_id: 'r1', ruta_nombre: 'Ruta Centro' },
    { id: 'mov-4', negocio_id: 'n1', jornada_id: 'j2', tipo: 'COMBUSTIBLE', naturaleza: 'GASTO', monto: 35000, nota: 'Combustible ruta sur', clave_idempotencia: 'w5-4', creado_por: 'u-cob2', creado_por_nombre: 'Ana P.', creado_el: '2026-08-15T08:00:00Z', jornada_fecha: '2026-08-15', ruta_id: 'r2', ruta_nombre: 'Ruta Sur' },
    { id: 'mov-5', negocio_id: 'n1', jornada_id: 'j2', tipo: 'RECIBIDO', naturaleza: 'CUENTA_POR_COBRAR', monto: 75000, nota: 'Cobro cliente B', clave_idempotencia: 'w5-5', creado_por: 'u-cob2', creado_por_nombre: 'Ana P.', creado_el: '2026-08-15T09:00:00Z', jornada_fecha: '2026-08-15', ruta_id: 'r2', ruta_nombre: 'Ruta Sur' },
  ];
  const MOV_SORTS = new Set(['creado_el', 'monto', 'tipo']);

  if (req.method === 'GET' && path === '/api/movimientos/web') {
    const token = bearerToken(req);
    const ses = sesionDe(token);
    if (!ses) return json(res, 401, { detail: 'Credencial de sesion requerida' });
    if (!capabilities(ses.rol).includes('movimientos:ver')) {
      return json(res, 403, { detail: 'No autorizado para movimientos:ver' });
    }

    const query = new URL(req.url, 'http://localhost').searchParams;
    const q = query.get('q');
    const tipo = query.get('tipo');
    const naturaleza = query.get('naturaleza');
    const ruta_id = query.get('ruta_id');
    const limit = Math.min(parseInt(query.get('limit') || '50', 10) || 50, 100);
    const offset = parseInt(query.get('offset') || '0', 10) || 0;
    const sort = query.get('sort') || 'creado_el';
    const order = query.get('order') || 'desc';
    if (!MOV_SORTS.has(sort)) return json(res, 422, { detail: `sort no permitido: ${sort}` });

    let filas = MOVIMIENTOS_MOCK.slice();
    if (ses.rol === 'COBRADOR') filas = filas.filter((f) => f.ruta_id === ses.route_id);
    if (q) filas = filas.filter((f) => (f.nota || '').toLowerCase().includes(q.toLowerCase()));
    if (tipo) filas = filas.filter((f) => f.tipo === tipo);
    if (naturaleza) filas = filas.filter((f) => f.naturaleza === naturaleza);
    if (ruta_id) filas = filas.filter((f) => f.ruta_id === ruta_id);

    const dir = order === 'desc' ? -1 : 1;
    filas.sort((a, b) => {
      const va = a[sort] ?? '';
      const vb = b[sort] ?? '';
      return va < vb ? -dir : va > vb ? dir : 0;
    });

    const total = filas.length;
    const items = filas.slice(offset, offset + limit).map((f) => {
      const out = {
        id: f.id,
        tipo: f.tipo,
        naturaleza: f.naturaleza,
        monto: f.monto,
        nota: f.nota,
        creado_por_nombre: f.creado_por_nombre,
        creado_el: f.creado_el,
        jornada_fecha: f.jornada_fecha,
        ruta_id: f.ruta_id,
        ruta_nombre: f.ruta_nombre,
      };
      if (ses.rol === 'INVERSIONISTA') {
        out.creado_por_nombre = null;
        out.nota = null;
      }
      return out;
    });
    return json(res, 200, { items, total, limit, offset });
  }

  // ── W5: GET /api/movimientos/resumen (agregados, movimientos:ver) ──────────
  if (req.method === 'GET' && path === '/api/movimientos/resumen') {
    const token = bearerToken(req);
    const ses = sesionDe(token);
    if (!ses) return json(res, 401, { detail: 'Credencial de sesion requerida' });
    if (!capabilities(ses.rol).includes('movimientos:ver')) {
      return json(res, 403, { detail: 'No autorizado para movimientos:ver' });
    }

    let filas = MOVIMIENTOS_MOCK.slice();
    if (ses.rol === 'COBRADOR') filas = filas.filter((f) => f.ruta_id === ses.route_id);
    const totalMov = filas.length;
    const totalMonto = filas.reduce((acc, f) => acc + f.monto, 0);
    const gastos = filas.filter((f) => f.naturaleza === 'GASTO');
    const porTipo = {};
    for (const g of gastos) {
      if (!porTipo[g.tipo]) porTipo[g.tipo] = { tipo: g.tipo, total: 0, count: 0 };
      porTipo[g.tipo].total += g.monto;
      porTipo[g.tipo].count += 1;
    }
    return json(res, 200, {
      total_movimientos: totalMov,
      total_monto: totalMonto,
      gastos_por_tipo: Object.values(porTipo),
    });
  }

  // ── W6: GET /api/cobranza/web (worklist, cobranza:ver) ─────────────────────
  const COBRANZA_FIXTURE = [
    {
      credito_id: 'c1', cliente_id: 'cl1', cliente_nombre: 'Juan Perez',
      ruta_id: 'r1', ruta_nombre: 'Ruta Centro', cobrador_id: 'u2', cobrador_nombre: 'Cobrador Uno',
      estado: 'ACTIVO', total: 1200000, saldo: 800000, cuota: 200000, n_cuotas: 6,
      cuotas_pagadas: 2, mora_legacy: 5, days_past_due: 12,
      overdue_installments: 2, overdue_amount: 400000, aging_bucket: '8-15',
      oldest_unpaid_due_date: '2026-08-05',
    },
    {
      credito_id: 'c2', cliente_id: 'cl2', cliente_nombre: 'Maria Gomez',
      ruta_id: 'r1', ruta_nombre: 'Ruta Centro', cobrador_id: 'u2', cobrador_nombre: 'Cobrador Uno',
      estado: 'ACTIVO', total: 600000, saldo: 600000, cuota: 200000, n_cuotas: 3,
      cuotas_pagadas: 0, mora_legacy: 20, days_past_due: 25,
      overdue_installments: 3, overdue_amount: 600000, aging_bucket: '16-30',
      oldest_unpaid_due_date: '2026-07-15',
    },
    {
      credito_id: 'c3', cliente_id: 'cl3', cliente_nombre: 'Carlos Ruiz',
      ruta_id: 'r2', ruta_nombre: 'Ruta Sur', cobrador_id: 'u2', cobrador_nombre: 'Cobrador Uno',
      estado: 'ACTIVO', total: 300000, saldo: 100000, cuota: 100000, n_cuotas: 3,
      cuotas_pagadas: 2, mora_legacy: 0, days_past_due: 0,
      overdue_installments: 0, overdue_amount: 0, aging_bucket: 'CURRENT',
      oldest_unpaid_due_date: null,
    },
  ];

  if (req.method === 'GET' && path === '/api/cobranza/web') {
    const token = bearerToken(req);
    const ses = sesionDe(token);
    if (!ses) return json(res, 401, { detail: 'Credencial de sesion requerida' });
    if (!capabilities(ses.rol).includes('cobranza:ver')) {
      return json(res, 403, { detail: 'No autorizado para cobranza:ver' });
    }

    let filas = COBRANZA_FIXTURE.slice();
    if (ses.rol === 'COBRADOR') filas = filas.filter((f) => f.ruta_id === ses.route_id);

    const limit = Math.min(parseInt(url.searchParams.get('limit') ?? '50', 10), 100);
    const offset = parseInt(url.searchParams.get('offset') ?? '0', 10);
    const sort = url.searchParams.get('sort') ?? 'priority';
    const order = url.searchParams.get('order') ?? 'desc';
    const agingBucket = url.searchParams.get('bucket') || url.searchParams.get('aging_bucket');
    const estado = url.searchParams.get('estado');

    if (agingBucket) filas = filas.filter((f) => f.aging_bucket === agingBucket);
    if (estado) filas = filas.filter((f) => f.estado === estado);

    const cmp = sort === 'saldo' ? (a, b) => a.saldo - b.saldo
      : sort === 'days_past_due' ? (a, b) => a.days_past_due - b.days_past_due
      : (a, b) => b.days_past_due - a.days_past_due;
    if (order === 'asc') filas.sort(cmp); else filas.sort((a, b) => cmp(b, a));

    const items = filas.slice(offset, offset + limit).map((f) => {
      if (ses.rol === 'INVERSIONISTA') {
        return { ...f, cliente_nombre: null, cliente_id: null, cobrador_nombre: null };
      }
      return f;
    });

    return json(res, 200, { items, total: filas.length, limit, offset });
  }

  // ── W6: GET /api/cobranza/resumen (KPIs, cobranza:ver) ─────────────────────
  if (req.method === 'GET' && path === '/api/cobranza/resumen') {
    const token = bearerToken(req);
    const ses = sesionDe(token);
    if (!ses) return json(res, 401, { detail: 'Credencial de sesion requerida' });
    if (!capabilities(ses.rol).includes('cobranza:ver')) {
      return json(res, 403, { detail: 'No autorizado para cobranza:ver' });
    }

    let filas = COBRANZA_FIXTURE.slice();
    if (ses.rol === 'COBRADOR') filas = filas.filter((f) => f.ruta_id === ses.route_id);

    const aging = {};
    for (const b of ['CURRENT', '1-7', '8-15', '16-30', '31-60', '61-90', '90+']) aging[b] = 0;
    for (const f of filas) aging[f.aging_bucket] = (aging[f.aging_bucket] ?? 0) + 1;

    return json(res, 200, {
      total_creditos: filas.length,
      total_saldo: filas.reduce((a, f) => a + f.saldo, 0),
      total_vencido: filas.reduce((a, f) => a + f.overdue_amount, 0),
      creditos_en_mora: filas.filter((f) => f.days_past_due > 0).length,
      aging_distribution: aging,
    });
  }

  // ── W6: GET /api/cobranza/{credito_id} (drill-down, cobranza:ver) ──────────
  const cobranzaMatch = path.match(/^\/api\/cobranza\/([^/]+)$/);
  if (req.method === 'GET' && cobranzaMatch) {
    const token = bearerToken(req);
    const ses = sesionDe(token);
    if (!ses) return json(res, 401, { detail: 'Credencial de sesion requerida' });
    if (!capabilities(ses.rol).includes('cobranza:ver')) {
      return json(res, 403, { detail: 'No autorizado para cobranza:ver' });
    }

    const creditoId = cobranzaMatch[1];
    const cred = COBRANZA_FIXTURE.find((f) => f.credito_id === creditoId);
    if (!cred) return json(res, 404, { detail: 'Credito no encontrado' });
    if (ses.rol === 'COBRADOR' && cred.ruta_id !== ses.route_id) {
      return json(res, 404, { detail: 'Credito no encontrado' });
    }

    const result = {
      ...cred,
      obligaciones_vencidas: cred.overdue_installments > 0
        ? Array.from({ length: cred.overdue_installments }, (_, i) => ({
            numero: cred.cuotas_pagadas + i + 1,
            fecha_vencimiento: cred.oldest_unpaid_due_date ?? '2026-08-01',
            monto: cred.cuota,
            estado: 'PENDIENTE',
          }))
        : [],
      pagos_recientes: cred.cuotas_pagadas > 0
        ? Array.from({ length: cred.cuotas_pagadas }, (_, i) => ({
            id: `pay-${creditoId}-${i}`,
            tipo: 'PAYMENT',
            monto: cred.cuota,
            recibido_el: '2026-07-01',
            nota: null,
          }))
        : [],
      promesas: PROMESAS_MOCK.filter((p) => p.credito_id === creditoId).map((p) => ({
        id: p.id, amount: p.amount, promised_date: p.promised_date,
        estado: p.estado, nota: ses.rol === 'INVERSIONISTA' ? null : p.nota,
        creado_el: p.creado_el,
      })),
    };

    if (ses.rol === 'INVERSIONISTA') {
      result.cliente_nombre = null;
      result.cliente_id = null;
      result.cobrador_nombre = null;
    }

    return json(res, 200, result);
  }

  // ── W6: POST /api/cobranza/promesas (crear, promesas:crear) ────────────────
  if (req.method === 'POST' && path === '/api/cobranza/promesas') {
    const token = bearerToken(req);
    const ses = sesionDe(token);
    if (!ses) return json(res, 401, { detail: 'Credencial de sesion requerida' });
    if (!capabilities(ses.rol).includes('promesas:crear')) {
      return json(res, 403, { detail: 'No autorizado para promesas:crear' });
    }

    const { credito_id, amount, promised_date, nota, clave_idempotencia } = body;

    if (!credito_id) return json(res, 422, { detail: 'credito_id requerido' });
    if (!amount || amount <= 0) return json(res, 422, { detail: 'amount debe ser > 0' });
    if (!promised_date) return json(res, 422, { detail: 'promised_date requerido' });

    const cred = COBRANZA_FIXTURE.find((f) => f.credito_id === credito_id);
    if (!cred) return json(res, 404, { detail: 'Credito no encontrado' });
    if (ses.rol === 'COBRADOR' && cred.ruta_id !== ses.route_id) {
      return json(res, 404, { detail: 'Credito no encontrado' });
    }

    const existing = PROMESAS_MOCK.find((p) => p.credito_id === credito_id && p.estado === 'ACTIVE');
    if (existing) return json(res, 409, { detail: 'Ya existe una promesa activa para este credito' });

    const promesa = {
      id: `prom-${PROMESAS_MOCK.length + 1}`,
      credito_id,
      amount,
      promised_date,
      nota: ses.rol === 'INVERSIONISTA' ? null : nota,
      estado: 'ACTIVE',
      creado_el: new Date().toISOString(),
      clave_idempotencia,
    };
    PROMESAS_MOCK.push(promesa);
    return json(res, 201, { id: promesa.id, estado: promesa.estado });
  }

  // ── W6: POST /api/cobranza/promesas/{id}/cumplir ───────────────────────────
  const promesaCumplirMatch = path.match(/^\/api\/cobranza\/promesas\/([^/]+)\/cumplir$/);
  if (req.method === 'POST' && promesaCumplirMatch) {
    const token = bearerToken(req);
    const ses = sesionDe(token);
    if (!ses) return json(res, 401, { detail: 'Credencial de sesion requerida' });
    if (!capabilities(ses.rol).includes('promesas:actualizar')) {
      return json(res, 403, { detail: 'No autorizado para promesas:actualizar' });
    }
    const p = PROMESAS_MOCK.find((x) => x.id === promesaCumplirMatch[1]);
    if (!p) return json(res, 404, { detail: 'Promesa no encontrada' });
    if (p.estado !== 'ACTIVE') return json(res, 409, { detail: `Promesa en estado ${p.estado}` });
    p.estado = 'FULFILLED';
    return json(res, 200, { id: p.id, estado: p.estado });
  }

  // ── W6: POST /api/cobranza/promesas/{id}/incumplir ─────────────────────────
  const promesaIncumplirMatch = path.match(/^\/api\/cobranza\/promesas\/([^/]+)\/incumplir$/);
  if (req.method === 'POST' && promesaIncumplirMatch) {
    const token = bearerToken(req);
    const ses = sesionDe(token);
    if (!ses) return json(res, 401, { detail: 'Credencial de sesion requerida' });
    if (!capabilities(ses.rol).includes('promesas:actualizar')) {
      return json(res, 403, { detail: 'No autorizado para promesas:actualizar' });
    }
    const p = PROMESAS_MOCK.find((x) => x.id === promesaIncumplirMatch[1]);
    if (!p) return json(res, 404, { detail: 'Promesa no encontrada' });
    if (p.estado !== 'ACTIVE') return json(res, 409, { detail: `Promesa en estado ${p.estado}` });
    p.estado = 'BROKEN';
    return json(res, 200, { id: p.id, estado: p.estado });
  }

  // ── W6: POST /api/cobranza/promesas/{id}/cancelar ──────────────────────────
  const promesaCancelarMatch = path.match(/^\/api\/cobranza\/promesas\/([^/]+)\/cancelar$/);
  if (req.method === 'POST' && promesaCancelarMatch) {
    const token = bearerToken(req);
    const ses = sesionDe(token);
    if (!ses) return json(res, 401, { detail: 'Credencial de sesion requerida' });
    if (!capabilities(ses.rol).includes('promesas:actualizar')) {
      return json(res, 403, { detail: 'No autorizado para promesas:actualizar' });
    }
    const p = PROMESAS_MOCK.find((x) => x.id === promesaCancelarMatch[1]);
    if (!p) return json(res, 404, { detail: 'Promesa no encontrada' });
    if (p.estado !== 'ACTIVE') return json(res, 409, { detail: `Promesa en estado ${p.estado}` });
    p.estado = 'CANCELLED';
    return json(res, 200, { id: p.id, estado: p.estado });
  }

  // ── W7: GET /api/reportes/resumen (reportes:ver) ───────────────────────────
  if (req.method === 'GET' && path === '/api/reportes/resumen') {
    const token = bearerToken(req);
    const ses = sesionDe(token);
    if (!ses) return json(res, 401, { detail: 'Credencial de sesion requerida' });
    if (!capabilities(ses.rol).includes('reportes:ver')) {
      return json(res, 403, { detail: 'No autorizado para reportes:ver' });
    }
    const periodo = new URL(req.url, 'http://localhost').searchParams.get('periodo') ?? 'hoy';
    return json(res, 200, {
      periodo,
      fecha_inicio: '2026-08-17',
      fecha_fin: '2026-08-17',
      cartera_vigente: 15000000,
      cartera_vencida: 2500000,
      pct_vencido: 16.7,
      recaudo_periodo: 3500000,
      gastos_periodo: 450000,
      neto_periodo: 3050000,
    });
  }

  // ── W7: GET /api/reportes/recaudo (reportes:ver) ───────────────────────────
  if (req.method === 'GET' && path === '/api/reportes/recaudo') {
    const token = bearerToken(req);
    const ses = sesionDe(token);
    if (!ses) return json(res, 401, { detail: 'Credencial de sesion requerida' });
    if (!capabilities(ses.rol).includes('reportes:ver')) {
      return json(res, 403, { detail: 'No autorizado para reportes:ver' });
    }
    const periodo = new URL(req.url, 'http://localhost').searchParams.get('periodo') ?? '7d';
    const serie = [
      { fecha: '2026-08-11', recaudo: 500000, reversal: 50000, neto: 450000 },
      { fecha: '2026-08-12', recaudo: 600000, reversal: 30000, neto: 570000 },
      { fecha: '2026-08-13', recaudo: 450000, reversal: 0, neto: 450000 },
      { fecha: '2026-08-14', recaudo: 700000, reversal: 100000, neto: 600000 },
      { fecha: '2026-08-15', recaudo: 550000, reversal: 20000, neto: 530000 },
      { fecha: '2026-08-16', recaudo: 650000, reversal: 0, neto: 650000 },
      { fecha: '2026-08-17', recaudo: 550000, reversal: 0, neto: 550000 },
    ];
    const total_recaudo = serie.reduce((s, x) => s + x.recaudo, 0);
    const total_reversal = serie.reduce((s, x) => s + x.reversal, 0);
    const total_neto = serie.reduce((s, x) => s + x.neto, 0);
    return json(res, 200, { periodo, fecha_inicio: '2026-08-11', fecha_fin: '2026-08-17', serie, total_recaudo, total_reversal, total_neto });
  }

  // ── W7: GET /api/reportes/aging (reportes:ver) ─────────────────────────────
  if (req.method === 'GET' && path === '/api/reportes/aging') {
    const token = bearerToken(req);
    const ses = sesionDe(token);
    if (!ses) return json(res, 401, { detail: 'Credencial de sesion requerida' });
    if (!capabilities(ses.rol).includes('reportes:ver')) {
      return json(res, 403, { detail: 'No autorizado para reportes:ver' });
    }
    return json(res, 200, {
      fecha: '2026-08-17',
      buckets: {
        CURRENT: { count: 12, amount: 0 },
        '1-7': { count: 3, amount: 500000 },
        '8-15': { count: 2, amount: 350000 },
        '16-30': { count: 1, amount: 200000 },
        '31-60': { count: 1, amount: 150000 },
        '61-90': { count: 0, amount: 0 },
        '90+': { count: 0, amount: 0 },
      },
    });
  }

  // ── W7: GET /api/reportes/rutas (reportes:ver) ─────────────────────────────
  if (req.method === 'GET' && path === '/api/reportes/rutas') {
    const token = bearerToken(req);
    const ses = sesionDe(token);
    if (!ses) return json(res, 401, { detail: 'Credencial de sesion requerida' });
    if (!capabilities(ses.rol).includes('reportes:ver')) {
      return json(res, 403, { detail: 'No autorizado para reportes:ver' });
    }
    const periodo = new URL(req.url, 'http://localhost').searchParams.get('periodo') ?? 'hoy';
    return json(res, 200, {
      periodo,
      rutas: [
        { ruta_id: 'r1', ruta_nombre: 'Ruta Centro', cartera: 5000000, vencido: 800000, creditos: 8 },
        { ruta_id: 'r2', ruta_nombre: 'Ruta Norte', cartera: 4500000, vencido: 600000, creditos: 6 },
        { ruta_id: 'r3', ruta_nombre: 'Ruta Sur', cartera: 5500000, vencido: 1100000, creditos: 7 },
      ],
    });
  }

  // ── W7: GET /api/reportes/movimientos (reportes:ver) ───────────────────────
  if (req.method === 'GET' && path === '/api/reportes/movimientos') {
    const token = bearerToken(req);
    const ses = sesionDe(token);
    if (!ses) return json(res, 401, { detail: 'Credencial de sesion requerida' });
    if (!capabilities(ses.rol).includes('reportes:ver')) {
      return json(res, 403, { detail: 'No autorizado para reportes:ver' });
    }
    const periodo = new URL(req.url, 'http://localhost').searchParams.get('periodo') ?? 'hoy';
    return json(res, 200, {
      periodo,
      fecha_inicio: '2026-08-17',
      fecha_fin: '2026-08-17',
      total_gastos: 450000,
      total_recibido: 3500000,
      por_tipo: [
        { tipo: 'TRANSPORTE', total: 150000, count: 3, naturalezas: { GASTO: 150000 } },
        { tipo: 'MATERIALES', total: 100000, count: 2, naturalezas: { GASTO: 100000 } },
        { tipo: 'PAGO', total: 3500000, count: 12, naturalezas: { RECIBIDO: 3500000 } },
      ],
    });
  }

  // ── W8: GET /api/dashboard/ejecutivo (dashboard:ejecutivo, solo ADMIN) ────
  if (req.method === 'GET' && path === '/api/dashboard/ejecutivo') {
    const token = bearerToken(req);
    const ses = sesionDe(token);
    if (!ses) return json(res, 401, { detail: 'Credencial de sesion requerida' });
    if (!capabilities(ses.rol).includes('dashboard:ejecutivo')) {
      return json(res, 403, { detail: 'No autorizado para dashboard:ejecutivo' });
    }
    return json(res, 200, {
      fecha: '2026-08-17',
      negocio: { nombre: 'Mock Negocio', plan: 'basic', moneda: 'COP' },
      hoy: {
        cartera_vigente: 15000000,
        cartera_vencida: 2500000,
        pct_vencido: 16.7,
        recaudo_hoy: 550000,
        gastos_hoy: 150000,
        neto_hoy: 400000,
      },
      operativo: {
        rutas_activas: 3,
        cobradores_activos: 2,
        creditos_activos: 21,
        jornada_cerrada_hoy: false,
      },
      riesgo: {
        clientes_en_mora: 6,
        promesas_activas: 2,
        promesas_incumplidas: 1,
        aging_distribution: {
          CURRENT: { count: 12, amount: 0 },
          '1-7': { count: 3, amount: 500000 },
          '8-15': { count: 2, amount: 350000 },
          '16-30': { count: 1, amount: 200000 },
          '31-60': { count: 1, amount: 150000 },
          '61-90': { count: 0, amount: 0 },
          '90+': { count: 0, amount: 0 },
        },
      },
      tendencia_7d: {
        serie: [
          { fecha: '2026-08-11', recaudo: 500000, reversal: 50000, neto: 450000 },
          { fecha: '2026-08-12', recaudo: 600000, reversal: 30000, neto: 570000 },
          { fecha: '2026-08-13', recaudo: 450000, reversal: 0, neto: 450000 },
          { fecha: '2026-08-14', recaudo: 700000, reversal: 100000, neto: 600000 },
          { fecha: '2026-08-15', recaudo: 550000, reversal: 20000, neto: 530000 },
          { fecha: '2026-08-16', recaudo: 650000, reversal: 0, neto: 650000 },
          { fecha: '2026-08-17', recaudo: 550000, reversal: 0, neto: 550000 },
        ],
        total_recaudo: 4000000,
        total_reversal: 200000,
        total_neto: 3800000,
      },
      rutas: [
        { ruta_id: 'r1', ruta_nombre: 'Ruta Centro', cartera: 5000000, vencido: 800000, creditos: 8 },
        { ruta_id: 'r2', ruta_nombre: 'Ruta Norte', cartera: 4500000, vencido: 600000, creditos: 6 },
        { ruta_id: 'r3', ruta_nombre: 'Ruta Sur', cartera: 5500000, vencido: 1100000, creditos: 7 },
      ],
      alertas: [
        { tipo: 'JORNADA_ABIERTA', mensaje: 'Hay jornadas sin cerrar hoy', severidad: 'warning' },
        { tipo: 'PROMESAS_INCUMPLIDAS', mensaje: '1 promesa(s) incumplida(s)', severidad: 'warning' },
        { tipo: 'CLIENTES_EN_MORA', mensaje: '6 cliente(s) en mora', severidad: 'info' },
      ],
    });
  }

  // ── POST /api/onboarding/negocios (publico, pre-sesion, Etapa 3) ──────────
  // Replica el contrato real: valida el body (422 con extra=forbid), NIT con
  // conflicto -> 409, y devuelve negocio + admin inicial + codigo bootstrap.
  if (req.method === 'POST' && path === '/api/onboarding/negocios') {
    const errors = validarAlta(body);
    if (errors.length) {
      return json(res, 422, { detail: `Campos invalidos: ${errors.join(', ')}` });
    }
    const out = altaNegocio(body);
    if (out.status === 409) return json(res, 409, { detail: out.detail });
    return json(res, 201, out.body);
  }

  // ── GET /api/dispositivos (Etapa 3, contrato real) ─────────────────────────
  // Replica DispositivoAdminResponse[] y las reglas de dispositivo.py:
  //   - listar es SOLO ADMINISTRADOR (capability `dispositivos:registrar`);
  //     COBRADOR / INVERSIONISTA -> 403 fail-closed (RBAC review)
  //   - 401 sin sesion; el detalle de estado/campos sale de la "DB" del mock
  //   - el DTO devuelto es el admin minimizado (nunca secretos)
  if (req.method === 'GET' && path === '/api/dispositivos') {
    const token = bearerToken(req);
    const sesion = sesionDe(token);
    if (!sesion) return json(res, 401, { detail: 'Unauthorized' });
    if (sesion.dispositivos401) return json(res, 401, { detail: 'Credencial de sesion (Bearer JWT) requerida' });
    if (sesion.error) return json(res, 500, { detail: 'Mock internal error' });
    if (!capabilities(sesion.rol).includes('dispositivos:registrar')) {
      return json(res, 403, { detail: 'Solo ADMINISTRADOR puede listar dispositivos' });
    }
    if (sesion.sinDispositivos) return json(res, 200, []);
    return json(res, 200, listaDispositivos());
  }

  // ── acciones administrativas de dispositivos (SOLO ADMINISTRADOR, 403) ────
  if (req.method === 'POST' && path === '/api/dispositivos') {
    const sesion = sesionDe(bearerToken(req));
    if (!sesion) return json(res, 401, { detail: 'Unauthorized' });
    if (!capabilities(sesion.rol).includes('dispositivos:registrar')) {
      return json(res, 403, { detail: 'Solo ADMINISTRADOR puede registrar dispositivos' });
    }
    return json(res, 201, nuevoDispositivo(body));
  }

  const revocarMatch = path.match(/^\/api\/dispositivos\/([^/]+)\/revocar$/);
  if (req.method === 'POST' && revocarMatch) {
    const sesion = sesionDe(bearerToken(req));
    if (!sesion) return json(res, 401, { detail: 'Unauthorized' });
    if (!capabilities(sesion.rol).includes('dispositivos:registrar')) {
      return json(res, 403, { detail: 'Solo ADMINISTRADOR puede revocar dispositivos' });
    }
    const dev = dispositivosAdmin.get(revocarMatch[1]);
    if (!dev) return json(res, 404, { detail: 'Dispositivo no encontrado' });
    dev.estado = 'REVOKED';
    dev.activo = 0;
    dev.revocado_el = new Date().toISOString();
    return json(res, 200, toAdminDTO(dev));
  }

  const reactivarMatch = path.match(/^\/api\/dispositivos\/([^/]+)\/reactivar$/);
  if (req.method === 'POST' && reactivarMatch) {
    const sesion = sesionDe(bearerToken(req));
    if (!sesion) return json(res, 401, { detail: 'Unauthorized' });
    if (!capabilities(sesion.rol).includes('dispositivos:registrar')) {
      return json(res, 403, { detail: 'Solo ADMINISTRADOR puede reactivar dispositivos' });
    }
    const dev = dispositivosAdmin.get(reactivarMatch[1]);
    if (!dev || dev.estado !== 'REVOKED') return json(res, 404, { detail: 'Dispositivo no encontrado o ya activo' });
    // Invariante: un cobrador solo tiene UN ACTIVE (409, igual que el backend);
    // el camino canonico para renovar su dispositivo es Reemplazar.
    const otroActivo = Array.from(dispositivosAdmin.values()).some(
      (o) => o.id !== dev.id && o.usuario_id && o.usuario_id === dev.usuario_id && o.estado === 'ACTIVE',
    );
    if (otroActivo) return json(res, 409, { detail: 'El cobrador ya tiene un dispositivo ACTIVE; revoque o reemplace antes' });
    dev.estado = 'ACTIVE';
    dev.activo = 1;
    dev.revocado_el = null;
    dev.autorizado_por = sesion.user_id;
    dev.autorizado_el = new Date().toISOString();
    return json(res, 200, toAdminDTO(dev));
  }

  const reemplazarMatch = path.match(/^\/api\/dispositivos\/([^/]+)\/reemplazar$/);
  if (req.method === 'POST' && reemplazarMatch) {
    const sesion = sesionDe(bearerToken(req));
    if (!sesion) return json(res, 401, { detail: 'Unauthorized' });
    if (!capabilities(sesion.rol).includes('dispositivos:registrar')) {
      return json(res, 403, { detail: 'Solo ADMINISTRADOR puede reemplazar dispositivos' });
    }
    const dev = dispositivosAdmin.get(reemplazarMatch[1]);
    if (!dev) return json(res, 404, { detail: 'Dispositivo no encontrado' });
    if (!dev.usuario_id) return json(res, 404, { detail: 'El dispositivo no tiene cobrador asignado para reemplazo' });
    if (dev.estado === 'REPLACED') return json(res, 404, { detail: 'El dispositivo ya fue reemplazado' });
    dev.estado = 'REPLACED';
    dev.activo = 0;
    return json(res, 200, {
      dispositivo: toAdminDTO(dev),
      nuevo_codigo: {
        codigo_id: uuid(),
        token: randomToken(),
        prefijo: 'DS',
        expira_el: rfc3339(Date.now() + 30 * 60 * 1000),
      },
    });
  }

  // ── POST /api/activaciones/codigos (SOLO ADMINISTRADOR, 201) ──────────────
  if (req.method === 'POST' && path === '/api/activaciones/codigos') {
    const sesion = sesionDe(bearerToken(req));
    if (!sesion) return json(res, 401, { detail: 'Unauthorized' });
    if (!capabilities(sesion.rol).includes('codigos:crear')) {
      return json(res, 403, { detail: 'Solo ADMINISTRADOR puede generar codigos de activacion' });
    }
    if (!body.usuario_id) return json(res, 422, { detail: 'usuario_id requerido' });
    return json(res, 201, {
      codigo_id: uuid(),
      token: randomToken(),
      prefijo: 'DS',
      expira_el: rfc3339(Date.now() + 30 * 60 * 1000),
    });
  }
  if (req.method === 'GET' && path === '/api/rutas/resumen') {
    const sesion = sesionDe(bearerToken(req));
    if (!sesion || !(capabilities(sesion.rol).includes('ruta:ver') || capabilities(sesion.rol).includes('rutas:ver'))) {
      return json(res, 403, { detail: 'Forbidden: sin capability de rutas' });
    }
    if (sesion.rol === 'COBRADOR') {
      return json(res, 200, { total_rutas: 1, activas: 1, inactivas: 0, con_cobrador: 1 });
    }
    return json(res, 200, {
      total_rutas: RUTAS_MOCK.length,
      activas: RUTAS_MOCK.filter((r) => r.activa === 1).length,
      inactivas: RUTAS_MOCK.filter((r) => r.activa === 0).length,
      con_cobrador: RUTAS_MOCK.filter((r) => r.cobrador_id).length,
    });
  }
  if (req.method === 'GET' && path === '/api/rutas') {
    const sesion = sesionDe(bearerToken(req));
    if (!sesion || !(capabilities(sesion.rol).includes('ruta:ver') || capabilities(sesion.rol).includes('rutas:ver'))) {
      return json(res, 403, { detail: 'Forbidden: sin capability de rutas' });
    }
    // COBRADOR ve solo su ruta activa (aislamiento igual al backend).
    if (sesion.rol === 'COBRADOR') {
      const ruta = RUTAS_MOCK.find((r) => r.id === sesion.route_id && r.activa === 1);
      if (!ruta) return json(res, 200, { items: [], total: 0, limit: 50, offset: 0 });
      return json(res, 200, { items: [rutaListItem(ruta)], total: 1, limit: 50, offset: 0 });
    }
    const query = new URL(req.url, 'http://localhost').searchParams;
    const q = (query.get('q') || '').toLowerCase().trim();
    const activa = query.get('activa');
    const cobrador_id = query.get('cobrador_id');
    const limit = Math.min(parseInt(query.get('limit') || '50', 10) || 50, 100);
    const offset = parseInt(query.get('offset') || '0', 10) || 0;
    const sort = query.get('sort') || 'nombre';
    const order = (query.get('order') || 'asc').toLowerCase() === 'desc' ? -1 : 1;

    let filas = RUTAS_MOCK.map((r) => rutaListItem(r));
    if (q) filas = filas.filter((r) => (r.nombre || '').toLowerCase().includes(q));
    if (activa === '1' || activa === '0') filas = filas.filter((r) => String(r.activa) === activa);
    if (cobrador_id) filas = filas.filter((r) => r.cobrador_id === cobrador_id);

    const validSorts = new Set(['nombre', 'creado_el', 'version']);
    if (validSorts.has(sort)) {
      filas.sort((a, b) => {
        const va = a[sort] ?? '';
        const vb = b[sort] ?? '';
        if (va < vb) return -1 * order;
        if (va > vb) return 1 * order;
        return 0;
      });
    }

    const total = filas.length;
    const items = filas.slice(offset, offset + limit);
    return json(res, 200, { items, total, limit, offset });
  }
  if (req.method === 'GET' && path.startsWith('/api/rutas/')) {
    const id = decodeURIComponent(path.slice('/api/rutas/'.length));
    const sesion = sesionDe(bearerToken(req));
    if (!sesion || !(capabilities(sesion.rol).includes('ruta:ver') || capabilities(sesion.rol).includes('rutas:ver'))) {
      return json(res, 403, { detail: 'Forbidden: sin capability de rutas' });
    }
    const ruta = RUTAS_MOCK.find((r) => r.id === id);
    if (!ruta) return json(res, 404, { detail: 'Ruta no encontrada' });
    if (sesion.rol === 'COBRADOR' && (ruta.id !== sesion.route_id || ruta.activa !== 1)) {
      return json(res, 404, { detail: 'Ruta no encontrada' });
    }
    return json(res, 200, {
      id: ruta.id,
      nombre: ruta.nombre,
      cobrador_id: ruta.cobrador_id,
      cobrador_nombre: ruta.cobrador_nombre,
      activa: ruta.activa,
      version: ruta.version,
      creado_el: ruta.creado_el,
    });
  }
  if (req.method === 'POST' && path === '/api/rutas') {
    const sesion = sesionDe(bearerToken(req));
    if (!sesion) return json(res, 401, { detail: 'Credencial de sesion requerida' });
    if (!capabilities(sesion.rol).includes('rutas:crear')) {
      return json(res, 403, { detail: 'Solo el administrador puede crear rutas' });
    }
    const nombre = typeof body.nombre === 'string' ? body.nombre.trim() : '';
    if (!nombre) return json(res, 422, { detail: 'nombre es requerido' });
    const duplicado = RUTAS_MOCK.find((r) => r.nombre.toLowerCase() === nombre.toLowerCase() && r.activa === 1);
    if (duplicado) {
      return json(res, 409, { detail: `Ya existe ruta activa '${nombre}'` });
    }
    const cobrador_id = typeof body.cobrador_id === 'string' ? body.cobrador_id : null;
    const cobrador = cobrador_id ? USUARIOS_MOCK.find((u) => u.id === cobrador_id && u.rol === 'COBRADOR') ?? null : null;
    const ruta = {
      id: uuid(),
      nombre,
      cobrador_id: cobrador_id,
      cobrador_nombre: cobrador ? cobrador.nombre : null,
      activa: 1,
      version: 1,
      negocio_id: 'n1',
      creado_el: new Date().toISOString(),
    };
    RUTAS_MOCK.push(ruta);
    return json(res, 201, {
      id: ruta.id,
      nombre: ruta.nombre,
      cobrador_id: ruta.cobrador_id,
      cobrador_nombre: ruta.cobrador_nombre,
      activa: ruta.activa,
      version: ruta.version,
      creado_el: ruta.creado_el,
    });
  }
  if (req.method === 'PATCH' && path.startsWith('/api/rutas/') && path.endsWith('/reasignar')) {
    const id = decodeURIComponent(path.slice('/api/rutas/'.length, -'/reasignar'.length));
    const sesion = sesionDe(bearerToken(req));
    if (!sesion) return json(res, 401, { detail: 'Credencial de sesion requerida' });
    if (!capabilities(sesion.rol).includes('rutas:reasignar')) {
      return json(res, 403, { detail: 'No autorizado para rutas:reasignar' });
    }
    const ruta = RUTAS_MOCK.find((r) => r.id === id);
    if (!ruta) return json(res, 404, { detail: 'Ruta no encontrada' });
    const nombre = typeof body.nombre === 'string' ? body.nombre.trim() : '';
    if (!nombre) return json(res, 422, { detail: 'nombre es requerido' });
    const duplicado = RUTAS_MOCK.find((r) => r.nombre.toLowerCase() === nombre.toLowerCase() && r.activa === 1);
    if (duplicado) {
      return json(res, 409, { detail: `Ya existe ruta activa '${nombre}'` });
    }
    const nuevo = {
      id: uuid(),
      nombre,
      cobrador_id: ruta.cobrador_id,
      cobrador_nombre: ruta.cobrador_nombre,
      activa: 1,
      version: (ruta.version || 1) + 1,
      negocio_id: ruta.negocio_id ?? 'n1',
      creado_el: new Date().toISOString(),
    };
    ruta.activa = 0;
    RUTAS_MOCK.push(nuevo);
    return json(res, 200, {
      ruta_anterior_id: ruta.id,
      ruta_anterior_nombre: ruta.nombre,
      ruta_nueva_id: nuevo.id,
      ruta_nueva_nombre: nuevo.nombre,
      cobrador_id: nuevo.cobrador_id,
      version_asignacion: nuevo.version,
    });
  }
  if (req.method === 'GET' && path === '/api/jornadas') {
    const sesion = sesionDe(bearerToken(req));
    if (!sesion || !(capabilities(sesion.rol).includes('jornada:ver') || capabilities(sesion.rol).includes('jornadas:ver'))) {
      return json(res, 403, { detail: 'Forbidden: sin capability de jornadas' });
    }
    // COBRADOR: jornada abierta de su ruta. Inversionista: solo lectura.
    if (sesion.rol === 'COBRADOR') {
      const hoy = new Date().toISOString().slice(0, 10);
      return json(res, 200, [{ id: 'j1', fecha: hoy, estado: 'OPEN', esperado: 120000, contado: 115000, diferencia: -5000 }]);
    }
    return json(res, 200, []);
  }

   // ── activacion (publico, contrato real) ──────────────────────────────────
  if (req.method === 'POST' && path === '/api/activaciones/desafio') {
    const { token, clave_publica } = body;
    if (!token || !clave_publica) return json(res, 422, { detail: 'token y clave_publica son requeridos' });
    const codigo = ACTIVATION_TOKENS.get(token);
    if (!codigo) return json(res, 404, { detail: 'Codigo de activacion invalido' });
    if (codigo.rol !== 'COBRADOR' && codigo.rol !== 'INVERSIONISTA' && codigo.rol !== 'ADMINISTRADOR') {
      return json(res, 409, { detail: 'Rol del codigo no admitido' });
    }
    try { parseSpki(clave_publica); } catch { return json(res, 400, { detail: 'clave_publica no es SPKI base64 valido' }); }
    const intento_id = uuid();
    const expiraMs = codigo.vencido
      ? Date.now() - 1000
      : Date.now() + 5 * 60 * 1000;
    desafiosActivacion.set(intento_id, {
      spki: clave_publica,
      nonce: randomToken(),
      expira: expiraMs,
      consumed: false,
      environment: 'development',
      // El intento porta la identidad del objetivo (rol, usuario, ruta). El rol
      // nunca se envia por el body publico: el servidor lo deriva del codigo,
      // como el backend en activacion_service._validar_usuario_objetivo.
      rol: codigo.rol,
      usuario_id: codigo.usuario_id,
      negocio_id: codigo.negocio_id,
      ruta_id: codigo.ruta_id ?? null,
      ruta_nombre: codigo.ruta_nombre ?? null,
    });
    const d = desafiosActivacion.get(intento_id);
    return json(res, 200, {
      intento_id,
      nonce: d.nonce,
      expira_el: rfc3339(d.expira),
      environment: d.environment,
    });
  }

  if (req.method === 'POST' && path === '/api/activaciones/canjear') {
    const { intento_id, firma } = body;
    const d = desafiosActivacion.get(intento_id);
    if (!d) return json(res, 404, { detail: 'Intento de activacion invalido' });
    if (!firma) return json(res, 400, { detail: 'firma no es base64url valido' });

    const hash = publicKeyHash(d.spki);
    // Verifica firma ECDSA-DER del payload daily-v1 (contrato real).
    const payload = buildActivacionPayload(d.environment, d.nonce, intento_id, hash, d.expira);
    let ok = false;
    try {
      const verifier = crypto.createVerify('SHA256');
      verifier.update(payload);
      ok = verifier.verify(parseSpki(d.spki), Buffer.from(firma, 'base64url'));
    } catch { ok = false; }

    if (d.consumed) {
      // Idempotencia real del contrato: solo el poseedor de la clave privada
      // del par registrado reobtiene la MISMA credencial; una firma distinta
      // no hereda (replay hostil) y recibe 409.
      if (ok && d.resultado && Date.now() < d.resultado.expira_ms) {
        return json(res, 200, { ...d.resultado.body, idempotente: true });
      }
      return json(res, 409, { detail: 'Intento de activacion ya utilizado' });
    }
    if (Date.now() > d.expira) {
      d.consumed = true;
      return json(res, 410, { detail: 'Intento de activacion vencido' });
    }
    if (!ok) return json(res, 401, { detail: 'Firma invalida: el dispositivo no posee la clave privada del par registrado' });
    d.consumed = true;

    // COBRADOR exige ruta activa única (H3), como el backend. INV/ADMIN no.
    if (d.rol === 'COBRADOR' && !d.ruta_id) {
      return json(res, 401, { detail: 'El cobrador no tiene una ruta activa asignada' });
    }

    const device_id = uuid();
    const credencial = randomToken();
    const body_respuesta = {
      dispositivo_id: device_id,
      negocio_id: d.negocio_id,
      usuario_id: d.usuario_id,
      cobrador_id: d.usuario_id,
      rol: d.rol,
      ruta_id: d.ruta_id ?? null,
      ruta_nombre: d.ruta_nombre ?? null,
      credencial_bootstrap: credencial,
      expira_el: rfc3339(Date.now() + 5 * 60 * 1000),
      idempotente: false,
    };
    d.resultado = { body: body_respuesta, expira_ms: Date.now() + 5 * 60 * 1000 };
    dispositivos.set(device_id, {
      spki: d.spki,
      public_key_hash: hash,
      rol: d.rol,
      usuario_id: d.usuario_id,
      negocio_id: d.negocio_id,
      ruta_id: d.ruta_id ?? null,
      ruta_nombre: d.ruta_nombre ?? null,
    });
    bootstrap.set(credencial, device_id);
    return json(res, 200, body_respuesta);
  }

  // ── sesion (contrato real: exige Bearer y firma valida) ──────────────────
  if (req.method === 'POST' && path === '/api/auth/device/desafio') {
    const credencial = bearerToken(req);
    if (!credencial) return json(res, 401, { detail: 'Credencial de sesion (Bearer JWT o bootstrap) requerida' });
    // Resuelve el dispositivo: JWT de sesión vigente (renovación) o credencial
    // bootstrap emitida en el canje de activación (primer JWT post-activación).
    let device_id;
    const sesion = sesionDe(credencial);
    if (sesion) {
      device_id = sesion.device_id;
    } else {
      device_id = bootstrap.get(credencial);
    }
    if (device_id === undefined || (device_id === null && !sesion)) {
      return json(res, 401, { detail: 'Credencial de sesion invalida' });
    }
    if (device_id === 'mock-device' && !dispositivos.has(device_id)) {
      dispositivos.set(device_id, { spki: null, public_key_hash: 'mock'.padEnd(64, '0'), rol: 'COBRADOR', usuario_id: 'u1', negocio_id: 'n1', ruta_id: 'r1', ruta_nombre: 'Ruta Centro' });
    }
    const challenge_id = uuid();
    const expiraMs = credencial === MOCK_JWT_EXPIRED
      ? Date.now() - 1000
      : Date.now() + 5 * 60 * 1000;
    desafiosSesion.set(challenge_id, {
      nonce: randomToken(),
      expira: expiraMs,
      consumido: false,
      device_id,
      environment: 'development',
    });
    const ch = desafiosSesion.get(challenge_id);
    return json(res, 200, {
      challenge_id,
      nonce: ch.nonce,
      expira_el: rfc3339(ch.expira),
      environment: ch.environment,
    });
  }

  if (req.method === 'POST' && path === '/api/auth/device/canjear') {
    const { challenge_id, firma } = body;
    const ch = desafiosSesion.get(challenge_id);
    if (!ch) return json(res, 404, { detail: 'Desafio de sesion invalido' });
    if (ch.consumido) return json(res, 409, { detail: 'Desafio de sesion ya utilizado (replay)' });
    if (Date.now() > ch.expira) { ch.consumido = true; return json(res, 410, { detail: 'Desafio de sesion vencido' }); }
    const dev = dispositivos.get(ch.device_id);
    if (!dev || !dev.spki) return json(res, 401, { detail: 'Dispositivo sin clave publica registrada' });
    // Verifica firma ECDSA-DER del payload daily-auth-v1.
    const payload = buildAuthPayload(challenge_id, ch.device_id, ch.nonce, ch.expira, ch.environment, dev.public_key_hash);
    let ok = false;
    try {
      const verifier = crypto.createVerify('SHA256');
      verifier.update(payload);
      ok = verifier.verify(parseSpki(dev.spki), Buffer.from(firma, 'base64url'));
    } catch { ok = false; }
    if (!ok) return json(res, 401, { detail: 'Firma invalida: el dispositivo no posee la clave privada del par registrado' });
    ch.consumido = true;
    // Emite un token de sesión POR DISPOSITIVO con forma de JWT (payload lleva
    // device_id como el token real). El rol se deriva de la identidad del
    // dispositivo (como el backend), nunca del token: COBRADOR / INVERSIONISTA /
    // ADMINISTRADOR se separan por capabilities en /me.
    const token = emitSessionToken(ch.device_id, dev);
    SESIONES.set(token, {
      user_id: dev.usuario_id ?? 'u1',
      usuario_nombre: dev.rol === 'ADMINISTRADOR' ? 'Admin Mock' : (dev.rol === 'INVERSIONISTA' ? 'Inversor Test' : 'Cobrador Mock'),
      rol: dev.rol ?? 'COBRADOR',
      device_id: ch.device_id,
      route_id: dev.ruta_id ?? null,
      route_nombre: dev.ruta_nombre ?? null,
    });
    return json(res, 200, {
      token,
      negocio_id: dev.negocio_id ?? 'n1',
      usuario_id: dev.usuario_id ?? 'u1',
      dispositivo_id: ch.device_id,
      version_asignacion: 1,
      expira_el: rfc3339(Date.now() + 24 * 60 * 60 * 1000),
    });
  }

  // ── GET /api/usuarios (listar usuarios del negocio) ─────────────────────────
  if (req.method === 'GET' && path === '/api/usuarios') {
    const token = bearerToken(req);
    const ses = sesionDe(token);
    if (!ses) return json(res, 401, { detail: 'Credencial de sesion requerida' });
    if (ses.rol !== 'ADMINISTRADOR') return json(res, 403, { detail: 'Forbidden' });

    // W1 mock: lista de usuarios por negocio
    const rol = req.url.includes('rol=') ? new URL(req.url, 'http://localhost').searchParams.get('rol') : null;
    const activo = req.url.includes('activo=') ? new URL(req.url, 'http://localhost').searchParams.get('activo') : null;

    const usuariosMock = USUARIOS_MOCK.filter(u => {
      if (u.negocio_id !== 'n1') return false;
      if (rol && u.rol !== rol) return false;
      if (activo !== null && String(u.activo) !== activo) return false;
      return true;
    });

    return json(res, 200, usuariosMock.map(u => ({
      id: u.id,
      rol: u.rol,
      nombre: u.nombre,
      documento: u.documento,
      activo: u.activo,
      creado_el: u.creado_el,
    })));
  }

  // ── POST /api/usuarios (crear usuario) ──────────────────────────────────────
  if (req.method === 'POST' && path === '/api/usuarios') {
    const token = bearerToken(req);
    const ses = sesionDe(token);
    if (!ses) return json(res, 401, { detail: 'Credencial de sesion requerida' });
    if (ses.rol !== 'ADMINISTRADOR') return json(res, 403, { detail: 'Forbidden' });

    const { nombre, rol, documento } = body;
    if (!nombre || typeof nombre !== 'string' || !nombre.trim()) {
      return json(res, 422, { detail: 'nombre es requerido' });
    }
    if (!rol || !['COBRADOR', 'INVERSIONISTA'].includes(rol)) {
      return json(res, 422, { detail: 'rol invalido' });
    }

    const nuevo = {
      id: uuid(),
      negocio_id: 'n1',
      rol,
      nombre: nombre.trim(),
      documento: documento ? String(documento).trim() : null,
      activo: 1,
      creado_el: new Date().toISOString(),
    };
    USUARIOS_MOCK.push(nuevo);
    return json(res, 201, nuevo);
  }

  // ── PATCH /api/usuarios/:id (editar usuario) ────────────────────────────────
  if (req.method === 'PATCH' && path.startsWith('/api/usuarios/') && !path.includes('/estado')) {
    const token = bearerToken(req);
    const ses = sesionDe(token);
    if (!ses) return json(res, 401, { detail: 'Credencial de sesion requerida' });
    if (ses.rol !== 'ADMINISTRADOR') return json(res, 403, { detail: 'Forbidden' });

    const id = path.split('/').pop();
    const u = USUARIOS_MOCK.find(u => u.id === id);
    if (!u) return json(res, 404, { detail: 'Usuario no encontrado' });

    const { nombre, documento } = body;
    if (nombre) u.nombre = nombre.trim();
    if (documento !== undefined) u.documento = documento ? String(documento).trim() : null;

    return json(res, 200, {
      id: u.id,
      negocio_id: u.negocio_id,
      rol: u.rol,
      nombre: u.nombre,
      documento: u.documento,
      activo: u.activo,
      creado_el: u.creado_el,
    });
  }

  // ── PATCH /api/usuarios/:id/estado?activo=0|1 (cambiar estado) ──────────────
  if (req.method === 'PATCH' && path.match(/^\/api\/usuarios\/[^\/]+\/estado$/)) {
    const token = bearerToken(req);
    const ses = sesionDe(token);
    if (!ses) return json(res, 401, { detail: 'Credencial de sesion requerida' });
    if (ses.rol !== 'ADMINISTRADOR') return json(res, 403, { detail: 'Forbidden' });

    const url = new URL(req.url, 'http://localhost');
    const activo = parseInt(url.searchParams.get('activo'), 10);
    if (isNaN(activo) || activo !== 0 && activo !== 1) {
      return json(res, 422, { detail: 'activo debe ser 0 o 1' });
    }

    const parts = path.split('/');
    const id = parts[parts.length - 2];
    const u = USUARIOS_MOCK.find(u => u.id === id);
    if (!u) return json(res, 404, { detail: 'Usuario no encontrado' });
    u.activo = activo;

    return json(res, 200, {
      id: u.id,
      negocio_id: u.negocio_id,
      rol: u.rol,
      nombre: u.nombre,
      documento: u.documento,
      activo: u.activo,
      creado_el: u.creado_el,
    });
  }

  // ── GET /api/audit (logs de auditoria) ──────────────────────────────────────
  if (req.method === 'GET' && path === '/api/audit') {
    const token = bearerToken(req);
    const ses = sesionDe(token);
    if (!ses) return json(res, 401, { detail: 'Credencial de sesion requerida' });
    if (ses.rol !== 'ADMINISTRADOR') return json(res, 403, { detail: 'Forbidden' });

    const url = new URL(req.url, 'http://localhost');
    const action = url.searchParams.get('action');
    const entity_type = url.searchParams.get('entity_type');
    const actor_id = url.searchParams.get('actor_id');
    const limit = Math.min(parseInt(url.searchParams.get('limit') || '50', 10) || 50, 200);

    let logs = AUDIT_MOCK.filter(l => {
      if (l.negocio_id !== 'n1') return false;
      if (action && l.action !== action) return false;
      if (entity_type && l.entity_type !== entity_type) return false;
      if (actor_id && l.actor_id !== actor_id) return false;
      return true;
    });

    // Orden: mas reciente primero
    logs.sort((a, b) => new Date(b.creado_el).getTime() - new Date(a.creado_el).getTime());
    logs = logs.slice(0, limit);

    // Read model: incluir actor_nombre (LEFT JOIN simulado)
    const result = logs.map(l => {
      const actor = USUARIOS_MOCK.find(u => u.id === l.actor_id);
      return {
        id: l.id,
        negocio_id: l.negocio_id,
        actor_id: l.actor_id,
        actor_nombre: actor ? actor.nombre : null,
        action: l.action,
        entity_type: l.entity_type,
        entity_id: l.entity_id,
        metadata: l.metadata,
        ip_address: l.ip_address,
        user_agent: l.user_agent,
        creado_el: l.creado_el,
      };
    });

    return json(res, 200, result);
  }

  // ── POST /api/activaciones/codigos (generar codigo de activacion) ────────────
  // (ya existe en mock-api.mjs desde linea ~595, verificar que no duplique)

  // ── W2: GET /api/clientes (listar clientes del negocio, paginado) ──────────
  if (req.method === 'GET' && path === '/api/clientes') {
    const token = bearerToken(req);
    const ses = sesionDe(token);
    if (!ses) return json(res, 401, { detail: 'Credencial de sesion requerida' });
    if (!capabilities(ses.rol).includes('clientes:ver')) {
      return json(res, 403, { detail: 'No autorizado para clientes:ver' });
    }

    const query = new URL(req.url, 'http://localhost').searchParams;
    const q = query.get('q');
    const tipo_documento = query.get('tipo_documento');
    const identity_status = query.get('identity_status');
    const limit = Math.min(parseInt(query.get('limit') || '50', 10) || 50, 100);
    const offset = parseInt(query.get('offset') || '0', 10) || 0;

    // COBRADOR: scoped a su ruta (aislamiento derivado via Credito, como el backend).
    const esCobrador = ses.rol === 'COBRADOR';

    const norm = (s) => (s || '').toLowerCase();
    let items = CLIENTES_MOCK.filter((c) => {
      if (c.negocio_id !== 'n1') return false;
      if (esCobrador && !clienteEnRuta(c, ses.route_id)) return false;
      if (tipo_documento && c.tipo_documento !== tipo_documento) return false;
      if (identity_status && c.identity_status !== identity_status) return false;
      if (q) {
        const doc = `${c.tipo_documento ?? ''} ${c.documento_normalizado ?? ''}`.toLowerCase();
        const nombre = norm([c.nombres, c.primer_apellido, c.segundo_apellido].filter(Boolean).join(' '));
        const tel = norm(c.telefono_1);
        if (!nombre.includes(norm(q)) && !doc.includes(norm(q)) && !tel.includes(norm(q))) return false;
      }
      return true;
    });

    const total = items.length;
    items = items.slice(offset, offset + limit);
    return json(res, 200, {
      items: items.map(clienteListDTO),
      total,
      limit,
      offset,
    });
  }

  // ── W2: POST /api/clientes (crear cliente, clientes:gestionar) ─────────────
  if (req.method === 'POST' && path === '/api/clientes') {
    const token = bearerToken(req);
    const ses = sesionDe(token);
    if (!ses) return json(res, 401, { detail: 'Credencial de sesion requerida' });
    if (!capabilities(ses.rol).includes('clientes:gestionar')) {
      return json(res, 403, { detail: 'No autorizado para clientes:gestionar' });
    }

    const trim = (v) => (typeof v === 'string' ? v.trim() || null : null);
    if (!body.primer_apellido || typeof body.primer_apellido !== 'string' || !body.primer_apellido.trim()) {
      return json(res, 422, { detail: 'primer_apellido es requerido' });
    }
    if (!body.nombres || typeof body.nombres !== 'string' || !body.nombres.trim()) {
      return json(res, 422, { detail: 'nombres es requerido' });
    }
    // extra=forbid: la identidad no se define por el cliente.
    const permitidos = new Set([
      'primer_apellido', 'segundo_apellido', 'nombres', 'tipo_documento',
      'documento_normalizado', 'telefono_1', 'telefono_2', 'direccion',
      'barrio', 'ciudad', 'ocupacion',
    ]);
    for (const k of Object.keys(body)) if (!permitidos.has(k)) {
      return json(res, 422, { detail: `Campo no permitido: ${k}` });
    }

    const nuevo = {
      id: uuid(),
      negocio_id: 'n1',
      tipo_documento: trim(body.tipo_documento),
      documento_normalizado: trim(body.documento_normalizado),
      identity_status: 'PROVISIONAL',
      primer_apellido: body.primer_apellido.trim(),
      segundo_apellido: trim(body.segundo_apellido),
      nombres: body.nombres.trim(),
      telefono_1: trim(body.telefono_1),
      telefono_2: trim(body.telefono_2),
      direccion: trim(body.direccion),
      barrio: trim(body.barrio),
      ciudad: trim(body.ciudad),
      ocupacion: trim(body.ocupacion),
      creado_el: new Date().toISOString(),
      creditos: [],
      pagos: [],
    };
    CLIENTES_MOCK.push(nuevo);
    return json(res, 201, clienteResponseDTO(nuevo));
  }

  // ── W2: GET /api/clientes/:id (Cliente 360, clientes:ver) ──────────────────
  if (req.method === 'GET' && path.startsWith('/api/clientes/')) {
    const token = bearerToken(req);
    const ses = sesionDe(token);
    if (!ses) return json(res, 401, { detail: 'Credencial de sesion requerida' });
    if (!capabilities(ses.rol).includes('clientes:ver')) {
      return json(res, 403, { detail: 'No autorizado para clientes:ver' });
    }

    const id = path.split('/').pop();
    const c = CLIENTES_MOCK.find((x) => x.id === id && x.negocio_id === 'n1');
    if (!c) return json(res, 404, { detail: 'Cliente no encontrado' });
    // COBRADOR: 404 si el cliente no esta en su ruta (mismo contrato que el backend).
    if (ses.rol === 'COBRADOR' && !clienteEnRuta(c, ses.route_id)) {
      return json(res, 404, { detail: 'Cliente no encontrado' });
    }
    return json(res, 200, cliente360DTO(c));
  }

  // ── W2: PATCH /api/clientes/:id (editar cliente, clientes:gestionar) ───────
  if (req.method === 'PATCH' && path.startsWith('/api/clientes/')) {
    const token = bearerToken(req);
    const ses = sesionDe(token);
    if (!ses) return json(res, 401, { detail: 'Credencial de sesion requerida' });
    if (!capabilities(ses.rol).includes('clientes:gestionar')) {
      return json(res, 403, { detail: 'No autorizado para clientes:gestionar' });
    }

    const id = path.split('/').pop();
    const c = CLIENTES_MOCK.find((x) => x.id === id && x.negocio_id === 'n1');
    if (!c) return json(res, 404, { detail: 'Cliente no encontrado' });

    // extra=forbid: identidad (tipo_documento/documento_normalizado/identity_status) NO es editable.
    const editables = new Set([
      'primer_apellido', 'segundo_apellido', 'nombres', 'telefono_1',
      'telefono_2', 'direccion', 'barrio', 'ciudad', 'ocupacion',
    ]);
    for (const k of Object.keys(body)) if (!editables.has(k)) {
      return json(res, 422, { detail: `Campo no editable: ${k}` });
    }

    const trim = (v) => (typeof v === 'string' ? v.trim() || null : null);
    if (body.primer_apellido !== undefined) c.primer_apellido = trim(body.primer_apellido);
    if (body.segundo_apellido !== undefined) c.segundo_apellido = trim(body.segundo_apellido);
    if (body.nombres !== undefined) c.nombres = trim(body.nombres);
    if (body.telefono_1 !== undefined) c.telefono_1 = trim(body.telefono_1);
    if (body.telefono_2 !== undefined) c.telefono_2 = trim(body.telefono_2);
    if (body.direccion !== undefined) c.direccion = trim(body.direccion);
    if (body.barrio !== undefined) c.barrio = trim(body.barrio);
    if (body.ciudad !== undefined) c.ciudad = trim(body.ciudad);
    if (body.ocupacion !== undefined) c.ocupacion = trim(body.ocupacion);

    return json(res, 200, clienteResponseDTO(c));
  }

  return json(res, 404, { detail: 'Not found in mock API' });
});

// ─── JCS canonicalization (replica del contrato, ver jcs.dart) ─────────────
function rfc3339(ms) {
  return new Date(ms).toISOString().replace(/\.\d+Z$/, 'Z');
}
function jcsStringify(value) {
  let out = '"';
  for (const ch of value) {
    const code = ch.codePointAt(0);
    if (code === 0x22) out += '\\"';
    else if (code === 0x5c) out += '\\\\';
    else if (code === 0x08) out += '\\b';
    else if (code === 0x09) out += '\\t';
    else if (code === 0x0a) out += '\\n';
    else if (code === 0x0c) out += '\\f';
    else if (code === 0x0d) out += '\\r';
    else if (code <= 0x1f) out += `\\u00${code.toString(16).padStart(2, '0')}`;
    else out += ch;
  }
  return out + '"';
}
function jcs(obj) {
  const keys = Object.keys(obj).sort((a, b) => {
    for (let i = 0; i < Math.min(a.length, b.length); i++) {
      const ca = a.charCodeAt(i), cb = b.charCodeAt(i);
      if (ca !== cb) return ca < cb ? -1 : 1;
    }
    return a.length - b.length;
  });
  const parts = keys.map((k) => `${jcsStringify(k)}:${jcsStringify(String(obj[k]))}`);
  return `{${parts.join(',')}}`;
}
function buildActivacionPayload(env, nonce, attemptId, hash, expiraMs) {
  return jcs({
    protocol_version: 'daily-v1',
    environment: env,
    attempt_id: attemptId,
    nonce,
    public_key_hash: hash,
    expires_at: rfc3339(expiraMs),
  });
}
function buildAuthPayload(challengeId, deviceId, nonce, expiraMs, env, publicKeyHash) {
  return jcs({
    protocol_version: 'daily-auth-v1',
    purpose: 'issue_access_token',
    environment: env,
    challenge_id: challengeId,
    device_id: deviceId,
    nonce,
    public_key_hash: publicKeyHash,
    expires_at: rfc3339(expiraMs),
  });
}

const port = Number(process.env.MOCK_API_PORT || 8000);
seedDispositivosAdmin();
seedOnboarding();
server.listen(port, () => console.log(`[mock-api] listening on :${port}`));