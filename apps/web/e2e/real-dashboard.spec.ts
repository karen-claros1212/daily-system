import { test, expect } from '@playwright/test';

import { seedActivacion, type SeedOutput } from './helpers/real-seed';

/**
 * W8 — Dashboard Ejecutivo contra FastAPI real (:8001) + Postgres real + BFF Next.js (:3000).
 *
 * Certifica el read-model ejecutivo a través de la integración Web (BFF):
 *   - ADMIN: cookie daily_admin_token = seed.tokens.administrador
 *   - INVERSIONISTA: cookie daily_admin_token = seed.tokens.inversionista → 403
 *
 * El BFF proxyGet() usa la cookie HttpOnly daily_admin_token.
 */

const BFF = process.env.BFF_BASE ?? 'http://localhost:3000';

let seed: SeedOutput;

test.describe.serial('W8 real: Dashboard Ejecutivo (FastAPI :8001 + BFF :3000)', () => {
  test.beforeAll(async () => {
    seed = seedActivacion();
  });

  test('ADMIN: /dashboard renderiza Dashboard Ejecutivo', async ({ browser }) => {
    const ctx = await browser.newContext();
    await ctx.addCookies([{ name: 'daily_admin_token', value: seed.tokens.administrador, url: BFF }]);
    const page = await ctx.newPage();
    await page.goto('/dashboard');
    await expect(page.getByRole('heading', { name: 'Dashboard ejecutivo' })).toBeVisible();
    await expect(page.getByText('Cartera viva')).toBeVisible();
    await expect(page.getByText('Recaudo hoy')).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Tendencia de recaudo (7 días)' })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Concentración de riesgo (aging)' })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Exposición por ruta' })).toBeVisible();
    await ctx.close();
  });

  test('ADMIN: BFF /api/dashboard/ejecutivo retorna 200 con shape completo', async ({ browser }) => {
    const ctx = await browser.newContext();
    await ctx.addCookies([{ name: 'daily_admin_token', value: seed.tokens.administrador, url: BFF }]);
    const page = await ctx.newPage();
    const resp = await page.request.get('/api/dashboard/ejecutivo');
    expect(resp.status()).toBe(200);
    const body = await resp.json();
    expect(body).toHaveProperty('fecha');
    expect(body).toHaveProperty('negocio');
    expect(body).toHaveProperty('hoy');
    expect(body.hoy).toHaveProperty('cartera_vigente');
    expect(body.hoy).toHaveProperty('cartera_vencida');
    expect(body.hoy).toHaveProperty('pct_vencido');
    expect(body.hoy).toHaveProperty('recaudo_hoy');
    expect(body.hoy).toHaveProperty('gastos_hoy');
    expect(body.hoy).toHaveProperty('neto_hoy');
    expect(body.hoy.neto_hoy).toBe(body.hoy.recaudo_hoy - body.hoy.gastos_hoy);
    expect(body).toHaveProperty('operativo');
    expect(body.operativo).toHaveProperty('rutas_activas');
    expect(body.operativo).toHaveProperty('cobradores_activos');
    expect(body.operativo).toHaveProperty('creditos_activos');
    expect(body.operativo).toHaveProperty('jornada_cerrada_hoy');
    expect(body).toHaveProperty('riesgo');
    expect(body.riesgo).toHaveProperty('aging_distribution');
    expect(body).toHaveProperty('tendencia_7d');
    expect(body.tendencia_7d.serie).toHaveLength(7);
    expect(body.tendencia_7d.total_neto).toBe(body.tendencia_7d.serie.reduce((s, d) => s + d.neto, 0));
    expect(body).toHaveProperty('rutas');
    expect(Array.isArray(body.rutas)).toBe(true);
    expect(body).toHaveProperty('alertas');
    expect(Array.isArray(body.alertas)).toBe(true);
    for (const a of body.alertas) {
      expect(a).toHaveProperty('tipo');
      expect(a).toHaveProperty('mensaje');
      expect(['info', 'warning', 'critical']).toContain(a.severidad);
    }
    await ctx.close();
  });

  test('ADMIN: consistencia con /api/cobranza/resumen (misma autoridad)', async ({ browser }) => {
    const ctx = await browser.newContext();
    await ctx.addCookies([{ name: 'daily_admin_token', value: seed.tokens.administrador, url: BFF }]);
    const page = await ctx.newPage();
    const r1 = await page.request.get('/api/dashboard/ejecutivo');
    expect(r1.status()).toBe(200);
    const dash = await r1.json();
    const r2 = await page.request.get('/api/cobranza/resumen');
    expect(r2.status()).toBe(200);
    const resumen = await r2.json();
    expect(dash.hoy.cartera_vigente).toBe(resumen.total_cartera);
    expect(dash.hoy.cartera_vencida).toBe(resumen.total_vencido);
    expect(dash.hoy.pct_vencido).toBe(resumen.pct_vencido);
    expect(dash.riesgo.clientes_en_mora).toBe(resumen.clientes_en_mora);
    expect(dash.riesgo.aging_distribution).toEqual(resumen.aging_distribution);
    await ctx.close();
  });

  test('INVERSIONISTA: BFF /api/dashboard/ejecutivo retorna 403', async ({ browser }) => {
    const ctx = await browser.newContext();
    await ctx.addCookies([{ name: 'daily_admin_token', value: seed.tokens.inversionista, url: BFF }]);
    const page = await ctx.newPage();
    const resp = await page.request.get('/api/dashboard/ejecutivo');
    expect(resp.status()).toBe(403);
    await ctx.close();
  });

  test('INVERSIONISTA: /dashboard NO renderiza Dashboard Ejecutivo (W9 reservado)', async ({ browser }) => {
    const ctx = await browser.newContext();
    await ctx.addCookies([{ name: 'daily_admin_token', value: seed.tokens.inversionista, url: BFF }]);
    const page = await ctx.newPage();
    await page.goto('/dashboard');
    await expect(page.getByRole('heading', { name: 'Dashboard ejecutivo' })).not.toBeVisible();
    await expect(page.getByRole('heading', { name: 'Dashboard financiero' })).toBeVisible();
    await ctx.close();
  });
});
