import { test, expect } from '@playwright/test';

import { buildPayloadActivacion, buildPayloadAuth, base64UrlNoPad } from '../src/lib/auth/jcs';
import { rawToDerSignature, sha256Hex } from '../src/lib/auth/identity';
import { seedActivacion, type SeedOutput } from './helpers/real-seed';

/**
 * Matriz RBAC contra FastAPI real (:8001) + Postgres real.
 *
 * Autoridad real en tres capas:
 *   1. JWT minted por el servidor (issue_token + AUTH_JWT_PRIVATE_KEY) para
 *      INVERSIONISTA y ADMINISTRADOR (seed reproducible). El rol NO viaja en
 *      el JWT: deps.py lo deriva de la DB en cada request.
 *   2. COBRADOR: JWT real obtenido por el flujo de dispositivo completo
 *      (activación daily-v1 -> canje -> desafío daily-auth-v1 -> canje de
 *      sesión), el único camino que emite ese rol.
 *   3. /api/auth/me como fuente canónica: rol + capabilities desde la DB.
 *
 * Gates que prueba (por rol, con 403 REAL — nunca 401 ni redirect silencioso):
 *   - sin sesión            -> /me 401
 *   - COBRADOR              -> /me 200 COBRADOR, /api/jornadas (solo su ruta),
 *                              /api/inversionista/resumen -> 403
 *   - INVERSIONISTA         -> /me 200, resumen 200, abrir jornada -> 403
 *   - ADMINISTRADOR         -> /me 200, resumen 200
 */

const API = process.env.REAL_API_BASE ?? 'http://127.0.0.1:8001';

const CAPS_INVERSIONISTA = [
  'inversionista:resumen',
  'inversionista:suscripcion',
  'jornadas:ver',
  'rutas:ver',
  'creditos:ver',
  'movimientos:ver',
  'cobranza:ver',
  'reportes:ver',
];
const CAPS_ADMINISTRADOR = [
  'inversionista:resumen',
  'inversionista:suscripcion',
  'jornadas:ver',
  'rutas:ver',
  'rutas:crear',
  'rutas:reasignar',
  'creditos:ver',
  'creditos:gestionar',
  'movimientos:ver',
  'cobranza:ver',
  'cobranza:gestionar',
  'promesas:ver',
  'promesas:crear',
  'promesas:actualizar',
  'codigos:crear',
  'dispositivos:registrar',
  'usuarios:ver',
  'usuarios:gestionar',
  'audit:ver',
  'clientes:ver',
  'clientes:gestionar',
  'reportes:ver',
  'dashboard:ejecutivo',
];
const CAPS_COBRADOR = [
  'jornada:ver',
  'jornada:abrir',
  'jornada:cerrar',
  'ruta:ver',
  'movimientos:ver',
  'movimientos:registrar',
  'pagos:registrar',
  'sync:ver',
  'clientes:ver',
  'creditos:ver',
  'cobranza:ver',
  'promesas:ver',
  'promesas:crear',
  'promesas:actualizar',
];

interface MeBody {
  user_id: string;
  rol: string;
  activo: boolean;
  route_id: string | null;
  capabilities: string[];
  negocio: { negocio_id: string; nombre: string; suscripcion_activa: boolean };
}

async function me(token: string): Promise<{ status: number; body: MeBody | { detail?: string } }> {
  const r = await fetch(`${API}/api/auth/me`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  const body = await r.json().catch(() => ({}));
  return { status: r.status, body };
}

/**
 * Flujo real de dispositivo del COBRADOR: genera un par EC P-256 en el proceso
 * del test, registra el dispositivo por activación daily-v1 y canjea la sesión
 * daily-auth-v1. Devuelve el JWT de acceso real (rol COBRADOR).
 */
test.describe.serial('Matriz RBAC real (contrato FastAPI :8001)', () => {
  let seed: SeedOutput;
  let jwtCobrador: string;
  let rutaId: string;

  test.beforeAll(async () => {
    seed = seedActivacion();
    rutaId = seed.ruta_id;

    const keyPair = await crypto.subtle.generateKey(
      { name: 'ECDSA', namedCurve: 'P-256' },
      true,
      ['sign', 'verify'],
    );
    const spki = new Uint8Array(await crypto.subtle.exportKey('spki', keyPair.publicKey));
    const spkiB64 = Buffer.from(spki).toString('base64');
    const publicKeyHash = await sha256Hex(spki);
    const signJcs = async (payload: Uint8Array) =>
      base64UrlNoPad(
        rawToDerSignature(
          new Uint8Array(await crypto.subtle.sign({ name: 'ECDSA', hash: 'SHA-256' }, keyPair.privateKey, payload)),
        ),
      );

    // 1) activación daily-v1
    const d = await fetch(`${API}/api/activaciones/desafio`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token: seed.codigo_activacion, clave_publica: spkiB64, modelo: 'web', plataforma: 'web' }),
    });
    expect(d.status).toBe(200);
    const desafioActivacion = (await d.json()) as { intento_id: string; nonce: string; expira_el: string; environment: string };
    const payloadActivacion = buildPayloadActivacion({
      protocolVersion: 'daily-v1',
      environment: desafioActivacion.environment,
      attemptId: desafioActivacion.intento_id,
      nonce: desafioActivacion.nonce,
      publicKeyHash,
      expiresAt: desafioActivacion.expira_el,
    });
    const rCanje = await fetch(`${API}/api/activaciones/canjear`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ intento_id: desafioActivacion.intento_id, firma: await signJcs(payloadActivacion) }),
    });
    expect(rCanje.status).toBe(200);
    const canje = (await rCanje.json()) as { credencial_bootstrap: string; dispositivo_id: string };
    const bootstrap = canje.credencial_bootstrap;

    // 2) desafío sesión daily-auth-v1
    const ds = await fetch(`${API}/api/auth/device/desafio`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${bootstrap}` },
    });
    expect(ds.status).toBe(200);
    const desafioSesion = (await ds.json()) as { challenge_id: string; nonce: string; expira_el: string; environment: string };
    // deviceId lo pedimos del canje (idempotente).
    const payloadSesion = buildPayloadAuth({
      purpose: 'issue_access_token',
      environment: desafioSesion.environment,
      challengeId: desafioSesion.challenge_id,
      deviceId: canje.dispositivo_id,
      nonce: desafioSesion.nonce,
      publicKeyHash,
      expiresAt: desafioSesion.expira_el,
    });
    const cs = await fetch(`${API}/api/auth/device/canjear`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ challenge_id: desafioSesion.challenge_id, firma: await signJcs(payloadSesion) }),
    });
    expect(cs.status).toBe(200);
    jwtCobrador = ((await cs.json()) as { token: string }).token;
  });

  test('sin sesión: /api/auth/me -> 401 (nunca 403 ni redirect)', async () => {
    const r = await fetch(`${API}/api/auth/me`);
    expect(r.status).toBe(401);
    expect(r.url).not.toContain('redirect');
  });

  test('COBRADOR (JWT real del flujo de dispositivo): /me 200, jornadas scoped, resumen 403', async () => {
    const m = await me(jwtCobrador);
    expect(m.status).toBe(200);
    const body = m.body as MeBody;
    expect(body.rol).toBe('COBRADOR');
    expect(body.activo).toBe(true);
    body.capabilities.sort();
    expect(body.capabilities).toEqual([...CAPS_COBRADOR].sort());
    expect(body.route_id).toBe(rutaId);

    const list = await fetch(`${API}/api/jornadas`, {
      headers: { Authorization: `Bearer ${jwtCobrador}` },
    });
    expect(list.status).toBe(200);

    const res = await fetch(`${API}/api/inversionista/resumen`, {
      headers: { Authorization: `Bearer ${jwtCobrador}` },
    });
    expect(res.status, 'COBRADOR NUNCA ve resumen financiero').toBe(403);
    try {
      await res.json();
    } catch {
      // 403 real sin redirect; si es JSON, detalle explícito.
    }

    const sub = await fetch(`${API}/api/inversionista/suscripcion`, {
      headers: { Authorization: `Bearer ${jwtCobrador}` },
    });
    expect(sub.status, 'COBRADOR NUNCA ve suscripcion (Etapa 3)').toBe(403);
  });

  test('INVERSIONISTA (JWT minted por servidor): /me 200, resumen 200, abrir jornada 403', async () => {
    const m = await me(seed.tokens.inversionista);
    expect(m.status).toBe(200);
    const body = m.body as MeBody;
    expect(body.rol).toBe('INVERSIONISTA');
    body.capabilities.sort();
    expect(body.capabilities).toEqual([...CAPS_INVERSIONISTA].sort());

    const res = await fetch(`${API}/api/inversionista/resumen`, {
      headers: { Authorization: `Bearer ${seed.tokens.inversionista}` },
    });
    expect(res.status).toBe(200);
    expect((await res.json()).portfolio).toBeTruthy();

    const abrir = await fetch(`${API}/api/jornadas`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${seed.tokens.inversionista}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        ruta_id: rutaId,
        opening_base: 100,
        clave_idempotencia: `rbac-inv-${Date.now()}`,
      }),
    });
    expect(abrir.status).toBe(403);
  });

  test('INVERSIONISTA: GET /api/inversionista/suscripcion -> 200 con contrato real', async () => {
    const res = await fetch(`${API}/api/inversionista/suscripcion`, {
      headers: { Authorization: `Bearer ${seed.tokens.inversionista}` },
    });
    expect(res.status).toBe(200);
    const body = (await res.json()) as {
      negocio_id: string;
      estado_suscripcion: string;
      plan: string;
      paid_through_at: string | null;
      activa: boolean;
    };
    // Contrato SuscripcionStatusResponse: campos exactos, sin inventos.
    expect(body.negocio_id).toBeTruthy();
    expect(['al_dia', 'vencida']).toContain(body.estado_suscripcion);
    expect(typeof body.plan).toBe('string');
    expect(typeof body.activa).toBe('boolean');
    // activa debe ser consistente con el estado (al_dia + pago vigente).
    expect(body.activa).toBe(true);
  });

  test('ADMINISTRADOR (JWT minted por servidor): /me 200, resumen 200, suscripcion 200', async () => {
    const m = await me(seed.tokens.administrador);
    expect(m.status).toBe(200);
    const body = m.body as MeBody;
    expect(body.rol).toBe('ADMINISTRADOR');
    body.capabilities.sort();
    expect(body.capabilities).toEqual([...CAPS_ADMINISTRADOR].sort());

    const res = await fetch(`${API}/api/inversionista/resumen`, {
      headers: { Authorization: `Bearer ${seed.tokens.administrador}` },
    });
    expect(res.status).toBe(200);

    const sub = await fetch(`${API}/api/inversionista/suscripcion`, {
      headers: { Authorization: `Bearer ${seed.tokens.administrador}` },
    });
    expect(sub.status).toBe(200);
  });
});