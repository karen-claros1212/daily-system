import { test, expect } from '@playwright/test';
import { setSessionToken } from './helpers/session';

/**
 * W7 — Reportes Premium (mock).
 *
 * Contrato (mock replica del FastAPI real):
 *  - GET /api/reportes/resumen      KPIs (cartera, vencida, recaudo, gastos, neto)
 *  - GET /api/reportes/recaudo      serie diaria + totales
 *  - GET /api/reportes/aging        buckets por días de mora
 *  - GET /api/reportes/rutas        rendimiento por ruta
 *  - GET /api/reportes/movimientos  gastos por tipo
 *  - RBAC: reportes:ver (ADMIN + INVERSIONISTA, no COBRADOR)
 *  - INVERSIONISTA: PII minimizada
 *  - Periodos: hoy, 7d, 30d
 */

test.describe.configure({ mode: 'serial' });

test.describe('W7 E2E: ADMINISTRADOR - Reportes Premium', () => {
  test.beforeEach(async ({ page }) => {
    await setSessionToken(page, 'mock-admin');
  });

  test('ADMIN ve KPIs, tendencia, aging, rutas, movimientos', async ({ page }) => {
    await page.goto('/reportes');
    await expect(page.getByRole('heading', { name: 'Reportes' })).toBeVisible();
    await expect(page.getByText('Cartera vigente')).toBeVisible();
    await expect(page.getByText('Cartera vencida')).toBeVisible();
    await expect(page.getByText('Recaudo del periodo')).toBeVisible();
    await expect(page.getByText('Neto del periodo')).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Tendencia de recaudo' })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Aging de cartera' })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Rendimiento por rutas' })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Gastos y movimientos' })).toBeVisible();
  });

  test('tendencia de recaudo muestra barras y totales', async ({ page }) => {
    await page.goto('/reportes');
    await expect(page.getByRole('heading', { name: 'Tendencia de recaudo' })).toBeVisible();
    await expect(page.getByText('Recaudo', { exact: true })).toBeVisible();
    await expect(page.getByText('Reversal', { exact: true })).toBeVisible();
    await expect(page.getByText('Neto', { exact: true })).toBeVisible();
  });

  test('aging muestra buckets con counts', async ({ page }) => {
    await page.goto('/reportes');
    await expect(page.getByRole('heading', { name: 'Aging de cartera' })).toBeVisible();
    await expect(page.getByText('Al día')).toBeVisible();
    await expect(page.getByText('1-7 días')).toBeVisible();
    await expect(page.getByText('8-15 días')).toBeVisible();
  });

  test('rutas muestra tabla con cartera y vencido', async ({ page }) => {
    await page.goto('/reportes');
    await expect(page.getByRole('heading', { name: 'Rendimiento por rutas' })).toBeVisible();
    await expect(page.getByText('Ruta Centro')).toBeVisible();
    await expect(page.getByText('Ruta Norte')).toBeVisible();
    await expect(page.getByText('Ruta Sur')).toBeVisible();
  });

  test('movimientos muestra tabla por tipo', async ({ page }) => {
    await page.goto('/reportes');
    await expect(page.getByRole('heading', { name: 'Gastos y movimientos' })).toBeVisible();
    await expect(page.getByText('TRANSPORTE')).toBeVisible();
    await expect(page.getByText('MATERIALES')).toBeVisible();
  });

  test('KPIs muestran valores en COP', async ({ page }) => {
    await page.goto('/reportes');
    await expect(page.getByText('Cartera vigente')).toBeVisible();
    const kpiCard = page.locator('text=Cartera vigente').locator('..');
    await expect(kpiCard).toContainText('$');
  });

  test('pct_vencido se muestra junto a cartera vencida', async ({ page }) => {
    await page.goto('/reportes');
    await expect(page.getByText(/% de la cartera/)).toBeVisible();
  });

  test('neto_periodo muestra gastos como subtexto', async ({ page }) => {
    await page.goto('/reportes');
    await expect(page.getByText(/Gastos:/)).toBeVisible();
  });

  test('selector de periodo es accesible (id + enabled)', async ({ page }) => {
    await page.goto('/reportes');
    const select = page.locator('#rep-periodo');
    await expect(select).toBeVisible();
    await expect(select).toBeEnabled();
  });

  test('selector de periodo cambia datos sin error', async ({ page }) => {
    await page.goto('/reportes');
    await expect(page.getByText('Cartera vigente')).toBeVisible();
    await page.selectOption('#rep-periodo', '7d');
    await page.waitForTimeout(500);
    await expect(page.getByText('Cartera vigente')).toBeVisible();
  });
});

test.describe('W7 E2E: INVERSIONISTA - Reportes Premium', () => {
  test.beforeEach(async ({ page }) => {
    await setSessionToken(page, 'test-token');
  });

  test('INVERSIONISTA ve reportes (PII minimizada)', async ({ page }) => {
    await page.goto('/reportes');
    await expect(page.getByRole('heading', { name: 'Reportes' })).toBeVisible();
    await expect(page.getByText('Cartera vigente')).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Tendencia de recaudo' })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Aging de cartera' })).toBeVisible();
  });
});

test.describe('W7 E2E: COBRADOR - Reportes Premium (403)', () => {
  test('COBRADOR sin reportes:ver ve 403', async ({ page }) => {
    await setSessionToken(page, 'test-cobrador-code');
    await page.goto('/reportes');
    await expect(page.getByText(/403|No autorizado|acceso/i)).toBeVisible();
  });
});
