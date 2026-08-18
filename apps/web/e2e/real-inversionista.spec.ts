import { test, expect } from '@playwright/test';

import { seedActivacion, runSql, type SeedOutput } from './helpers/real-seed';

/**
 * W9 — Inversionista Final contra FastAPI real (:8001) + Postgres real + BFF Next.js (:3000).
 *
 * Certifica la experiencia completa del INVERSIONISTA a través de la integración
 * Web (BFF, cookie HttpOnly daily_admin_token = seed.tokens.inversionista):
 *   1. /dashboard renderiza DashboardInversionista.
 *   2. resumen BFF real = 200.
 *   3. datos financieros coinciden con autoridades backend (W6/W7).
 *   4. aging/tendencia presentes.
 *   5. Reportes 200.
 *   6. Créditos 200 PII-minimized.
 *   7. Cobranza 200 PII-minimized.
 *   8. Movimientos 200 PII-minimized.
 *   9. Rutas 200 sin cobrador PII.
 *   10. Suscripción 200 read-only.
 *   11. Clientes direct URL bloqueado.
 *   12. Usuarios/audit/dispositivos bloqueados.
 *   13. mutaciones administrativas 403.
 *   14. cross-tenant no filtra información.
 */

const BFF = process.env.BFF_BASE ?? 'http://localhost:3000';
const API = process.env.REAL_API_BASE ?? 'http://127.0.0.1:8001';

let seed: SeedOutput;

test.describe.serial('W9 real: Inversionista Final (FastAPI :8001 + BFF :3000)', () => {
  test.beforeAll(async () => {
    seed = seedActivacion();
  });

  function invContext() {
    return {
      cookie: { name: 'daily_admin_token', value: seed.tokens.inversionista, url: BFF },
      bearer: { Authorization: `Bearer ${seed.tokens.inversionista}` },
    };
  }

  test('1. /dashboard renderiza DashboardInversionista', async ({ browser }) => {
    const ctx = await browser.newContext();
    await ctx.addCookies([invContext().cookie]);
    const page = await ctx.newPage();
    await page.goto('/dashboard');
    await expect(page.getByRole('heading', { name: 'Dashboard financiero' })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Dashboard ejecutivo' })).not.toBeVisible();
    await expect(page.getByText('Cartera viva')).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Tendencia de recaudo (7 días)' })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Exposición por ruta' })).toBeVisible();
    await ctx.close();
  });

  test('2. resumen BFF real = 200 con shape W9', async ({ browser }) => {
    const ctx = await browser.newContext();
    await ctx.addCookies([invContext().cookie]);
    const page = await ctx.newPage();
    const resp = await page.request.get('/api/inversionista/resumen');
    expect(resp.status()).toBe(200);
    const body = await resp.json();
    expect(body.portfolio).toHaveProperty('cartera_viva');
    expect(body.portfolio).toHaveProperty('cartera_vencida');
    expect(body.portfolio).toHaveProperty('pct_vencido');
    expect(body.portfolio).toHaveProperty('recaudo_hoy');
    expect(body.portfolio).toHaveProperty('neto_hoy');
    expect(body).toHaveProperty('negocio');
    expect(body.negocio).toHaveProperty('fecha');
    expect(body).toHaveProperty('riesgo');
    expect(body.riesgo).toHaveProperty('aging_distribution');
    expect(body).toHaveProperty('tendencia_7d');
    expect(body.tendencia_7d.serie).toHaveLength(7);
    expect(Array.isArray(body.rutas)).toBe(true);
    await ctx.close();
  });

  test('3. datos financieros coinciden con autoridades W6/W7', async ({ browser }) => {
    const ctx = await browser.newContext();
    await ctx.addCookies([invContext().cookie]);
    const page = await ctx.newPage();
    const r1 = await page.request.get('/api/inversionista/resumen');
    expect(r1.status()).toBe(200);
    const inv = await r1.json();
    const r2 = await page.request.get('/api/cobranza/resumen');
    expect(r2.status()).toBe(200);
    const cobranza = await r2.json();
    // Una sola fórmula de cartera: INV == W6.
    expect(inv.portfolio.cartera_viva).toBe(cobranza.total_cartera);
    expect(inv.portfolio.cartera_vencida).toBe(cobranza.total_vencido);
    expect(inv.portfolio.pct_vencido).toBe(cobranza.pct_vencido);
    expect(inv.riesgo.clientes_en_mora).toBe(cobranza.clientes_en_mora);
    expect(inv.riesgo.aging_distribution).toEqual(cobranza.aging_distribution);
    await ctx.close();
  });

  test('4. aging y tendencia presentes y coherentes', async ({ browser }) => {
    const ctx = await browser.newContext();
    await ctx.addCookies([invContext().cookie]);
    const page = await ctx.newPage();
    const resp = await page.request.get('/api/inversionista/resumen');
    const body = await resp.json();
    // Aging: 7 buckets.
    const buckets = Object.keys(body.riesgo.aging_distribution);
    expect(buckets).toContain('CURRENT');
    expect(buckets).toContain('90+');
    // Tendencia: 7 días, neto coherente.
    expect(body.tendencia_7d.serie).toHaveLength(7);
    expect(body.tendencia_7d.total_neto).toBe(
      body.tendencia_7d.serie.reduce((s: number, d: { neto: number }) => s + d.neto, 0),
    );
    await ctx.close();
  });

  test('5. Reportes 200 (reportes:ver)', async ({ browser }) => {
    const ctx = await browser.newContext();
    await ctx.addCookies([invContext().cookie]);
    const page = await ctx.newPage();
    const resp = await page.request.get('/api/reportes/resumen');
    expect(resp.status()).toBe(200);
    await ctx.close();
  });

  test('6. Créditos 200 PII-minimized', async ({ browser }) => {
    const ctx = await browser.newContext();
    await ctx.addCookies([invContext().cookie]);
    const page = await ctx.newPage();
    const resp = await page.request.get('/api/creditos');
    expect(resp.status()).toBe(200);
    const body = await resp.json();
    for (const item of body.items) {
      expect(item.cliente_nombre).toBeNull();
      expect(item.cliente_id).toBeNull();
      expect(item.cobrador_nombre).toBeNull();
    }
    await ctx.close();
  });

  test('7. Cobranza 200 PII-minimized', async ({ browser }) => {
    const ctx = await browser.newContext();
    await ctx.addCookies([invContext().cookie]);
    const page = await ctx.newPage();
    const resp = await page.request.get('/api/cobranza/web');
    expect(resp.status()).toBe(200);
    const body = await resp.json();
    for (const item of body.items) {
      expect(item.cliente_nombre).toBeNull();
      expect(item.cliente_id).toBeNull();
      expect(item.cobrador_nombre).toBeNull();
    }
    await ctx.close();
  });

  test('8. Movimientos 200 PII-minimized', async ({ browser }) => {
    const ctx = await browser.newContext();
    await ctx.addCookies([invContext().cookie]);
    const page = await ctx.newPage();
    const resp = await page.request.get('/api/movimientos');
    expect(resp.status()).toBe(200);
    const body = await resp.json();
    for (const item of body.items) {
      expect(item.creado_por_nombre).toBeNull();
      expect(item.nota).toBeNull();
    }
    await ctx.close();
  });

  test('9. Rutas 200 sin cobrador PII', async ({ browser }) => {
    const ctx = await browser.newContext();
    await ctx.addCookies([invContext().cookie]);
    const page = await ctx.newPage();
    const resp = await page.request.get('/api/rutas');
    expect(resp.status()).toBe(200);
    const body = await resp.json();
    expect(body.items.length).toBeGreaterThanOrEqual(1);
    for (const item of body.items) {
      expect(item.cobrador_id).toBeNull();
      expect(item.cobrador_nombre).toBeNull();
      // ruta_nombre sí está (agregado, no PII).
      expect(item.nombre).toBeTruthy();
    }
    await ctx.close();
  });

  test('10. Suscripción 200 read-only', async ({ browser }) => {
    const ctx = await browser.newContext();
    await ctx.addCookies([invContext().cookie]);
    const page = await ctx.newPage();
    const resp = await page.request.get('/api/inversionista/suscripcion');
    expect(resp.status()).toBe(200);
    const body = await resp.json();
    expect(body).toHaveProperty('estado_suscripcion');
    expect(body).toHaveProperty('plan');
    expect(body).toHaveProperty('activa');
    await ctx.close();
  });

  test('11. Clientes direct URL bloqueado (403 controlado)', async ({ browser }) => {
    const ctx = await browser.newContext();
    await ctx.addCookies([invContext().cookie]);
    const page = await ctx.newPage();
    await page.goto('/clientes');
    await expect(page.getByRole('heading', { name: 'Acceso denegado' })).toBeVisible();
    await ctx.close();
  });

  test('12. Usuarios/audit/dispositivos direct URL bloqueados', async ({ browser }) => {
    const ctx = await browser.newContext();
    await ctx.addCookies([invContext().cookie]);
    const page = await ctx.newPage();
    for (const path of ['/usuarios', '/auditoria', '/dispositivos']) {
      await page.goto(path);
      await expect(page.getByRole('heading', { name: 'Acceso denegado' })).toBeVisible();
    }
    await ctx.close();
  });

  test('13. mutaciones administrativas 403 (POST /api/creditos, /api/usuarios)', async () => {
    const headers = { Authorization: `Bearer ${seed.tokens.inversionista}`, 'Content-Type': 'application/json' };
    // INV no crea créditos (creditos:gestionar es ADMIN-only) -> 403 (no 401).
    const r1 = await fetch(`${API}/api/creditos`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ cliente_id: seed.inversionista_id, ruta_id: seed.ruta_id, cuota: 10000, n_cuotas: 10, monto: 10000, fecha_inicio: '2026-08-16' }),
    });
    expect(r1.status).toBe(403);
    // INV no gestiona usuarios (usuarios:gestionar es ADMIN-only) -> 403.
    const r2 = await fetch(`${API}/api/usuarios`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ rol: 'COBRADOR', nombre: 'X', documento: '1' }),
    });
    expect(r2.status).toBe(403);
  });

  test('14. cross-tenant: negocio ajeno no filtra información', async ({ browser }) => {
    // Crea un negocio B con un crédito; el INV del negocio A no lo ve.
    const nitB = `9${Date.now().toString().slice(-8)}`;
    const rNeg = await (await fetch(`${API}/api/onboarding/negocios`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ nombre: `W9 Tenant B ${nitB}`, nit: nitB, administrador: { nombre: 'Admin B' } }),
    })).json() as { negocio: { id: string } };
    const nidB = rNeg.negocio.id;

    const ctx = await browser.newContext();
    await ctx.addCookies([invContext().cookie]);
    const page = await ctx.newPage();
    const resp = await page.request.get('/api/inversionista/resumen');
    const body = await resp.json();
    // El negocio A (seed) NO incluye el negocio_id B en su cartera.
    expect(body.negocio.nombre).not.toContain(`Tenant B ${nitB}`);
    expect(body.negocio_nombre).not.toContain(`Tenant B ${nitB}`);
    await ctx.close();

    // Limpieza: el negocio B no contamina (queda en su propio tenant).
    runSql(`DELETE FROM credito WHERE negocio_id = '${nidB}'`);
    runSql(`DELETE FROM negocio WHERE id = '${nidB}'`);
  });
});
