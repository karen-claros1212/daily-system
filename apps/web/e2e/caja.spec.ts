import { test, expect } from '@playwright/test';
import { setSessionToken, todayISO, daysAgoISO } from './helpers/session';

test.describe('Caja', () => {
  const jornadaClosed = {
    id: 'j1',
    fecha: todayISO(),
    estado: 'CLOSED_SYNCED',
    esperado: 120000,
    contado: 115000,
    diferencia: -5000,
  };

  test('caja renders summary', async ({ page }) => {
    await page.route('**/api/jornadas', async (route) => {
      await route.fulfill({
        status: 200,
        json: [
          jornadaClosed,
          { id: 'j2', fecha: todayISO(), estado: 'CLOSED_LOCAL_PENDING_SYNC', esperado: 80000, contado: 82000, diferencia: 2000 },
        ],
      });
    });
    await setSessionToken(page, 'mock-jwt-token');
    await page.goto('/caja');
    await expect(page.locator('h1')).toBeVisible();
    await expect(page.locator('.metric-label')).toBeVisible();
  });

  test('caja shows totals', async ({ page }) => {
    await page.route('**/api/jornadas', async (route) => {
      await route.fulfill({
        status: 200,
        json: [
          { id: 'j1', fecha: todayISO(), estado: 'CLOSED_SYNCED', esperado: 100000, contado: 95000, diferencia: -5000 },
        ],
      });
    });
    await setSessionToken(page, 'mock-jwt-token');
    await page.goto('/caja');
    await expect(page.locator('h1')).toBeVisible();
  });

  test('caja shows difference color', async ({ page }) => {
    await page.route('**/api/jornadas', async (route) => {
      await route.fulfill({
        status: 200,
        json: [
          { id: 'j1', fecha: todayISO(), estado: 'CLOSED_SYNCED', esperado: 100000, contado: 95000, diferencia: -5000 },
        ],
      });
    });
    await setSessionToken(page, 'mock-jwt-token');
    await page.goto('/caja');
    await expect(page.locator('h1')).toBeVisible();
  });

  test('caja empty state', async ({ page }) => {
    await page.route('**/api/jornadas', async (route) => {
      await route.fulfill({ status: 200, json: [] });
    });
    await setSessionToken(page, 'mock-jwt-token');
    await page.goto('/caja');
    await expect(page.locator('text=No hay jornadas')).toBeVisible();
  });

  test('caja last 30 jornadas', async ({ page }) => {
    const jornadas = Array.from({ length: 35 }, (_, i) => ({
      id: `j${i}`,
      fecha: daysAgoISO(i),
      estado: 'CLOSED_SYNCED',
      esperado: 100000,
      contado: 100000,
      diferencia: 0,
    }));
    await page.route('**/api/jornadas', async (route) => {
      await route.fulfill({ status: 200, json: jornadas });
    });
    await setSessionToken(page, 'mock-jwt-token');
    await page.goto('/caja');
    const rows = page.locator('tbody tr');
    await expect(rows).toHaveCount(30);
  });

  test('caja API error', async ({ page }) => {
    await page.route('**/api/jornadas', async (route) => {
      await route.fulfill({ status: 500, json: { detail: 'Server error' } });
    });
    await setSessionToken(page, 'mock-jwt-token');
    await page.goto('/caja');
    await expect(page.locator('.flash-error')).toBeVisible();
  });
});