import { test, expect } from '@playwright/test';

import { buildPayloadActivacion, buildPayloadAuth, base64UrlNoPad } from '../src/lib/auth/jcs';
import { rawToDerSignature, sha256Hex } from '../src/lib/auth/identity';
import { seedActivacion, runSql, type SeedOutput } from './helpers/real-seed';

/**
 * W6 — Cobranza y Mora contra FastAPI real (:8001) + Postgres real + BFF Next.js (:3000).
 *
 * Certifica el read-model web de cobranza a través de la integración Web (BFF):
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
let creditoId: string;

test.describe.serial('W6 real: Cobranza Web (FastAPI :8001 + BFF :3000)', () => {
  test.beforeAll(async ({ browser }) => {
    seed = seedActivacion();

    // Insertar cliente + crédito con cuotas vencidas en PG.
    creditoId = crypto.randomUUID();
    const clienteId = crypto.randomUUID();
    const cuota1Id = crypto.randomUUID();
    const cuota2Id = crypto.randomUUID();
    const cuota3Id = crypto.randomUUID();

    await runSql(`
      INSERT INTO cliente (id, negocio_id, tipo_documento, documento_normalizado, nombres, primer_apellido, identity_status)
      VALUES ('${clienteId}', '${seed.negocio_id}', 'CC', '123456789', 'Cliente E2E', 'W6', 'PROVISIONAL');
      INSERT INTO credito (id, negocio_id, cliente_id, ruta_id, monto, total, cuota, n_cuotas, estado, fecha_inicio)
      VALUES ('${creditoId}', '${seed.negocio_id}', '${clienteId}', '${seed.ruta_id}', 200000, 600000, 200000, 3, 'ACTIVO', NOW() - INTERVAL '60 days');
      INSERT INTO cuota_programada (id, negocio_id, credito_id, numero, monto, fecha_vencimiento, estado)
      VALUES
        ('${cuota1Id}', '${seed.negocio_id}', '${creditoId}', 1, 200000, NOW() - INTERVAL '45 days', 'PENDIENTE'),
        ('${cuota2Id}', '${seed.negocio_id}', '${creditoId}', 2, 200000, NOW() - INTERVAL '15 days', 'PENDIENTE'),
        ('${cuota3Id}', '${seed.negocio_id}', '${creditoId}', 3, 200000, NOW() + INTERVAL '15 days', 'PENDIENTE');
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

    const rDesafio = await fetch(`${API}/api/auth/device/desafio`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${bootstrapCred}` },
      body: JSON.stringify({ dispositivo_id: deviceId }),
    });
    expect(rDesafio.status).toBe(200);
    const sesDesafio = (await rDesafio.json()) as { challenge_id: string; nonce: string; expira_el: string; environment: string };
    const payloadAuth = buildPayloadAuth({
      purpose: 'issue_access_token',
      environment: sesDesafio.environment,
      challengeId: sesDesafio.challenge_id,
      deviceId,
      nonce: sesDesafio.nonce,
      publicKeyHash,
      expiresAt: sesDesafio.expira_el,
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

  test('ADMIN: BFF cookie real → worklist con crédito en mora', async ({ browser }) => {
    const ctx = await browser.newContext();
    await ctx.addCookies([{ name: 'daily_admin_token', value: seed.tokens.administrador, url: BFF }]);
    const page = await ctx.newPage();
    const res = await page.request.get(`${BFF}/api/cobranza/web?limit=50`);
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body.total).toBeGreaterThanOrEqual(1);
    expect(body.items).toHaveLength(body.total);
    const item = body.items.find((i: { credito_id: string }) => i.credito_id === creditoId);
    expect(item).toBeDefined();
    expect(item.aging_bucket).not.toBe('CURRENT');
    expect(item.days_past_due).toBeGreaterThan(0);
    expect(item.overdue_installments).toBeGreaterThanOrEqual(1);
    await ctx.close();
  });

  test('ADMIN: BFF cookie real → resumen con KPIs', async ({ browser }) => {
    const ctx = await browser.newContext();
    await ctx.addCookies([{ name: 'daily_admin_token', value: seed.tokens.administrador, url: BFF }]);
    const page = await ctx.newPage();
    const res = await page.request.get(`${BFF}/api/cobranza/resumen`);
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body.total_creditos).toBeGreaterThanOrEqual(1);
    expect(body.total_saldo).toBeGreaterThan(0);
    expect(body.aging_distribution).toBeDefined();
    await ctx.close();
  });

  test('ADMIN: drill-down muestra obligaciones vencidas y promesas', async ({ browser }) => {
    const ctx = await browser.newContext();
    await ctx.addCookies([{ name: 'daily_admin_token', value: seed.tokens.administrador, url: BFF }]);
    const page = await ctx.newPage();
    const res = await page.request.get(`${BFF}/api/cobranza/${creditoId}`);
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body.credito_id).toBe(creditoId);
    expect(body.obligaciones_vencidas).toHaveLength(expect.any(Number));
    expect(body.obligaciones_vencidas.length).toBeGreaterThanOrEqual(1);
    expect(body.promesas).toBeDefined();
    expect(body.aging_bucket).not.toBe('CURRENT');
    await ctx.close();
  });

  test('ADMIN: crea promesa → 201 + estado ACTIVE', async ({ browser }) => {
    const ctx = await browser.newContext();
    await ctx.addCookies([{ name: 'daily_admin_token', value: seed.tokens.administrador, url: BFF }]);
    const page = await ctx.newPage();
    const res = await page.request.post(`${BFF}/api/cobranza/promesas`, {
      data: {
        credito_id: creditoId,
        amount: 200000,
        promised_date: new Date(Date.now() + 7 * 86400000).toISOString().split('T')[0],
        nota: 'Promesa e2e real',
        clave_idempotencia: crypto.randomUUID(),
      },
    });
    expect(res.status()).toBe(201);
    const body = await res.json();
    expect(body.id).toBeDefined();
    expect(body.estado).toBe('ACTIVE');
    await ctx.close();
  });

  test('ADMIN: segunda promesa sin cancelar → 409', async ({ browser }) => {
    const ctx = await browser.newContext();
    await ctx.addCookies([{ name: 'daily_admin_token', value: seed.tokens.administrador, url: BFF }]);
    const page = await ctx.newPage();
    const res = await page.request.post(`${BFF}/api/cobranza/promesas`, {
      data: {
        credito_id: creditoId,
        amount: 100000,
        promised_date: new Date(Date.now() + 14 * 86400000).toISOString().split('T')[0],
        clave_idempotencia: crypto.randomUUID(),
      },
    });
    expect(res.status()).toBe(409);
    await ctx.close();
  });

  test('ADMIN: promesa con monto inválido → 422', async ({ browser }) => {
    const ctx = await browser.newContext();
    await ctx.addCookies([{ name: 'daily_admin_token', value: seed.tokens.administrador, url: BFF }]);
    const page = await ctx.newPage();
    const res = await page.request.post(`${BFF}/api/cobranza/promesas`, {
      data: {
        credito_id: creditoId,
        amount: 0,
        promised_date: new Date(Date.now() + 7 * 86400000).toISOString().split('T')[0],
        clave_idempotencia: crypto.randomUUID(),
      },
    });
    expect(res.status()).toBe(422);
    await ctx.close();
  });

  // ─── COBRADOR ────────────────────────────────────────────────────────────────

  test('COBRADOR: JWT real → worklist scoped a su ruta', async ({ browser }) => {
    const ctx = await browser.newContext();
    await ctx.addCookies([{ name: 'daily_admin_token', value: jwtCobrador, url: BFF }]);
    const page = await ctx.newPage();
    const res = await page.request.get(`${BFF}/api/cobranza/web?limit=50`);
    expect(res.status()).toBe(200);
    const body = await res.json();
    for (const item of body.items) {
      expect(item.ruta_id).toBe(seed.ruta_id);
    }
    await ctx.close();
  });

  test('COBRADOR: drill-down de crédito en su ruta → 200', async ({ browser }) => {
    const ctx = await browser.newContext();
    await ctx.addCookies([{ name: 'daily_admin_token', value: jwtCobrador, url: BFF }]);
    const page = await ctx.newPage();
    const res = await page.request.get(`${BFF}/api/cobranza/${creditoId}`);
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body.credito_id).toBe(creditoId);
    expect(body.ruta_id).toBe(seed.ruta_id);
    await ctx.close();
  });

  test('COBRADOR: /me tiene cobranza:ver y promesas:crear', async () => {
    const r = await fetch(`${API}/api/auth/me`, {
      headers: { Authorization: `Bearer ${jwtCobrador}` },
    });
    expect(r.status).toBe(200);
    const body = await r.json();
    expect(body.rol).toBe('COBRADOR');
    expect(body.capabilities).toContain('cobranza:ver');
    expect(body.capabilities).toContain('promesas:crear');
  });

  // ─── INVERSIONISTA ───────────────────────────────────────────────────────────

  test('INVERSIONISTA: cookie real → PII minimizada en worklist', async ({ browser }) => {
    const ctx = await browser.newContext();
    await ctx.addCookies([{ name: 'daily_admin_token', value: seed.tokens.inversionista, url: BFF }]);
    const page = await ctx.newPage();
    const res = await page.request.get(`${BFF}/api/cobranza/web?limit=50`);
    expect(res.status()).toBe(200);
    const body = await res.json();
    for (const item of body.items) {
      expect(item.cliente_nombre).toBeNull();
      expect(item.cliente_id).toBeNull();
    }
    await ctx.close();
  });

  test('INVERSIONISTA: drill-down sin PII', async ({ browser }) => {
    const ctx = await browser.newContext();
    await ctx.addCookies([{ name: 'daily_admin_token', value: seed.tokens.inversionista, url: BFF }]);
    const page = await ctx.newPage();
    const res = await page.request.get(`${BFF}/api/cobranza/${creditoId}`);
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body.cliente_nombre).toBeNull();
    expect(body.cobrador_nombre).toBeNull();
    expect(body.saldo).toBeGreaterThan(0);
    await ctx.close();
  });
});
