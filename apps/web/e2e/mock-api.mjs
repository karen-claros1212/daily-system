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
    'ruta:ver', 'movimientos:registrar', 'pagos:registrar', 'sync:ver',
  ],
  INVERSIONISTA: [
    'inversionista:resumen', 'inversionista:suscripcion',
    'jornadas:ver', 'rutas:ver', 'creditos:ver',
  ],
  ADMINISTRADOR: [
    'inversionista:resumen', 'inversionista:suscripcion',
    'jornadas:ver', 'rutas:ver', 'rutas:crear', 'rutas:reasignar',
    'creditos:ver', 'codigos:crear', 'dispositivos:registrar',
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

function parseSpki(spkiBase64) {
  return crypto.createPublicKey({
    key: Buffer.from(spkiBase64, 'base64'),
    format: 'der',
    type: 'spki',
  });
}

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
  if (req.method === 'GET' && path === '/api/rutas') {
    const sesion = sesionDe(bearerToken(req));
    if (!sesion || !(capabilities(sesion.rol).includes('ruta:ver') || capabilities(sesion.rol).includes('rutas:ver'))) {
      return json(res, 403, { detail: 'Forbidden: sin capability de rutas' });
    }
    // COBRADOR ve solo la ruta de SU asignacion (como el backend, que filtra
    // por el ctx del dispositivo); inversionista/admin ven la de negocio.
    if (sesion.rol === 'COBRADOR') {
      if (!sesion.route_id) return json(res, 200, []);
      return json(res, 200, [{ id: sesion.route_id, nombre: sesion.route_nombre, cobrador_nombre: sesion.usuario_nombre, activa: true, version: 1 }]);
    }
    return json(res, 200, [
      { id: 'r1', nombre: 'Ruta Norte', cobrador_nombre: 'Carlos M.', activa: true, version: 1 },
      { id: 'r2', nombre: 'Ruta Sur', cobrador_nombre: 'Ana P.', activa: false, version: 2 },
    ]);
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
server.listen(port, () => console.log(`[mock-api] listening on :${port}`));