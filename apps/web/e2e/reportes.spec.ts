import { test, expect } from '@playwright/test';
import { setSessionToken } from './helpers/session';

test.describe('Reportes', () => {
  const mockData = {
    portfolio: { total_creditos_activos: 50, cartera_neta: 5000000, recaudo_hoy: 800000 },
    negocio_nombre: 'Test',
    plan: 'basic',
    moneda: 'COP',
  };

  test('reportes renders', async ({ page }) => {
    await page.route('**/api/inversionista/resumen', async (route) => {
      await route.fulfill({ status: 200, json: mockData });
    });
    await setSessionToken(page);
    await page.goto('/reportes');
    await expect(page.locator('h1')).toContainText('Reportes');
    await expect(page.locator('.metric-value')).toHaveCount(4);
  });

  test('reportes shows portfolio data', async ({ page }) => {
    await page.route('**/api/inversionista/resumen', async (route) => {
      await route.fulfill({ status: 200, json: mockData });
    });
    await setSessionToken(page);
    await page.goto('/reportes');
    await expect(page.locator('.metric-value').first()).toContainText('50');
  });

  test('reportes API error', async ({ page }) => {
    await page.route('**/api/inversionista/resumen', async (route) => {
      await route.fulfill({ status: 500, json: { detail: 'Error' } });
    });
    await setSessionToken(page);
    await page.goto('/reportes');
    await expect(page.locator('.flash-error')).toBeVisible();
  });
});