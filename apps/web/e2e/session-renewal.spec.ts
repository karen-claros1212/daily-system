import { test, expect, request as pwRequest, type APIRequestContext } from '@playwright/test';
import crypto from 'node:crypto';

import { buildPayloadActivacion, buildPayloadAuth } from '../src/lib/auth/jcs';
import { sha256Hex } from '../src/lib/auth/identity';

/**
 * Ciclo de vida de la sesión Web (Commit 5): renovación + expiración/revocación.
 *
 * Obtiene un JWT real para COBRADOR vía el flujo de dispositivo (daily-v1 ->
 * daily-auth-v1) contra el mock, lo coloca en la cookie httpOnly
 * `daily_admin_token` y verifica:
 *   1. El BFF `/api/auth/web/desafio` resuelve el dispositivo desde el JWT de
 *      la cookie -> 200 con challenge_id + device_id (renovable).
 *   2. Renovación sobre bearer revocado/vencido -> 401 (fail-closed, sin
 *      maquillar), simulando expiración/revocación del dispositivo.
 *
 * El redirect al login sin sesión ya lo cubre rbac-roles.spec.ts.
 */

const API = `http://localhost:${process.env.MOCK_API_PORT || 8100}`;
const SITE = 'http://localhost:3000';
const SESSION_COOKIE = 'daily_admin_token';

interface DeviceCreds {
  token: string;
  deviceId: string;
  publicKeyHash: string;
}

async function loginCobrador(ctx: APIRequestContext): Promise<DeviceCreds> {
  const kp = crypto.generateKeyPairSync('ec', { namedCurve: 'prime256v1' });
  const priv = kp.privateKey;
  const spkiB64 = kp.publicKey.export({ format: 'der', type: 'spki' }).toString('base64');
  const publicKeyHash = await sha256Hex(Uint8Array.from(Buffer.from(spkiB64, 'base64')));
  const sign = (p: Uint8Array) =>
    crypto
      .sign('sha256', Buffer.from(p), { key: priv, dsaEncoding: 'der' })
      .toString('base64url');

  const d = await (await ctx.post(`${API}/api/activaciones/desafio`, { data: { token: 'test-cobrador-code', clave_publica: spkiB64 } })).json();
  const payloadA = buildPayloadActivacion({
    protocolVersion: 'daily-v1',
    environment: d.environment,
    attemptId: d.intento_id,
    nonce: d.nonce,
    publicKeyHash,
    expiresAt: d.expira_el,
  });
  const canje = await (await ctx.post(`${API}/api/activaciones/canjear`, { data: { intento_id: d.intento_id, firma: sign(payloadA) } })).json();
  const des = await (
    await ctx.post(`${API}/api/auth/device/desafio`, {
      data: {},
      headers: { Authorization: `Bearer ${canje.credencial_bootstrap}` },
    })
  ).json();
  const payloadS = buildPayloadAuth({
    purpose: 'issue_access_token',
    environment: des.environment,
    challengeId: des.challenge_id,
    deviceId: canje.dispositivo_id,
    nonce: des.nonce,
    publicKeyHash,
    expiresAt: des.expira_el,
  });
  const session = await (await ctx.post(`${API}/api/auth/device/canjear`, { data: { challenge_id: des.challenge_id, firma: sign(payloadS) } })).json();
  return { token: session.token, deviceId: canje.dispositivo_id, publicKeyHash };
}

test.describe('Session lifecycle (real device flow + BFF)', () => {
  let ctx: APIRequestContext;

  test.beforeAll(async () => {
    ctx = await pwRequest.newContext();
  });
  test.afterAll(async () => await ctx.dispose());

  test('BFF renewal desafio resuelve el dispositivo desde la cookie del JWT', async () => {
    const { token, deviceId } = await loginCobrador(ctx);

    // /api/auth/web/desafio lee la cookie httpOnly y resuelve device_id del JWT.
    const r = await ctx.post(`${SITE}/api/auth/web/desafio`, {
      data: {},
      headers: { Cookie: `${SESSION_COOKIE}=${token}` },
    });
    expect(r.status()).toBe(200);
    const j = await r.json();
    expect(j.challenge_id).toBeTruthy();
    expect(j.device_id).toBe(deviceId);
    expect(j.nonce).toBeTruthy();
  });

  test('renovación sobre bearer revocado/vencido -> 401 (fail-closed)', async () => {
    // Un token que no resuelve dispositivo simula expiración/revocación.
    const r = await ctx.post(`${SITE}/api/auth/web/desafio`, {
      data: {},
      headers: { Cookie: `${SESSION_COOKIE}=token-revocado` },
    });
    // El BFF propaga el 401 del backend (sesión inválida) sin maquillar.
    expect(r.status()).toBe(401);
  });
});
