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
// device_id -> { spki, public_key_hash }
const dispositivos = new Map();
// codigo -> device_id (bootstrap emitido)
const bootstrap = new Map();

// codigo de activacion valido para E2E (emitido por "el administrador")
const ACTIVATION_TOKENS = new Map([
  ['test-activation-code', { cobrador_id: 'c1', negocio_id: 'n1' }],
  // codigo que emite un desafio YA vencido, para probar el 410 del contrato
  ['test-expired-code', { cobrador_id: 'c1', negocio_id: 'n1' }],
]);

// JWT de sesion "valido" emitido por este mock (para renovacion)
const MOCK_JWT = 'mock-jwt-token';
// Credencial que hace que el desafio de sesion nazca vencido (prueba 410).
const MOCK_JWT_EXPIRED = 'mock-jwt-expired';

// ─── RBAC (replica fiel de src/rbac.py) ─────────────────────────────────────
// El mock NO es permisivo: deriva el rol del token y aplica las mismas reglas
// que el backend. El flujo de dispositivo (daily-v1 / daily-auth-v1) SOLO
// emite COBRADOR (canjear_desafio del backend), igual que el contrato real.
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

// "DB" del mock: token de sesion -> identidad (rol derivado, nunca del JWT).
const SESIONES = new Map([
  ['test-token', { user_id: 'u_inv', usuario_nombre: 'Inversor Test', rol: 'INVERSIONISTA' }],
  ['mock-custom', { user_id: 'u_inv', usuario_nombre: 'Inversor Test', rol: 'INVERSIONISTA' }],
  ['mock-empty', { user_id: 'u_inv', usuario_nombre: 'Inversor Test', rol: 'INVERSIONISTA' }],
  ['mock-error', { user_id: 'u_inv', usuario_nombre: 'Inversor Test', rol: 'INVERSIONISTA' }],
  // Token emitido por el flujo de dispositivo: SIEMPRE COBRADOR (contrato real).
  [MOCK_JWT, { user_id: 'u1', usuario_nombre: 'Cobrador Mock', rol: 'COBRADOR', route_id: 'r1', route_nombre: 'Ruta Centro' }],
  // Token ADMINISTRADOR para evidenciar la separación RBAC por rol en E2E.
  // Solo el backend emite tokens con rol; aquí se simula la identidad que el
  // backend derivaría de la DB para un usuario administrador del negocio.
  ['mock-admin', { user_id: 'u_admin', usuario_nombre: 'Admin Mock', rol: 'ADMINISTRADOR' }],
]);

function sesionDe(token) {
  return SESIONES.get(token) ?? null;
}

function randomToken() {
  return crypto.randomBytes(32).toString('base64url');
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
      device_id: sesion.rol === 'COBRADOR' ? 'mock-device' : null,
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
    if (!ACTIVATION_TOKENS.has(token)) return json(res, 404, { detail: 'Codigo de activacion invalido' });
    try { parseSpki(clave_publica); } catch { return json(res, 400, { detail: 'clave_publica no es SPKI base64 valido' }); }
    const intento_id = uuid();
    const expiraMs = ACTIVATION_TOKENS.has(token) && token === 'test-expired-code'
      ? Date.now() - 1000
      : Date.now() + 5 * 60 * 1000;
    desafiosActivacion.set(intento_id, {
      spki: clave_publica,
      nonce: randomToken(),
      expira: expiraMs,
      consumed: false,
      environment: 'development',
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

    const device_id = uuid();
    const credencial = randomToken();
    const body_respuesta = {
      dispositivo_id: device_id,
      negocio_id: 'n1',
      cobrador_id: 'c1',
      credencial_bootstrap: credencial,
      expira_el: rfc3339(Date.now() + 5 * 60 * 1000),
      idempotente: false,
    };
    d.resultado = { body: body_respuesta, expira_ms: Date.now() + 5 * 60 * 1000 };
    dispositivos.set(device_id, { spki: d.spki, public_key_hash: hash });
    bootstrap.set(credencial, device_id);
    return json(res, 200, body_respuesta);
  }

  // ── sesion (contrato real: exige Bearer y firma valida) ──────────────────
  if (req.method === 'POST' && path === '/api/auth/device/desafio') {
    const credencial = bearerToken(req);
    if (!credencial) return json(res, 401, { detail: 'Credencial de sesion (Bearer JWT o bootstrap) requerida' });
    // Acepta JWT mock (renovacion) o un bootstrap emitido por este mock.
    let device_id;
    if (credencial === MOCK_JWT || credencial === MOCK_JWT_EXPIRED) {
      device_id = 'mock-device';
      if (!dispositivos.has(device_id)) dispositivos.set(device_id, { spki: null, public_key_hash: 'mock'.padEnd(64, '0') });
    } else {
      device_id = bootstrap.get(credencial);
      if (!device_id) return json(res, 401, { detail: 'Credencial de sesion invalida' });
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
    return json(res, 200, {
      token: MOCK_JWT,
      negocio_id: 'n1',
      usuario_id: 'u1',
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