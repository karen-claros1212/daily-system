import { test, expect, request as pwRequest } from '@playwright/test';
import crypto from 'node:crypto';

// ─── Pruebas de CONTRATO contra el mock endurecido, sin pasar por el
// ─── navegador: verifica los negativos del contrato auth
// ─── (401 to/401 firma/409 replay/410 vencido/404 inexistente) con firma real
// ─── ECDSA-DER, como los produciria el navegador (identity.ts rawToDerSignature).
//
// El puerto del mock sale de MOCK_API_PORT (el config lo fija a 8100, puerto
// dedicado; :8000 lo comparte un servicio del sistema).

const MOCK = `http://localhost:${process.env.MOCK_API_PORT || 8100}`;

function jcsStringify(value: string): string {
  let out = '"';
  for (const ch of value) {
    const code = ch.codePointAt(0);
    if (code === 0x22) out += '\\"';
    else if (code === 0x5c) out += '\\\\';
    else if (code <= 0x1f) out += `\\u00${code.toString(16).padStart(2, '0')}`;
    else out += ch;
  }
  return out + '"';
}
function jcs(obj: Record<string, string>): string {
  const keys = Object.keys(obj).sort();
  return `{${keys.map((k) => `${jcsStringify(k)}:${jcsStringify(obj[k])}`).join(',')}}`;
}
function sha256hex(b: Buffer): string {
  return crypto.createHash('sha256').update(b).digest('hex');
}
function signDer(payload: string, key: crypto.KeyObject): string {
  return crypto
    .sign('sha256', Buffer.from(payload, 'utf8'), { key, dsaEncoding: 'der' })
    .toString('base64url');
}

test.describe('Auth contract against hardened mock', () => {
  let ctx: Awaited<ReturnType<typeof pwRequest.newContext>>;
  let priv: crypto.KeyObject;
  let pub: crypto.KeyObject;
  let spkiB64: string;

  test.beforeAll(async () => {
    ctx = await pwRequest.newContext({ baseURL: MOCK });
    const kp = crypto.generateKeyPairSync('ec', { namedCurve: 'prime256v1' });
    priv = kp.privateKey;
    pub = kp.publicKey;
    spkiB64 = pub.export({ format: 'der', type: 'spki' }).toString('base64');
  });
  test.afterAll(async () => {
    await ctx.dispose();
  });

  async function desafio(token: string) {
    return ctx.post('/api/activaciones/desafio', { data: { token, clave_publica: spkiB64 } });
  }
  function payloadActivacion(d: { intento_id: string; nonce: string; expira_el: string; environment: string }): string {
    return jcs({
      protocol_version: 'daily-v1',
      environment: d.environment,
      attempt_id: d.intento_id,
      nonce: d.nonce,
      public_key_hash: sha256hex(Buffer.from(spkiB64, 'base64')),
      expires_at: d.expira_el,
    });
  }
  async function canjear(intentoId: string, firma: string) {
    return ctx.post('/api/activaciones/canjear', { data: { intento_id: intentoId, firma } });
  }

  test('token invalido en desafio de activacion -> 404', async () => {
    const r = await desafio('no-existe');
    expect(r.status()).toBe(404);
  });

  test('desafio activacion sin SPKI valido -> 400', async () => {
    const r = await ctx.post('/api/activaciones/desafio', {
      data: { token: 'test-activation-code', clave_publica: 'no-una-spki' },
    });
    expect(r.status()).toBe(400);
  });

  test('firma invalida en canje activacion -> 401', async () => {
    const d = await (await desafio('test-activation-code')).json();
    const r = await canjear(d.intento_id, Buffer.alloc(70, 1).toString('base64url'));
    expect(r.status()).toBe(401);
    expect((await r.json()).detail).toContain('Firma invalida');
  });

  test('desafio activacion reutilizado -> 409 (replay hostil, firma distinta)', async () => {
    const d = await (await desafio('test-activation-code')).json();
    const payload = payloadActivacion(d);
    const ok = await canjear(d.intento_id, signDer(payload, priv));
    expect(ok.status()).toBe(200);

    // Reintento idempotente con la MISMA firma -> 200 idempotente (contrato real)
    const idem = await canjear(d.intento_id, signDer(payload, priv));
    expect(idem.status()).toBe(200);
    expect((await idem.json()).idempotente).toBe(true);

    // Replay hostil (firma distinta sobre el mismo intento) -> 409
    const hostil = await ctx.post('/api/auth/device/desafio', { data: {} });
    void hostil;
    const r = await canjear(d.intento_id, signDer(payload + 'x', priv));
    expect(r.status()).toBe(409);
  });

  test('intento de activacion vencido -> 410', async () => {
    const d = await (await desafio('test-expired-code')).json();
    const r = await canjear(d.intento_id, signDer(payloadActivacion(d), priv));
    expect(r.status()).toBe(410);
  });

  test('intento de activacion inexistente -> 404', async () => {
    const r = await canjear('00000000-0000-4000-8000-000000000000', 'ab');
    expect(r.status()).toBe(404);
  });

  test('desafio de sesion sin Bearer -> 401', async () => {
    const r = await ctx.post('/api/auth/device/desafio', { data: {} });
    expect(r.status()).toBe(401);
  });

  test('desafio de sesion con bootstrap invalido -> 401', async () => {
    const r = await ctx.post('/api/auth/device/desafio', {
      headers: { Authorization: 'Bearer credencial-inexistente' },
      data: {},
    });
    expect(r.status()).toBe(401);
  });

  test('canje de sesion con challenge desconocido -> 404', async () => {
    const r = await ctx.post('/api/auth/device/canjear', {
      data: { challenge_id: '00000000-0000-4000-8000-000000000000', firma: 'ab' },
    });
    expect(r.status()).toBe(404);
  });

  test('canje de sesion con challenge vencido -> 410', async () => {
    const des = await ctx.post('/api/auth/device/desafio', {
      headers: { Authorization: 'Bearer mock-jwt-expired' },
      data: {},
    });
    expect(des.status()).toBe(200);
    const ch = await des.json();
    const r = await ctx.post('/api/auth/device/canjear', {
      data: { challenge_id: ch.challenge_id, firma: signDer('', priv) },
    });
    expect(r.status()).toBe(410);
  });

  test('canje de sesion con firma invalida -> 401', async () => {
    // Bootstrap real via canje de activacion valido (replay idempotente).
    const d = await (await desafio('test-activation-code')).json();
    const payload = payloadActivacion(d);
    const canje = await canjear(d.intento_id, signDer(payload, priv));
    if (canje.status() !== 200) {
      // consumo previo: reintento idempotente
      const idem = await canjear(d.intento_id, signDer(payload, priv));
      expect(idem.status()).toBe(200);
    }
    const bootstrapTk = (await canje.json()).credencial_bootstrap;

    const des = await ctx.post('/api/auth/device/desafio', {
      headers: { Authorization: `Bearer ${bootstrapTk}` },
      data: {},
    });
    expect(des.status()).toBe(200);
    const ch = await des.json();
    const r = await ctx.post('/api/auth/device/canjear', {
      data: { challenge_id: ch.challenge_id, firma: Buffer.alloc(70, 1).toString('base64url') },
    });
    expect(r.status()).toBe(401);
  });
});