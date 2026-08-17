import { test, expect } from '@playwright/test';
import { setSessionToken } from './helpers/session';

/**
 * W5 — Centro Financiero: Movimientos (Web Premium, mock real via mock-api.mjs).
 *
 * Contrato (mock replica del FastAPI real):
 *  - GET /api/movimientos/web     envelope {items,total,limit,offset} con filtros
 *                                (q, tipo, naturaleza, ruta_id), sort, paginación
 *  - GET /api/movimientos/resumen agregados (total_movimientos, total_monto,
 *                                gastos_por_tipo)
 *  - RBAC: movimientos:ver (ADMINISTRADOR | INVERSIONISTA) | COBRADOR scoped
 *  - INVERSIONISTA: PII minimizada (creado_por_nombre → null)
 *  - COBRADOR: scoped a su ruta activa
 */

const MOCK = `http://localhost:${process.env.MOCK_API_PORT || 8100}`;

test.describe.configure({ mode: 'serial' });

test.describe('W5 E2E: ADMINISTRADOR - Movimientos', () => {
  test.beforeEach(async ({ page }) => {
    await setSessionToken(page, 'mock-admin');
  });

  test('ADMIN ve Centro Financiero con resumen y tabla de movimientos', async ({ page }) => {
    await page.goto('/movimientos');

    await expect(page.getByRole('heading', { name: 'Centro Financiero' })).toBeVisible();

    // Resumen cards
    await expect(page.getByText('Total movimientos')).toBeVisible();
    await expect(page.getByText('Total monto')).toBeVisible();

    // Tabla con movimientos
    const tabla = page.getByRole('table');
    await expect(tabla).toContainText('GASOLINA');
    await expect(tabla).toContainText('OFICINA');
    await expect(tabla).toContainText('RECIBIDO');
    await expect(tabla).toContainText('Ruta Centro');
    await expect(tabla).toContainText('Ruta Sur');
  });

  test('ADMIN filtra por naturaleza GASTO', async ({ page }) => {
    await page.goto('/movimientos');
    await page.waitForTimeout(500);

    await page.locator('#mov-naturaleza').selectOption('GASTO');
    await page.waitForTimeout(500);

    const tabla = page.getByRole('table');
    await expect(tabla).toContainText('GASOLINA');
    await expect(tabla).toContainText('OFICINA');
    await expect(tabla).toContainText('COMBUSTIBLE');
    // RECIBIDO es CUENTA_POR_COBRAR, no GASTO
    const rows = tabla.getByRole('row');
    const count = await rows.count();
    // Header + 3 gastos (GASOLINA, OFICINA, COMBUSTIBLE)
    expect(count).toBe(4);
  });

  test('ADMIN filtra por ruta', async ({ page }) => {
    await page.goto('/movimientos');
    await page.waitForTimeout(500);

    await page.locator('#mov-ruta').selectOption({ label: 'Ruta Centro' });
    await page.waitForTimeout(500);

    const tabla = page.getByRole('table');
    await expect(tabla).toContainText('Ruta Centro');
    const rows = tabla.getByRole('row');
    const count = await rows.count();
    // Header + 3 movimientos de Ruta Centro
    expect(count).toBe(4);
  });

  test('ADMIN cambia orden a monto ascendente', async ({ page }) => {
    await page.goto('/movimientos');
    await page.waitForTimeout(500);

    await page.locator('#mov-sort').selectOption('monto');
    await page.locator('#mov-order').selectOption('asc');
    await page.waitForTimeout(500);

    const tabla = page.getByRole('table');
    const rows = tabla.getByRole('row').filter({ hasText: /GASOLINA|OFICINA|RECIBIDO|COMBUSTIBLE/ });
    const firstRow = rows.first();
    // El monto más bajo es 20000 (OFICINA)
    await expect(firstRow).toContainText('OFICINA');
  });

  test('ADMIN busca por nota', async ({ page }) => {
    await page.goto('/movimientos');
    await page.waitForTimeout(500);

    await page.locator('#mov-search').fill('Gasolina');
    await page.locator('#mov-search').press('Enter');
    await page.waitForTimeout(500);

    const tabla = page.getByRole('table');
    await expect(tabla).toContainText('Gasolina ruta centro');
    const rows = tabla.getByRole('row').filter({ hasText: /GASOLINA|OFICINA|RECIBIDO|COMBUSTIBLE/ });
    const count = await rows.count();
    expect(count).toBe(1);
  });
});

test.describe('W5 E2E: INVERSIONISTA - Movimientos (PII minimizada)', () => {
  test.beforeEach(async ({ page }) => {
    await setSessionToken(page, 'test-token');
  });

  test('INVERSIONISTA ve movimientos sin nombre de cobrador', async ({ page }) => {
    await page.goto('/movimientos');

    await expect(page.getByRole('heading', { name: 'Centro Financiero' })).toBeVisible();

    const tabla = page.getByRole('table');
    await expect(tabla).toContainText('GASOLINA');

    // PII minimizada: no debe mostrar nombres de cobradores
    const rows = tabla.getByRole('row');
    const count = await rows.count();
    for (let i = 1; i < count; i++) {
      const row = rows.nth(i);
      await expect(row).not.toContainText('Carlos M.');
      await expect(row).not.toContainText('Ana P.');
    }
  });
});

test.describe('W5 E2E: COBRADOR - Movimientos (scoped)', () => {
  test.beforeEach(async ({ page }) => {
    await setSessionToken(page, 'test-cobrador-code');
  });

  test('COBRADOR ve solo movimientos de su ruta', async ({ page }) => {
    await page.goto('/movimientos');

    await expect(page.getByRole('heading', { name: 'Centro Financiero' })).toBeVisible();

    const tabla = page.getByRole('table');
    // mock-cobrador tiene route_id r1 (Ruta Centro)
    await expect(tabla).toContainText('Ruta Centro');
    // No debe ver Ruta Sur
    const rows = tabla.getByRole('row');
    const count = await rows.count();
    for (let i = 1; i < count; i++) {
      const row = rows.nth(i);
      await expect(row).not.toContainText('Ruta Sur');
    }
  });
});
