import { test, expect } from '@playwright/test';

import { seedActivacion, type SeedOutput } from './helpers/real-seed';

/**
 * W7 — Reportes Premium contra FastAPI real (:8001) + Postgres real + BFF Next.js (:3000).
 *
 * Certifica los read-models de reportes a través de la integración Web (BFF):
 *   - ADMIN: cookie daily_admin_token = seed.tokens.administrador
 *   - INVERSIONISTA: cookie daily_admin_token = seed.tokens.inversionista
 *
 * El BFF proxyGet() usa la cookie HttpOnly daily_admin_token.
 */

const BFF = process.env.BFF_BASE ?? 'http://localhost:3000';

let seed: SeedOutput;

test.describe.serial('W7 real: Reportes Premium (FastAPI :8001 + BFF :3000)', () => {
  test.beforeAll(async () => {
    seed = seedActivacion();
  });

  test('ADMIN: /reportes muestra KPIs y secciones', async ({ browser }) => {
    const ctx = await browser.newContext();
    await ctx.addCookies([{ name: 'daily_admin_token', value: seed.tokens.administrador, url: BFF }]);
    const page = await ctx.newPage();
    await page.goto(`${BFF}/reportes`, { waitUntil: 'networkidle' });
    await expect(page.getByRole('heading', { name: 'Reportes' })).toBeVisible({ timeout: 10000 });
    await expect(page.getByText('Cartera vigente')).toBeVisible();
    await expect(page.getByText('Cartera vencida')).toBeVisible();
    await expect(page.getByText('Recaudo del periodo')).toBeVisible();
    await expect(page.getByText('Neto del periodo')).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Tendencia de recaudo' })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Aging de cartera' })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Rendimiento por rutas' })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Gastos y movimientos' })).toBeVisible();
    await ctx.close();
  });

  test('ADMIN: BFF /api/reportes/resumen retorna 200 con datos', async ({ browser }) => {
    const ctx = await browser.newContext();
    await ctx.addCookies([{ name: 'daily_admin_token', value: seed.tokens.administrador, url: BFF }]);
    const page = await ctx.newPage();
    const resp = await page.request.get('/api/reportes/resumen?periodo=hoy');
    expect(resp.status()).toBe(200);
    const body = await resp.json();
    expect(body).toHaveProperty('cartera_vigente');
    expect(body).toHaveProperty('cartera_vencida');
    expect(body).toHaveProperty('recaudo_periodo');
    expect(body).toHaveProperty('gastos_periodo');
    expect(body).toHaveProperty('neto_periodo');
    await ctx.close();
  });

  test('ADMIN: BFF /api/reportes/recaudo retorna serie', async ({ browser }) => {
    const ctx = await browser.newContext();
    await ctx.addCookies([{ name: 'daily_admin_token', value: seed.tokens.administrador, url: BFF }]);
    const page = await ctx.newPage();
    const resp = await page.request.get('/api/reportes/recaudo?periodo=7d');
    expect(resp.status()).toBe(200);
    const body = await resp.json();
    expect(body).toHaveProperty('serie');
    expect(Array.isArray(body.serie)).toBe(true);
    expect(body).toHaveProperty('total_recaudo');
    expect(body).toHaveProperty('total_neto');
    await ctx.close();
  });

  test('ADMIN: BFF /api/reportes/aging retorna buckets', async ({ browser }) => {
    const ctx = await browser.newContext();
    await ctx.addCookies([{ name: 'daily_admin_token', value: seed.tokens.administrador, url: BFF }]);
    const page = await ctx.newPage();
    const resp = await page.request.get('/api/reportes/aging');
    expect(resp.status()).toBe(200);
    const body = await resp.json();
    expect(body).toHaveProperty('buckets');
    expect(body.buckets).toHaveProperty('CURRENT');
    expect(body.buckets).toHaveProperty('1-7');
    await ctx.close();
  });

  test('ADMIN: BFF /api/reportes/rutas retorna rutas', async ({ browser }) => {
    const ctx = await browser.newContext();
    await ctx.addCookies([{ name: 'daily_admin_token', value: seed.tokens.administrador, url: BFF }]);
    const page = await ctx.newPage();
    const resp = await page.request.get('/api/reportes/rutas?periodo=hoy');
    expect(resp.status()).toBe(200);
    const body = await resp.json();
    expect(body).toHaveProperty('rutas');
    expect(Array.isArray(body.rutas)).toBe(true);
    await ctx.close();
  });

  test('ADMIN: BFF /api/reportes/movimientos retorna por_tipo', async ({ browser }) => {
    const ctx = await browser.newContext();
    await ctx.addCookies([{ name: 'daily_admin_token', value: seed.tokens.administrador, url: BFF }]);
    const page = await ctx.newPage();
    const resp = await page.request.get('/api/reportes/movimientos?periodo=hoy');
    expect(resp.status()).toBe(200);
    const body = await resp.json();
    expect(body).toHaveProperty('por_tipo');
    expect(Array.isArray(body.por_tipo)).toBe(true);
    expect(body).toHaveProperty('total_gastos');
    await ctx.close();
  });

  test('INVERSIONISTA: /reportes accesible con reportes:ver', async ({ browser }) => {
    const ctx = await browser.newContext();
    await ctx.addCookies([{ name: 'daily_admin_token', value: seed.tokens.inversionista, url: BFF }]);
    const page = await ctx.newPage();
    await page.goto(`${BFF}/reportes`, { waitUntil: 'networkidle' });
    await expect(page.getByRole('heading', { name: 'Reportes' })).toBeVisible({ timeout: 10000 });
    await expect(page.getByText('Cartera vigente')).toBeVisible();
    await ctx.close();
  });

  test('INVERSIONISTA: BFF /api/reportes/resumen retorna 200', async ({ browser }) => {
    const ctx = await browser.newContext();
    await ctx.addCookies([{ name: 'daily_admin_token', value: seed.tokens.inversionista, url: BFF }]);
    const page = await ctx.newPage();
    const resp = await page.request.get('/api/reportes/resumen?periodo=hoy');
    expect(resp.status()).toBe(200);
    const body = await resp.json();
    expect(body).toHaveProperty('cartera_vigente');
    await ctx.close();
  });

  test('periodo 7d: BFF /api/reportes/resumen retorna 200', async ({ browser }) => {
    const ctx = await browser.newContext();
    await ctx.addCookies([{ name: 'daily_admin_token', value: seed.tokens.administrador, url: BFF }]);
    const page = await ctx.newPage();
    const resp = await page.request.get('/api/reportes/resumen?periodo=7d');
    expect(resp.status()).toBe(200);
    const body = await resp.json();
    expect(body).toHaveProperty('periodo', '7d');
    await ctx.close();
  });

  test('periodo 30d: BFF /api/reportes/recaudo retorna 200', async ({ browser }) => {
    const ctx = await browser.newContext();
    await ctx.addCookies([{ name: 'daily_admin_token', value: seed.tokens.administrador, url: BFF }]);
    const page = await ctx.newPage();
    const resp = await page.request.get('/api/reportes/recaudo?periodo=30d');
    expect(resp.status()).toBe(200);
    const body = await resp.json();
    expect(body).toHaveProperty('periodo', '30d');
    await ctx.close();
  });
});
