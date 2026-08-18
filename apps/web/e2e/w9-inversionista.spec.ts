import { test, expect } from '@playwright/test';
import { setSessionToken } from './helpers/session';

/**
 * W9 — Inversionista Final (mock).
 *
 * Contrato (mock replica del FastAPI real):
 *  - GET /api/inversionista/resumen  read-model financiero W9 (portfolio +
 *    negocio + riesgo + tendencia_7d + rutas), PII minimizada.
 *  - /dashboard despacha INVERSIONISTA -> DashboardInversionista (snapshot
 *    financiero read-only).
 *  - Navegación por capabilities: reportes:ver, creditos:ver, cobranza:ver,
 *    movimientos:ver, rutas:ver, inversionista:suscripcion.
 *  - Direct URLs administrativas -> vista 403 controlada (Acceso denegado).
 *  - Sin PII de cliente/cobrador en ninguna superficie.
 */

test.describe.configure({ mode: 'serial' });

test.describe('W9 E2E: INVERSIONISTA - Dashboard financiero premium', () => {
  test.beforeEach(async ({ page }) => {
    await setSessionToken(page, 'test-token');
  });

  test('INV ve DashboardInversionista (no el ejecutivo)', async ({ page }) => {
    await page.goto('/dashboard');
    await expect(page.getByRole('heading', { name: 'Dashboard financiero' })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Dashboard ejecutivo' })).not.toBeVisible();
  });

  test('INV: encabezado con negocio, fecha de negocio y plan', async ({ page }) => {
    await page.goto('/dashboard');
    await expect(page.getByText('Test Negocio')).toBeVisible();
    await expect(page.getByText('Plan')).toBeVisible();
    // Enlace a suscripción (estado completo en /suscripcion).
    await expect(page.getByRole('link', { name: 'Suscripción' })).toBeVisible();
  });

  test('INV: KPIs financieros (cartera viva, vencida, recaudo, neto)', async ({ page }) => {
    await page.goto('/dashboard');
    await expect(page.getByText('Cartera viva')).toBeVisible();
    await expect(page.getByText(/Cartera vencida \(/)).toBeVisible();
    await expect(page.getByText('Recaudo hoy')).toBeVisible();
    await expect(page.getByText(/Neto hoy/)).toBeVisible();
  });

  test('INV: riesgo y promesas (conteos, sin PII)', async ({ page }) => {
    await page.goto('/dashboard');
    await expect(page.getByText('Créditos activos')).toBeVisible();
    await expect(page.getByText('Clientes en mora')).toBeVisible();
    await expect(page.getByText('Promesas activas')).toBeVisible();
    await expect(page.getByText('Promesas incumplidas')).toBeVisible();
  });

  test('INV: tendencia 7d con totales', async ({ page }) => {
    await page.goto('/dashboard');
    await expect(page.getByRole('heading', { name: 'Tendencia de recaudo (7 días)' })).toBeVisible();
    await expect(page.getByText('Recaudo', { exact: true })).toBeVisible();
    await expect(page.getByText('Reversal', { exact: true })).toBeVisible();
    await expect(page.getByText('Neto', { exact: true })).toBeVisible();
  });

  test('INV: aging (7 buckets) y exposición por ruta', async ({ page }) => {
    await page.goto('/dashboard');
    await expect(page.getByRole('heading', { name: 'Concentración de riesgo (aging)' })).toBeVisible();
    await expect(page.getByText('Al día')).toBeVisible();
    await expect(page.getByText('90+ días')).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Exposición por ruta' })).toBeVisible();
    await expect(page.getByText('Ruta Norte')).toBeVisible();
    await expect(page.getByText('Ruta Sur')).toBeVisible();
  });

  test('INV: accesos a Reportes, Créditos, Cobranza, Centro Financiero', async ({ page }) => {
    await page.goto('/dashboard');
    await expect(page.getByRole('heading', { name: 'Explorar' })).toBeVisible();
    await expect(page.getByRole('link', { name: /Reportes/ })).toBeVisible();
    await expect(page.getByRole('link', { name: /Créditos/ })).toBeVisible();
    await expect(page.getByRole('link', { name: /Cobranza/ })).toBeVisible();
    await expect(page.getByRole('link', { name: /Centro Financiero/ })).toBeVisible();
  });

  test('INV: BFF /api/inversionista/resumen retorna 200 con shape W9', async ({ page }) => {
    const resp = await page.request.get('/api/inversionista/resumen');
    expect(resp.status()).toBe(200);
    const body = await resp.json();
    // Portfolio (legacy + W9).
    expect(body.portfolio).toHaveProperty('cartera_viva');
    expect(body.portfolio).toHaveProperty('cartera_vencida');
    expect(body.portfolio).toHaveProperty('pct_vencido');
    expect(body.portfolio).toHaveProperty('recaudo_hoy');
    expect(body.portfolio).toHaveProperty('gastos_hoy');
    expect(body.portfolio).toHaveProperty('neto_hoy');
    expect(body.portfolio.neto_hoy).toBe(body.portfolio.recaudo_hoy - body.portfolio.gastos_hoy);
    // Negocio.
    expect(body.negocio).toHaveProperty('nombre');
    expect(body.negocio).toHaveProperty('fecha');
    expect(body.negocio).toHaveProperty('plan');
    // Riesgo.
    expect(body.riesgo).toHaveProperty('clientes_en_mora');
    expect(body.riesgo).toHaveProperty('promesas_activas');
    expect(body.riesgo).toHaveProperty('promesas_incumplidas');
    expect(body.riesgo.aging_distribution).toHaveProperty('CURRENT');
    expect(body.riesgo.aging_distribution).toHaveProperty('90+');
    // Tendencia.
    expect(body.tendencia_7d.serie).toHaveLength(7);
    expect(body.tendencia_7d.total_neto).toBe(
      body.tendencia_7d.serie.reduce((s: number, d: { neto: number }) => s + d.neto, 0),
    );
    // Rutas (exposición, PII minimizada).
    expect(Array.isArray(body.rutas)).toBe(true);
    for (const r of body.rutas) {
      expect(r).toHaveProperty('ruta_nombre');
      expect(r).toHaveProperty('cartera');
      expect(r).toHaveProperty('vencido');
      expect(r).toHaveProperty('creditos');
      expect(r).not.toHaveProperty('cobrador_nombre');
      expect(r).not.toHaveProperty('cobrador_id');
    }
  });

  test('INV: PII ausente en el resumen (sin nombres de cliente ni cobrador)', async ({ page }) => {
    const resp = await page.request.get('/api/inversionista/resumen');
    expect(resp.status()).toBe(200);
    const raw = JSON.stringify(await resp.json());
    // El fixture de rutas no incluye cobrador; ni hay nombres de cliente.
    expect(raw).not.toContain('Cobrador');
    expect(raw).not.toContain('cobrador_nombre');
  });
});

test.describe('W9 E2E: INVERSIONISTA - navegación por capabilities', () => {
  test.beforeEach(async ({ page }) => {
    await setSessionToken(page, 'test-token');
  });

  test('INV: sidebar muestra Reportes, Créditos, Cobranza, Centro Financiero, Rutas', async ({ page }) => {
    await page.goto('/dashboard');
    await expect(page.getByRole('button', { name: 'Reportes' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Créditos' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Centro de Cobranza' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Centro Financiero' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Rutas' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Suscripción' })).toBeVisible();
  });

  test('INV: navegación a Reportes, Créditos, Cobranza, Centro Financiero, Rutas', async ({ page }) => {
    await page.goto('/dashboard');
    await page.getByRole('button', { name: 'Reportes' }).click();
    await expect(page).toHaveURL(/\/reportes/);
    await page.getByRole('button', { name: 'Créditos' }).click();
    await expect(page).toHaveURL(/\/creditos/);
    await page.getByRole('button', { name: 'Centro de Cobranza' }).click();
    await expect(page).toHaveURL(/\/cobranza/);
    await page.getByRole('button', { name: 'Centro Financiero' }).click();
    await expect(page).toHaveURL(/\/movimientos/);
    await page.getByRole('button', { name: 'Rutas' }).click();
    await expect(page).toHaveURL(/\/routes/);
  });

  test('INV: sin superficies de mutación (Caja es COBRADOR-only)', async ({ page }) => {
    await page.goto('/dashboard');
    await expect(page.getByRole('button', { name: 'Caja' })).toHaveCount(0);
    await expect(page.getByRole('button', { name: 'Usuarios' })).toHaveCount(0);
    await expect(page.getByRole('button', { name: 'Dispositivos' })).toHaveCount(0);
    await expect(page.getByRole('button', { name: 'Auditoría' })).toHaveCount(0);
    await expect(page.getByRole('button', { name: 'Clientes' })).toHaveCount(0);
  });
});

test.describe('W9 E2E: INVERSIONISTA - direct URLs administrativas bloqueadas', () => {
  test.beforeEach(async ({ page }) => {
    await setSessionToken(page, 'test-token');
  });

  for (const path of ['/clientes', '/usuarios', '/auditoria', '/dispositivos', '/caja']) {
    test(`INV: direct URL ${path} -> Acceso denegado (403 controlado)`, async ({ page }) => {
      await page.goto(path);
      await expect(page.getByRole('heading', { name: 'Acceso denegado' })).toBeVisible();
    });
  }
});

test.describe('W9 E2E: INVERSIONISTA - accesibilidad', () => {
  test('INV: dashboard accesible por teclado', async ({ page }) => {
    await setSessionToken(page, 'test-token');
    await page.goto('/dashboard');
    await page.keyboard.press('Tab');
    await expect(page.locator(':focus-visible')).toBeVisible();
  });

  test('INV: /dashboard pasa axe (WCAG 2.2 AA)', async ({ page }) => {
    await setSessionToken(page, 'test-token');
    await page.goto('/dashboard');
    await expect(page.getByRole('heading', { name: 'Dashboard financiero' })).toBeVisible();
    const { default: AxeBuilder } = await import('@axe-core/playwright');
    const results = await new AxeBuilder({ page }).include('main').analyze();
    const serious = results.violations.filter((v) => v.impact === 'critical' || v.impact === 'serious');
    expect(serious, JSON.stringify(serious, null, 2)).toHaveLength(0);
  });
});
