import { test, expect } from '@playwright/test';

import { buildPayloadActivacion, buildPayloadAuth, base64UrlNoPad } from '../src/lib/auth/jcs';
import { rawToDerSignature, sha256Hex } from '../src/lib/auth/identity';
import { seedActivacion, runSql, type SeedOutput } from './helpers/real-seed';

/**
 * W5 — Centro Financiero: Movimientos contra FastAPI real (:8001) + Postgres real + BFF Next.js (:3000).
 *
 * Certifica el read-model web de movimientos a través de la integración Web (BFF):
 *   - ADMIN: cookie daily_admin_token = seed.tokens.administrador
 *   - INVERSIONISTA: cookie daily_admin_token = seed.tokens.inversionista
 *   - COBRADOR: cookie daily_admin_token = JWT real del flujo de dispositivo
 *
 * El BFF proxyGet() usa la cookie HttpOnly daily_admin_token, NO el header
 * Authorization. Por tanto los tests crean contextos Playwright por rol.
 */

const API = process.env.REAL_API_BASE ?? 'http://127.0.0.1:8001';
const BFF = process.env.BFF_BASE ?? 'http://localhost:3000';

let seed: SeedOutput;
let jwtCobrador: string;

test.describe.serial('W5 real: Movimientos Web (FastAPI :8001 + BFF :3000)', () => {
  test.beforeAll(async ({ browser }) => {
    seed = seedActivacion();

    // Insertar jornada + movimientos en PG.
    const jornadaId = crypto.randomUUID();
    const mov1Id = crypto.randomUUID();
    const mov2Id = crypto.randomUUID();
    const mov3Id = crypto.randomUUID();

    await runSql(`
      INSERT INTO jornada (id, negocio_id, ruta_id, estado, opening_base, fecha)
      VALUES ('${jornadaId}', '${seed.negocio_id}', '${seed.ruta_id}', 'OPEN', 1000, NOW());
      INSERT INTO movimiento_caja (id, negocio_id, jornada_id, tipo, naturaleza, monto, nota, clave_idempotencia, creado_por)
      VALUES
        ('${mov1Id}', '${seed.negocio_id}', '${jornadaId}', 'GASOLINA', 'GASTO', 50000, 'Gasolina e2e', 'w5-real-1', '${seed.cobrador_id}'),
        ('${mov2Id}', '${seed.negocio_id}', '${jornadaId}', 'OFICINA', 'GASTO', 20000, 'Material e2e', 'w5-real-2', '${seed.cobrador_id}'),
        ('${mov3Id}', '${seed.negocio_id}', '${jornadaId}', 'RECIBIDO', 'CUENTA_POR_COBRAR', 100000, 'Cobro e2e', 'w5-real-3', '${seed.cobrador_id}');
    `);

    // JWT real de COBRADOR vía flujo de dispositivo canónico.
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

    // 1) Activación daily-v1
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
    const bootstrapCred = canje.credencial_bootstrap;
    const deviceId = canje.dispositivo_id;

    // 2) Desafío de dispositivo daily-auth-v1
    const rDesafio = await fetch(`${API}/api/auth/device/desafio`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${bootstrapCred}` },
      body: JSON.stringify({ dispositivo_id: deviceId }),
    });
    expect(rDesafio.status).toBe(200);
    const sesDesafio = (await rDesafio.json()) as { challenge_id: string; nonce: string; expira_el: string; environment: string };
    const payloadAuth = buildPayloadAuth({
      protocolVersion: 'daily-auth-v1',
      environment: sesDesafio.environment,
      attemptId: sesDesafio.challenge_id,
      nonce: sesDesafio.nonce,
      expiresAt: sesDesafio.expira_el,
      publicKeyHash,
    });
    const rSesion = await fetch(`${API}/api/auth/device/canjear`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${bootstrapCred}` },
      body: JSON.stringify({ challenge_id: sesDesafio.challenge_id, firma: await signJcs(payloadAuth) }),
    });
    expect(rSesion.status).toBe(200);
    const sesion = (await rSesion.json()) as { token: string };
    jwtCobrador = sesion.token;
  });

  // ─── ADMIN ───────────────────────────────────────────────────────────────────

  test('ADMIN: BFF cookie real → envelope con 3 movimientos', async ({ browser }) => {
    const ctx = await browser.newContext();
    await ctx.addCookies([{ name: 'daily_admin_token', value: seed.tokens.administrador, url: BFF }]);
    const page = await ctx.newPage();
    const res = await page.request.get(`${BFF}/api/movimientos?limit=50`);
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body.total).toBe(3);
    expect(body.items).toHaveLength(3);
    expect(body.limit).toBe(50);
    expect(body.offset).toBe(0);
    const item = body.items[0];
    expect(item).toHaveProperty('id');
    expect(item).toHaveProperty('tipo');
    expect(item).toHaveProperty('monto');
    expect(item).toHaveProperty('creado_por_nombre');
    expect(item.creado_por_nombre).not.toBeNull();
    await ctx.close();
  });

  test('ADMIN: BFF cookie real → resumen con agregados', async ({ browser }) => {
    const ctx = await browser.newContext();
    await ctx.addCookies([{ name: 'daily_admin_token', value: seed.tokens.administrador, url: BFF }]);
    const page = await ctx.newPage();
    const res = await page.request.get(`${BFF}/api/movimientos/resumen`);
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body.total_movimientos).toBe(3);
    expect(body.total_monto).toBe(170000);
    expect(body.gastos_por_tipo).toHaveLength(2);
    const gastos = Object.fromEntries(body.gastos_por_tipo.map((g: { tipo: string; total: number }) => [g.tipo, g.total]));
    expect(gastos['GASOLINA']).toBe(50000);
    expect(gastos['OFICINA']).toBe(20000);
    await ctx.close();
  });

  test('ADMIN: filtro naturaleza=GASTO → 2 items', async ({ browser }) => {
    const ctx = await browser.newContext();
    await ctx.addCookies([{ name: 'daily_admin_token', value: seed.tokens.administrador, url: BFF }]);
    const page = await ctx.newPage();
    const res = await page.request.get(`${BFF}/api/movimientos?naturaleza=GASTO`);
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body.total).toBe(2);
    expect(body.items).toHaveLength(2);
    await ctx.close();
  });

  test('ADMIN: búsqueda por nota', async ({ browser }) => {
    const ctx = await browser.newContext();
    await ctx.addCookies([{ name: 'daily_admin_token', value: seed.tokens.administrador, url: BFF }]);
    const page = await ctx.newPage();
    const res = await page.request.get(`${BFF}/api/movimientos?q=Gasolina`);
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body.total).toBe(1);
    expect(body.items[0].tipo).toBe('GASOLINA');
    await ctx.close();
  });

  test('ADMIN: sort=monto&order=asc ordena correctamente', async ({ browser }) => {
    const ctx = await browser.newContext();
    await ctx.addCookies([{ name: 'daily_admin_token', value: seed.tokens.administrador, url: BFF }]);
    const page = await ctx.newPage();
    const res = await page.request.get(`${BFF}/api/movimientos?sort=monto&order=asc`);
    expect(res.status()).toBe(200);
    const body = await res.json();
    const montos = body.items.map((i: { monto: number }) => i.monto);
    expect(montos).toEqual([...montos].sort((a, b) => a - b));
    await ctx.close();
  });

  test('ADMIN: paginación limit=2&offset=0 → 2 items', async ({ browser }) => {
    const ctx = await browser.newContext();
    await ctx.addCookies([{ name: 'daily_admin_token', value: seed.tokens.administrador, url: BFF }]);
    const page = await ctx.newPage();
    const res = await page.request.get(`${BFF}/api/movimientos?limit=2&offset=0`);
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body.total).toBe(3);
    expect(body.items).toHaveLength(2);
    expect(body.limit).toBe(2);
    await ctx.close();
  });

  test('ADMIN: sort inválido → 422', async ({ browser }) => {
    const ctx = await browser.newContext();
    await ctx.addCookies([{ name: 'daily_admin_token', value: seed.tokens.administrador, url: BFF }]);
    const page = await ctx.newPage();
    const res = await page.request.get(`${BFF}/api/movimientos?sort=invalido`);
    expect(res.status()).toBe(422);
    await ctx.close();
  });

  test('ADMIN: order inválido → 422', async ({ browser }) => {
    const ctx = await browser.newContext();
    await ctx.addCookies([{ name: 'daily_admin_token', value: seed.tokens.administrador, url: BFF }]);
    const page = await ctx.newPage();
    const res = await page.request.get(`${BFF}/api/movimientos?order=invalido`);
    expect(res.status()).toBe(422);
    await ctx.close();
  });

  // ─── COBRADOR ────────────────────────────────────────────────────────────────

  test('COBRADOR: JWT real de dispositivo → solo ruta activa', async ({ browser }) => {
    const ctx = await browser.newContext();
    await ctx.addCookies([{ name: 'daily_admin_token', value: jwtCobrador, url: BFF }]);
    const page = await ctx.newPage();
    const res = await page.request.get(`${BFF}/api/movimientos?limit=50`);
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body.total).toBe(3);
    for (const item of body.items) {
      expect(item.ruta_id).toBe(seed.ruta_id);
    }
    await ctx.close();
  });

  test('COBRADOR: /me tiene movimientos:ver', async () => {
    const r = await fetch(`${API}/api/auth/me`, {
      headers: { Authorization: `Bearer ${jwtCobrador}` },
    });
    expect(r.status).toBe(200);
    const body = await r.json();
    expect(body.rol).toBe('COBRADOR');
    expect(body.capabilities).toContain('movimientos:ver');
  });

  // ─── INVERSIONISTA ───────────────────────────────────────────────────────────

  test('INVERSIONISTA: cookie real → PII/minimización', async ({ browser }) => {
    const ctx = await browser.newContext();
    await ctx.addCookies([{ name: 'daily_admin_token', value: seed.tokens.inversionista, url: BFF }]);
    const page = await ctx.newPage();
    const res = await page.request.get(`${BFF}/api/movimientos?limit=50`);
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body.total).toBe(3);
    for (const item of body.items) {
      expect(item.creado_por_nombre).toBeNull();
      expect(item.nota).toBeNull();
    }
    await ctx.close();
  });
});
