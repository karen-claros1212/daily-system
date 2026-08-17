import { test, expect } from '@playwright/test';
import { setSessionToken } from './helpers/session';

/**
 * W8 — Dashboard Ejecutivo (mock).
 *
 * Contrato (mock replica del FastAPI real):
 *  - GET /api/dashboard/ejecutivo  read-model ejecutivo (KPIs, tendencia, riesgo, alertas)
 *  - RBAC: dashboard:ejecutivo (SOLO ADMINISTRADOR en W8)
 *  - INVERSIONISTA: 403 (W9 completará su experiencia)
 *  - COBRADOR: 403 (tiene su dashboard de campo)
 *  - /dashboard despacha: ADMIN -> Ejecutivo, INV -> financiero actual, COB -> campo
 */

test.describe.configure({ mode: 'serial' });

test.describe('W8 E2E: ADMINISTRADOR - Dashboard Ejecutivo', () => {
  test.beforeEach(async ({ page }) => {
    await setSessionToken(page, 'mock-admin');
  });

  test('ADMIN ve Dashboard Ejecutivo con KPIs, tendencia, riesgo y alertas', async ({ page }) => {
    await page.goto('/dashboard');
    await expect(page.getByRole('heading', { name: 'Dashboard ejecutivo' })).toBeVisible();
    await expect(page.getByText('Cartera viva')).toBeVisible();
    await expect(page.getByText(/Cartera vencida \(/)).toBeVisible();
    await expect(page.getByText('Recaudo hoy')).toBeVisible();
    await expect(page.getByText(/Neto hoy/)).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Tendencia de recaudo (7 días)' })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Concentración de riesgo (aging)' })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Exposición por ruta' })).toBeVisible();
  });

  test('ADMIN ve sección Requiere atención con alertas', async ({ page }) => {
    await page.goto('/dashboard');
    await expect(page.getByRole('heading', { name: 'Requiere atención' })).toBeVisible();
    await expect(page.getByText('Hay jornadas sin cerrar hoy')).toBeVisible();
    await expect(page.getByText(/promesa\(s\) incumplida\(s\)/)).toBeVisible();
    await expect(page.getByText(/cliente\(s\) en mora/)).toBeVisible();
  });

  test('ADMIN ve fila operativa (rutas, cobradores, créditos, jornada)', async ({ page }) => {
    await page.goto('/dashboard');
    await expect(page.getByText('Rutas activas')).toBeVisible();
    await expect(page.getByText('Cobradores activos')).toBeVisible();
    await expect(page.getByText('Créditos activos')).toBeVisible();
    await expect(page.getByText('Jornada cerrada hoy')).toBeVisible();
  });

  test('ADMIN: BFF /api/dashboard/ejecutivo retorna 200 con shape completo', async ({ page }) => {
    const resp = await page.request.get('/api/dashboard/ejecutivo');
    expect(resp.status()).toBe(200);
    const body = await resp.json();
    expect(body).toHaveProperty('fecha');
    expect(body).toHaveProperty('negocio');
    expect(body.negocio).toHaveProperty('nombre');
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
    expect(body.riesgo.aging_distribution).toHaveProperty('CURRENT');
    expect(body.riesgo.aging_distribution).toHaveProperty('90+');
    expect(body).toHaveProperty('tendencia_7d');
    expect(body.tendencia_7d.serie).toHaveLength(7);
    expect(body.tendencia_7d.total_neto).toBe(body.tendencia_7d.serie.reduce((s, d) => s + d.neto, 0));
    expect(body).toHaveProperty('rutas');
    expect(Array.isArray(body.rutas)).toBe(true);
    expect(body).toHaveProperty('alertas');
    expect(Array.isArray(body.alertas)).toBe(true);
  });

  test('ADMIN: tabla de rutas muestra cartera y vencido por ruta', async ({ page }) => {
    await page.goto('/dashboard');
    await expect(page.getByRole('heading', { name: 'Exposición por ruta' })).toBeVisible();
    await expect(page.getByText('Ruta Centro')).toBeVisible();
    await expect(page.getByText('Ruta Norte')).toBeVisible();
    await expect(page.getByText('Ruta Sur')).toBeVisible();
  });

  test('ADMIN: aging muestra los 7 buckets', async ({ page }) => {
    await page.goto('/dashboard');
    await expect(page.getByRole('heading', { name: 'Concentración de riesgo (aging)' })).toBeVisible();
    await expect(page.getByText('Al día')).toBeVisible();
    await expect(page.getByText('1-7 días')).toBeVisible();
    await expect(page.getByText('90+ días')).toBeVisible();
  });

  test('ADMIN: tendencia muestra totales recaudo/reversal/neto', async ({ page }) => {
    await page.goto('/dashboard');
    await expect(page.getByRole('heading', { name: 'Tendencia de recaudo (7 días)' })).toBeVisible();
    await expect(page.getByText('Recaudo', { exact: true })).toBeVisible();
    await expect(page.getByText('Reversal', { exact: true })).toBeVisible();
    await expect(page.getByText('Neto', { exact: true })).toBeVisible();
  });
});

test.describe('W8 E2E: INVERSIONISTA - sin dashboard ejecutivo (W9 reservado)', () => {
  test('INVERSIONISTA no ve Dashboard Ejecutivo (ve el financiero actual)', async ({ page }) => {
    await setSessionToken(page, 'test-token');
    await page.goto('/dashboard');
    await expect(page.getByRole('heading', { name: 'Dashboard ejecutivo' })).not.toBeVisible();
    await expect(page.getByRole('heading', { name: 'Dashboard financiero' })).toBeVisible();
  });

  test('INVERSIONISTA: BFF /api/dashboard/ejecutivo retorna 403', async ({ page }) => {
    await setSessionToken(page, 'test-token');
    const resp = await page.request.get('/api/dashboard/ejecutivo');
    expect(resp.status()).toBe(403);
  });
});

test.describe('W8 E2E: COBRADOR - dashboard de campo preservado', () => {
  test('COBRADOR no ve Dashboard Ejecutivo (403 en BFF)', async ({ page }) => {
    await setSessionToken(page, 'test-cobrador-code');
    const resp = await page.request.get('/api/dashboard/ejecutivo');
    expect(resp.status()).toBe(403);
  });

  test('COBRADOR ve su dashboard de campo en /dashboard', async ({ page }) => {
    await setSessionToken(page, 'test-cobrador-code');
    await page.goto('/dashboard');
    await expect(page.getByRole('heading', { name: 'Dashboard ejecutivo' })).not.toBeVisible();
  });
});
