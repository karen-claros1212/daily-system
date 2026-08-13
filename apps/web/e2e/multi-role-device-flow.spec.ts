import { test, expect, request as pwRequest } from '@playwright/test';
import crypto from 'node:crypto';

import { buildPayloadActivacion, buildPayloadAuth } from '../src/lib/auth/jcs';
import { sha256Hex } from '../src/lib/auth/identity';

/**
 * Matriz de activación multi-rol CONTRA EL MOCK (sin browser).
 *
 * Prueba que los TRES roles (COBRADOR/INVERSIONISTA/ADMINISTRADOR) atraviesan
 * el mismo mecanismo real de dispositivo (daily-v1 + daily-auth-v1) contra el
 * mock endurecido, y que el rol se deriva del código de activación objetivo
 * (como el backend en activacion_service._rol_usuario), NUNCA del cliente:
 *   desafio de activación -> canjear (bootstrap + device_id + rol) ->
 *   desafio de sesion -> canjear (emite token) -> /api/auth/me (rol server-side).
 *
 * Códigos por rol (mock-api.mjs ACTIVATION_TOKENS):
 *   - test-cobrador-code  -> COBRADOR   (ruta activa requerida, H3)
 *   - test-inversor-code  -> INVERSIONISTA (sin ruta)
 *   - test-admin-code     -> ADMINISTRADOR (sin ruta)
 *
 * La clave del dispositivo se genera en el proceso del test (ECDSA P-256) y la
 * firma se produce en formato DER-SHA256, exactamente como lo haría el browser
 * vía src/lib/auth/identity.ts (rawToDerSignature).
 */

const MOCK = `http://localhost:${process.env.MOCK_API_PORT || 8100}`;

const ROLES = [
  { code: 'test-cobrador-code', rol: 'COBRADOR', route_id: 'r1' },
  { code: 'test-inversor-code', rol: 'INVERSIONISTA', route_id: null },
  { code: 'test-admin-code', rol: 'ADMINISTRADOR', route_id: null },
] as const;

test.describe('Multi-role device flow (hardened mock)', () => {
  let ctx: Awaited<ReturnType<typeof pwRequest.newContext>>;
  let spkiB64: string;
  let publicKeyHash: string;
  let priv: crypto.KeyObject;

  test.beforeAll(async () => {
    ctx = await pwRequest.newContext({ baseURL: MOCK });
    const kp = crypto.generateKeyPairSync('ec', { namedCurve: 'prime256v1' });
    priv = kp.privateKey;
    spkiB64 = kp.publicKey.export({ format: 'der', type: 'spki' }).toString('base64');
    publicKeyHash = await sha256Hex(Uint8Array.from(Buffer.from(spkiB64, 'base64')));
  });
  test.afterAll(async () => { await ctx.dispose(); });

  const signDer = (payload: Uint8Array) =>
    crypto
      .sign('sha256', Buffer.from(payload), { key: priv, dsaEncoding: 'der' })
      .toString('base64url');

  for (const { code, rol, route_id } of ROLES) {
    test(`${rol} (${code}) atraviesa el flujo de dispositivo real`, async () => {
      // 1) desafío de activación (público, sin Bearer).
      const desafioRes = await ctx.post('/api/activaciones/desafio', {
        data: { token: code, clave_publica: spkiB64 },
      });
      expect(desafioRes.status(), `${rol}: desafio activacion`).toBe(200);
      const desafio = await desafioRes.json();

      // 2) canjear activación: firma JCS daily-v1 -> bootstrap + device_id + rol.
      const payloadActivacion = buildPayloadActivacion({
        protocolVersion: 'daily-v1',
        environment: desafio.environment,
        attemptId: desafio.intento_id,
        nonce: desafio.nonce,
        publicKeyHash,
        expiresAt: desafio.expira_el,
      });
      const canjeRes = await ctx.post('/api/activaciones/canjear', {
        data: { intento_id: desafio.intento_id, firma: signDer(payloadActivacion) },
      });
      expect(canjeRes.status(), `${rol}: canje activacion`).toBe(200);
      const canje = await canjeRes.json();
      expect(canje.rol).toBe(rol);
      expect(canje.credencial_bootstrap).toBeTruthy();

      // 3) desafío de sesion autenticado con el bootstrap (en memoria del BFF).
      const sesionDesafioRes = await ctx.post('/api/auth/device/desafio', {
        data: {},
        headers: { Authorization: `Bearer ${canje.credencial_bootstrap}` },
      });
      expect(sesionDesafioRes.status(), `${rol}: desafio sesion`).toBe(200);
      const sesionDesafio = await sesionDesafioRes.json();

      // 4) canjear sesion: firma JCS daily-auth-v1 -> emite token.
      const payloadAuth = buildPayloadAuth({
        purpose: 'issue_access_token',
        environment: sesionDesafio.environment,
        challengeId: sesionDesafio.challenge_id,
        deviceId: canje.dispositivo_id,
        nonce: sesionDesafio.nonce,
        publicKeyHash,
        expiresAt: sesionDesafio.expira_el,
      });
      const sesionCanjeRes = await ctx.post('/api/auth/device/canjear', {
        data: { challenge_id: sesionDesafio.challenge_id, firma: signDer(payloadAuth) },
      });
      expect(sesionCanjeRes.status(), `${rol}: canje sesion`).toBe(200);
      const sesionCanje = await sesionCanjeRes.json();
      expect(sesionCanje.token).toBeTruthy();

      // 5) /api/auth/me: fuente canónica; el rol sale de la "DB" del mock.
      const meRes = await ctx.get('/api/auth/me', {
        headers: { Authorization: `Bearer ${sesionCanje.token}` },
      });
      expect(meRes.status(), `${rol}: /me`).toBe(200);
      const me = await meRes.json();
      expect(me.rol).toBe(rol);
      expect(me.route_id).toBe(route_id);
      expect(me.activo).toBe(true);
    });
  }

  test('código de activación inexistente -> 404 (fail-closed, no ruta/rol por inducción)', async () => {
    // Un código desconocido NUNCA produce dispositivo ni sesión: el mock
    // rechaza en el primer paso (404), como el backend (CODIGO_INVALIDO 404).
    // No se permite inducir ruta ni rol por el body público.
    const kp = crypto.generateKeyPairSync('ec', { namedCurve: 'prime256v1' });
    const spki = kp.publicKey.export({ format: 'der', type: 'spki' }).toString('base64');
    const res = await ctx.post('/api/activaciones/desafio', {
      data: { token: 'codigo-que-no-existe', clave_publica: spki },
    });
    expect(res.status()).toBe(404);
    expect((await res.json()).detail).toContain('invalido');
  });
});
