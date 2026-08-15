import { test, expect } from '@playwright/test';

import { buildPayloadActivacion, buildPayloadAuth, base64UrlNoPad } from '../src/lib/auth/jcs';
import { rawToDerSignature, sha256Hex } from '../src/lib/auth/identity';
import { seedActivacion, runSql, type SeedOutput } from './helpers/real-seed';

/**
 * Dispositivos Autorizados contra FastAPI real (:8001) + Postgres real.
 *
 * Autoridad real en dos capas:
 *   1. ADMINISTRADOR / INVERSIONISTA: JWT minted por el servidor (seed
 *      reproducible con AUTH_JWT_PRIVATE_KEY). El rol se deriva de la DB.
 *   2. COBRADOR: JWT real por el flujo de dispositivo completo
 *      (activación daily-v1 -> canje -> desafío daily-auth-v1 -> canje de
 *      sesión), que además CREA el Dispositivo ACTIVE real del cobrador.
 *
 * Casos del review (A–G), todos contra el contrato real, sin manipular
 * respuestas ni debilitar `_puede_crear_dispositivo`:
 *   A  GET list (ADMIN) -> 200, DTO admin minimizado (sin secretos/tenancy)
 *   B  GET list (COBRADOR) -> 403 fail-closed
 *   C  GET list (INVERSIONISTA) -> 403 fail-closed
 *   D  revocar (ADMIN) -> 200 y el GET posterior persiste REVOKED
 *   E  reactivar (ADMIN) -> 200 (autorizado por el admin que ejecuta)
 *   F  reactivar con otro ACTIVE del mismo cobrador -> 409 (invariante)
 *   G  reemplazar (ADMIN) -> viejo REPLACED + código nuevo -> canje real
 *      -> el dispositivo nuevo nace ACTIVE
 */

const API = process.env.REAL_API_BASE ?? 'http://127.0.0.1:8001';

interface DispositivoAdminBody {
  id: string;
  usuario_id: string | null;
  estado: string;
  modelo: string | null;
  plataforma: string | null;
  autorizado_el: string | null;
  revocado_el: string | null;
  ultima_validacion_servidor: string | null;
  activo: number;
  creado_el: string | null;
}

const CAMPOS_NO_ADMIN = [
  'huella',
  'public_key_hash',
  'algoritmo_clave',
  'negocio_id',
  'autorizado_por',
] as const;

/** Activa un código (desafío + canje reales) con un par EC fresco. */
async function canjearCodigo(token: string): Promise<{ dispositivo_id: string }> {
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

  const d = await fetch(`${API}/api/activaciones/desafio`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ token, clave_publica: spkiB64, modelo: 'web', plataforma: 'web' }),
  });
  const dText = await d.text();
  expect(d.status, `desafio del codigo: ${dText}`).toBe(200);
  const desafioActivacion = JSON.parse(dText) as {
    intento_id: string;
    nonce: string;
    expira_el: string;
    environment: string;
  };
  const payloadActivacion = buildPayloadActivacion({
    protocolVersion: 'daily-v1',
    environment: desafioActivacion.environment,
    attemptId: desafioActivacion.intento_id,
    nonce: desafioActivacion.nonce,
    publicKeyHash,
    expiresAt: desafioActivacion.expira_el,
  });
  const rc = await fetch(`${API}/api/activaciones/canjear`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ intento_id: desafioActivacion.intento_id, firma: await signJcs(payloadActivacion) }),
  });
  const rcText = await rc.text();
  expect(rc.status, `canje del codigo: ${rcText}`).toBe(200);
  return JSON.parse(rcText) as { dispositivo_id: string };
}

test.describe.serial('Dispositivos autorizados (FastAPI real :8001)', () => {
  let seed: SeedOutput;
  let dCobradorId: string;
  let jwtCobrador: string;
  let jwtAdmin: string;
  let jwtInv: string;

  test.beforeAll(async () => {
    seed = seedActivacion();
    jwtAdmin = seed.tokens.administrador;
    jwtInv = seed.tokens.inversionista;

    // Flujo de dispositivo completo del COBRADOR (crea su Dispositivo ACTIVE).
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

    const d = await fetch(`${API}/api/activaciones/desafio`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token: seed.codigo_activacion, clave_publica: spkiB64, modelo: 'web', plataforma: 'web' }),
    });
    expect(d.status).toBe(200);
    const desafioActivacion = (await d.json()) as {
      intento_id: string;
      nonce: string;
      expira_el: string;
      environment: string;
    };
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
    dCobradorId = canje.dispositivo_id;
    const bootstrap = canje.credencial_bootstrap;

    const ds = await fetch(`${API}/api/auth/device/desafio`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${bootstrap}` },
    });
    expect(ds.status).toBe(200);
    const desafioSesion = (await ds.json()) as {
      challenge_id: string;
      nonce: string;
      expira_el: string;
      environment: string;
    };
    const payloadSesion = buildPayloadAuth({
      purpose: 'issue_access_token',
      environment: desafioSesion.environment,
      challengeId: desafioSesion.challenge_id,
      deviceId: dCobradorId,
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

  async function listar(rol: 'admin' | 'cobrador' | 'inversionista') {
    const token = rol === 'admin' ? jwtAdmin : rol === 'cobrador' ? jwtCobrador : jwtInv;
    return fetch(`${API}/api/dispositivos`, {
      headers: { Authorization: `Bearer ${token}` },
    });
  }

  async function dispositivoEnLista(devId: string): Promise<DispositivoAdminBody> {
    const r = await listar('admin');
    expect(r.status).toBe(200);
    const body = (await r.json()) as DispositivoAdminBody[];
    const dev = body.find((d) => d.id === devId);
    expect(dev, `dispositivo ${devId} debe estar en el listado`).toBeTruthy();
    return dev!;
  }

  test('A: ADMINISTRADOR lista con DTO minimizado (sin secretos ni tenancy) y el dispositivo del cobrador', async () => {
    const r = await listar('admin');
    expect(r.status).toBe(200);
    const body = (await r.json()) as DispositivoAdminBody[];
    expect(Array.isArray(body)).toBe(true);
    expect(body.length, 'el listado real no debe estar vacio').toBeGreaterThan(0);
    for (const dev of body) {
      for (const campo of CAMPOS_NO_ADMIN) {
        expect(dev, `DTO admin real no expone ${campo}`).not.toHaveProperty(campo);
      }
    }
    const dev = body.find((d) => d.id === dCobradorId);
    expect(dev, 'el dispositivo del cobrador nace del canje real').toBeTruthy();
    expect(dev!.estado).toBe('ACTIVE');
    expect(dev!.usuario_id).toBe(seed.cobrador_id);
  });

  test('B: COBRADOR NO puede listar dispositivos -> 403 real (fail-closed)', async () => {
    const r = await listar('cobrador');
    expect(r.status).toBe(403);
  });

  test('C: INVERSIONISTA NO puede listar dispositivos -> 403 real (fail-closed)', async () => {
    const r = await listar('inversionista');
    expect(r.status).toBe(403);
  });

  test('D: ADMINISTRADOR revoca -> 200 y el GET posterior persiste REVOKED', async () => {
    const r = await fetch(`${API}/api/dispositivos/${dCobradorId}/revocar`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${jwtAdmin}` },
    });
    expect(r.status).toBe(200);
    const dev = (await r.json()) as DispositivoAdminBody;
    expect(dev.estado).toBe('REVOKED');
    expect(dev.activo).toBe(0);

    const persistido = await dispositivoEnLista(dCobradorId);
    expect(persistido.estado).toBe('REVOKED');
    expect(persistido.revocado_el).toBeTruthy();
  });

  test('E: ADMINISTRADOR reactiva -> 200 y el DTO vuelve a ACTIVE', async () => {
    const r = await fetch(`${API}/api/dispositivos/${dCobradorId}/reactivar`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${jwtAdmin}` },
    });
    expect(r.status).toBe(200);
    const dev = (await r.json()) as DispositivoAdminBody;
    expect(dev.estado).toBe('ACTIVE');
    expect(dev.activo).toBe(1);

    const persistido = await dispositivoEnLista(dCobradorId);
    expect(persistido.estado).toBe('ACTIVE');
    expect(persistido.revocado_el).toBeNull();
  });

  test('F: reactivar con otro ACTIVE del mismo cobrador -> 409 controlado (no 500)', async () => {
    // Dispositivo histórico REVOKED del MISMO cobrador (fixture test-only vía
    // runSql). Con el dispositivo del cobrador ACTIVE, reactivarlo colisiona.
    const d2Id = crypto.randomUUID();
    runSql(
      `INSERT INTO dispositivo (id, negocio_id, usuario_id, public_key, public_key_hash, ` +
        `algoritmo_clave, modelo, plataforma, estado, version_asignacion, autorizado_por, ` +
        `autorizado_el, revocado_el, ultima_validacion_servidor, activo) ` +
        `VALUES ('${d2Id}', '${seed.negocio_id}', '${seed.cobrador_id}', NULL, NULL, NULL, ` +
        `'Dispositivo historico REVOKED', 'web', 'REVOKED', 1, NULL, ` +
        `NOW() - INTERVAL '1 day', NOW() - INTERVAL '1 day', NOW() - INTERVAL '1 hour', 0);`,
    );

    const r = await fetch(`${API}/api/dispositivos/${d2Id}/reactivar`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${jwtAdmin}` },
    });
    expect(r.status).toBe(409);
    const body = (await r.json()) as { detail?: string };
    expect(body.detail).toContain('ACTIVE');

    // El ACTIVE del cobrador sigue intacto tras el 409
    const persistido = await dispositivoEnLista(dCobradorId);
    expect(persistido.estado).toBe('ACTIVE');
  });

  test('G: reemplazar -> viejo REPLACED + código nuevo que canjeado crea el nuevo ACTIVE', async () => {
    const r = await fetch(`${API}/api/dispositivos/${dCobradorId}/reemplazar`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${jwtAdmin}` },
    });
    expect(r.status).toBe(200);
    const data = (await r.json()) as {
      dispositivo: DispositivoAdminBody;
      nuevo_codigo: { codigo_id: string; token: string; prefijo: string; expira_el: string | null };
    };
    expect(data.dispositivo.estado).toBe('REPLACED');
    expect(data.dispositivo.activo).toBe(0);
    for (const campo of CAMPOS_NO_ADMIN) {
      expect(data.dispositivo, `reemplazo real no expone ${campo}`).not.toHaveProperty(campo);
    }
    const nuevoToken = data.nuevo_codigo.token;
    expect(nuevoToken).toBeTruthy();

    // El viejo persiste REPLACED en el listado
    const viejo = await dispositivoEnLista(dCobradorId);
    expect(viejo.estado).toBe('REPLACED');

    // Canje REAL del código nuevo con par EC fresco -> el dispositivo nace ACTIVE
    const nuevo = await canjearCodigo(nuevoToken);
    expect(nuevo.dispositivo_id).not.toBe(dCobradorId);

    const nuevoEnLista = await dispositivoEnLista(nuevo.dispositivo_id);
    expect(nuevoEnLista.estado).toBe('ACTIVE');
    expect(nuevoEnLista.usuario_id).toBe(seed.cobrador_id);

    // Invariante: un solo ACTIVE por cobrador (el viejo quedó REPLACED)
    const list = await listar('admin');
    const body = (await list.json()) as DispositivoAdminBody[];
    const activosDelCobrador = body.filter((d) => d.usuario_id === seed.cobrador_id && d.estado === 'ACTIVE');
    expect(activosDelCobrador).toHaveLength(1);
    expect(activosDelCobrador[0].id).toBe(nuevo.dispositivo_id);
  });
});
