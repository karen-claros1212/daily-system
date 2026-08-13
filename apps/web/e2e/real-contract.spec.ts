import { test, expect } from '@playwright/test';

import { buildPayloadActivacion, buildPayloadAuth, base64UrlNoPad } from '../src/lib/auth/jcs';
import { rawToDerSignature, sha256Hex } from '../src/lib/auth/identity';
import { runSql, seedActivacion } from './helpers/real-seed';

/**
 * Negativos del contrato real (Paso 2b) — contra FastAPI real en :8001,
 * Postgres real, SIN mock-api.mjs. Genera su propio par EC P-256 en el
 * proceso del test (Node WebCrypto) y registra el dispositivo por el flujo de
 * activación real; a partir de ahi ejercita cada rechazo canónico.
 *
 * Expiración determinista (sin sleeps): UPDATE directo a la DB (helpers psql)
 * con `REAL_DB_URL` (default postgres://postgres@127.0.0.1:5433/daily_web_e2e_test).
 */

const API = process.env.REAL_API_BASE ?? 'http://127.0.0.1:8001';

let keyPair: CryptoKeyPair;
let spkiB64: string;
let publicKeyHash: string;

async function freshKeyPair(): Promise<void> {
  keyPair = await crypto.subtle.generateKey({ name: 'ECDSA', namedCurve: 'P-256' }, true, ['sign', 'verify']);
  const spki = new Uint8Array(await crypto.subtle.exportKey('spki', keyPair.publicKey));
  spkiB64 = Buffer.from(spki).toString('base64');
  publicKeyHash = await sha256Hex(spki);
}

async function signJcs(payload: Uint8Array): Promise<string> {
  const raw = new Uint8Array(
    await crypto.subtle.sign({ name: 'ECDSA', hash: 'SHA-256' }, keyPair.privateKey, payload),
  );
  return base64UrlNoPad(rawToDerSignature(raw));
}

interface DesafioActivacion { intento_id: string; nonce: string; expira_el: string; environment: string; }
interface CanjeActivacion {
  dispositivo_id: string; negocio_id: string; cobrador_id: string;
  credencial_bootstrap: string; expira_el: string; idempotente?: boolean;
}
interface DesafioSesion { challenge_id: string; nonce: string; expira_el: string; environment: string; }

async function activar(code: string): Promise<{ canje: CanjeActivacion; firma: string; intento_id: string }> {
  const d = await fetch(`${API}/api/activaciones/desafio`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ token: code, clave_publica: spkiB64, modelo: 'web', plataforma: 'web' }),
  });
  const desafio = (await d.json()) as DesafioActivacion;
  const payload = buildPayloadActivacion({
    protocolVersion: 'daily-v1',
    environment: desafio.environment,
    attemptId: desafio.intento_id,
    nonce: desafio.nonce,
    publicKeyHash,
    expiresAt: desafio.expira_el,
  });
  const firma = await signJcs(payload);
  const r = await fetch(`${API}/api/activaciones/canjear`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ intento_id: desafio.intento_id, firma }),
  });
  return { canje: (await r.json()) as CanjeActivacion, firma, intento_id: desafio.intento_id };
}

async function desafioSesion(credencial: string) {
  const r = await fetch(`${API}/api/auth/device/desafio`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${credencial}` },
  });
  const body = await r.json().catch(() => ({}));
  return { status: r.status, body };
}

async function canjearSesion(challenge_id: string, firma: string) {
  const r = await fetch(`${API}/api/auth/device/canjear`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ challenge_id, firma }),
  });
  const body = await r.json().catch(() => ({}));
  return { status: r.status, body };
}

let canjeReal: CanjeActivacion;
let bootstrap: string;
let jwtReal: string;
let firmaActivacion: string;
let intentoActivacion: string;

test.describe.serial('Paso 2b — Negativos contra FastAPI real (:8001)', () => {
  test.beforeAll(async () => {
    const { codigo_activacion } = seedActivacion();
    await freshKeyPair();
    const { canje, firma, intento_id } = await activar(codigo_activacion);
    canjeReal = canje;
    bootstrap = canje.credencial_bootstrap;
    firmaActivacion = firma;
    intentoActivacion = intento_id;
    expect(canje.dispositivo_id).toBeTruthy();
  });

  test('IDEMPOTENCIA real: re-canje del MISMO intento con la MISMA firma → 200 idempotente=true', async () => {
    // La idempotencia real vive en /api/activaciones/canjear (activacion_service):
    // mismo intento consumido + MISMA firma + bootstrap vigente -> 200
    // idempotente=true y devuelve el MISMO dispositivo/credencial. No inventa
    // una segunda activacion.
    const r = await fetch(`${API}/api/activaciones/canjear`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ intento_id: intentoActivacion, firma: firmaActivacion }),
    });
    expect(r.status).toBe(200);
    const j = (await r.json()) as CanjeActivacion;
    expect(j.idempotente).toBe(true);
    expect(j.dispositivo_id).toBe(canjeReal.dispositivo_id);
    expect(j.credencial_bootstrap).toBe(canjeReal.credencial_bootstrap);
    expect(j.expira_el).toBe(canjeReal.expira_el);
  });

  test('Bootstrap VALIDO -> desafio sesion 200 y canje firma real -> JWT 200', async () => {
    const d = await desafioSesion(bootstrap);
    expect(d.status).toBe(200);
    const ch = d.body as DesafioSesion;
    const payload = buildPayloadAuth({
      purpose: 'issue_access_token',
      environment: ch.environment,
      challengeId: ch.challenge_id,
      deviceId: canjeReal.dispositivo_id,
      nonce: ch.nonce,
      publicKeyHash,
      expiresAt: ch.expira_el,
    });
    const firma = await signJcs(payload);
    const c = await canjearSesion(ch.challenge_id, firma);
    expect(c.status).toBe(200);
    expect((c.body as { token: string }).token).toBeTruthy();
    jwtReal = (c.body as { token: string }).token;
  });

  test('Desafio protegido SIN Bearer → 401', async () => {
    const r = await fetch(`${API}/api/auth/device/desafio`, { method: 'POST' });
    expect(r.status).toBe(401);
  });

  test('Desafio con Bearer invalido (bootstrap falso) → 401', async () => {
    const d = await desafioSesion('bootstrap-falso-basura-no-existe');
    expect(d.status).toBe(401);
    expect((d.body as { detail?: string }).detail).toContain('Credencial de sesion invalida');
  });

  test('Firma ECDSA invalida (otra clave privada) → 401', async () => {
    const d = await desafioSesion(bootstrap);
    expect(d.status).toBe(200);
    const ch = d.body as DesafioSesion;
    // Firmar con OTRO par: la firma es DER valida pero de otra privada.
    const other = await crypto.subtle.generateKey({ name: 'ECDSA', namedCurve: 'P-256' }, true, ['sign', 'verify']);
    const payload = buildPayloadAuth({
      purpose: 'issue_access_token',
      environment: ch.environment,
      challengeId: ch.challenge_id,
      deviceId: canjeReal.dispositivo_id,
      nonce: ch.nonce,
      publicKeyHash,
      expiresAt: ch.expira_el,
    });
    const raw = new Uint8Array(
      await crypto.subtle.sign({ name: 'ECDSA', hash: 'SHA-256' }, other.privateKey, payload),
    );
    const firma = base64UrlNoPad(rawToDerSignature(raw));
    const c = await canjearSesion(ch.challenge_id, firma);
    expect(c.status).toBe(401);
    expect((c.body as { detail?: string }).detail).toContain('Firma invalida');
  });

  test('Payload JCS alterado DESPUES de firmar → 401', async () => {
    const d = await desafioSesion(bootstrap);
    expect(d.status).toBe(200);
    const ch = d.body as DesafioSesion;
    // Firmar un payload cuyo nonce difiere del emitido por el servidor: el
    // backend re-deriva el payload canónico desde el desafio y la firma no
    // cuadra. El nonce alterado mantiene el FORMATO valido (43 chars
    // base64url) para que el fallo ocurra en la verificacion ECDSA, no en la
    // validacion de formato.
    const nonceAlterado = 'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'; // 43 chars, distinto
    const payloadAlterado = buildPayloadAuth({
      purpose: 'issue_access_token',
      environment: ch.environment,
      challengeId: ch.challenge_id,
      deviceId: canjeReal.dispositivo_id,
      nonce: nonceAlterado,
      publicKeyHash,
      expiresAt: ch.expira_el,
    });
    const firma = await signJcs(payloadAlterado);
    const c = await canjearSesion(ch.challenge_id, firma);
    expect(c.status).toBe(401);
  });

  test('Challenge reutilizado (replay de challenge_id) → 409', async () => {
    const d = await desafioSesion(bootstrap);
    expect(d.status).toBe(200);
    const ch = d.body as DesafioSesion;
    const payload = buildPayloadAuth({
      purpose: 'issue_access_token',
      environment: ch.environment,
      challengeId: ch.challenge_id,
      deviceId: canjeReal.dispositivo_id,
      nonce: ch.nonce,
      publicKeyHash,
      expiresAt: ch.expira_el,
    });
    const firma = await signJcs(payload);
    const c1 = await canjearSesion(ch.challenge_id, firma);
    expect(c1.status).toBe(200);
    const c2 = await canjearSesion(ch.challenge_id, firma);
    expect(c2.status).toBe(409);
    expect((c2.body as { detail?: string }).detail).toContain('ya utilizado');
  });

  test('Challenge expirado → 410 (expiración determinista por DB)', async () => {
    const d = await desafioSesion(bootstrap);
    expect(d.status).toBe(200);
    const ch = d.body as DesafioSesion;
    // Backdatear expira_el a un minuto en el pasado, sin esperar el TTL real.
    runSql(`UPDATE desafio_auth SET expira_el = now() - interval '1 minute' WHERE id = '${ch.challenge_id}'`);
    const firma = await signJcs(
      buildPayloadAuth({
        purpose: 'issue_access_token',
        environment: ch.environment,
        challengeId: ch.challenge_id,
        deviceId: canjeReal.dispositivo_id,
        nonce: ch.nonce,
        publicKeyHash,
        expiresAt: ch.expira_el,
      }),
    );
    const c = await canjearSesion(ch.challenge_id, firma);
    expect(c.status).toBe(410);
    expect((c.body as { detail?: string }).detail).toContain('vencido');
  });

  test('Bootstrap expirado → desafio 401 (backdate determinista)', async () => {
    runSql(
      `UPDATE codigo_activacion SET credencial_bootstrap_expira_el = now() - interval '1 minute' ` +
        `WHERE credencial_bootstrap = '${bootstrap}'`,
    );
    const d = await desafioSesion(bootstrap);
    expect(d.status).toBe(401);
    expect((d.body as { detail?: string }).detail).toContain('Credencial de sesion invalida');
  });

  test('Dispositivo revocado (estado != ACTIVE) → desafio con JWT viejito 401', async () => {
    runSql(`UPDATE dispositivo SET estado = 'REVOKED', version_asignacion = version_asignacion + 1 WHERE id = '${canjeReal.dispositivo_id}'`);
    const d = await desafioSesion(jwtReal);
    expect(d.status).toBe(401);
  });

  test('Challenge inexistente → 404', async () => {
    const c = await canjearSesion('00000000-0000-0000-0000-000000000000', 'AAAA');
    expect(c.status).toBe(404);
  });
});