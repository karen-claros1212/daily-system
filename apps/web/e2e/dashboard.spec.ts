import { test, expect } from '@playwright/test';

const TOKEN = 'test-token';

function setToken(page: import('@playwright/test').Page, value: string) {
  return page.context().addCookies([
    { url: 'http://localhost:3000', name: 'daily_admin_token', value },
  ]);
}

test.describe('Dashboard', () => {
  test('dashboard renders metrics', async ({ page }) => {
    await setToken(page, TOKEN);
    await page.goto('/dashboard');
    await expect(page.locator('h1')).toContainText('Dashboard');
    // W9: 4 KPIs financieros + 4 de riesgo/promesas = 8 cards.
    await expect(page.locator('.metric-card')).toHaveCount(8);
  });

  test('dashboard shows correct values', async ({ page }) => {
    await setToken(page, 'mock-custom');
    await page.goto('/dashboard');
    // W9: primer KPI es Cartera viva (autoridad W6). mock-custom = 10.000.000.
    await expect(page.locator('.metric-value.money').first()).toContainText('10.000.000');
    // Tendencia 7d y exposición por ruta presentes (superficies W9).
    await expect(page.getByRole('heading', { name: 'Tendencia de recaudo (7 días)' })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Exposición por ruta' })).toBeVisible();
  });

  test('dashboard handles empty portfolio', async ({ page }) => {
    await setToken(page, 'mock-empty');
    await page.goto('/dashboard');
    await expect(page.locator('.metric-value').first()).toContainText('0');
  });

  test('dashboard handles API error', async ({ page }) => {
    await setToken(page, 'mock-error');
    await page.goto('/dashboard');
    // Sesión válida (INVERSIONISTA) + 500 del servicio: flash de error,
    // NO un redirect silencioso al login ni una vista de rol.
    await expect(page.locator('.flash-error')).toBeVisible();
  });

  test('sidebar navigation for INVERSIONISTA (financiero)', async ({ page }) => {
    await setToken(page, TOKEN);
    await page.goto('/dashboard');
    await page.getByRole('button', { name: 'Rutas' }).click();
    await expect(page).toHaveURL(/\/routes/);
    await page.getByRole('button', { name: 'Reportes' }).click();
    await expect(page).toHaveURL(/\/reportes/);
    // COBRADOR-only: Caja NO existe para INVERSIONISTA.
    await expect(page.getByRole('button', { name: 'Caja' })).toHaveCount(0);
  });

  test('sidebar navigation for COBRADOR (superficie de campo)', async ({ page }) => {
    // Token emitido por el flujo de dispositivo del mock (contrato real: solo COBRADOR).
    await setToken(page, 'mock-jwt-token');
    await page.goto('/dashboard');
    await expect(page.locator('h1')).toContainText('Mi jornada');
    await page.getByRole('button', { name: 'Rutas' }).click();
    await expect(page).toHaveURL(/\/routes/);
    await page.getByRole('button', { name: 'Caja' }).click();
    await expect(page).toHaveURL(/\/caja/);
    // Reportes (financiero) NO existe para COBRADOR.
    await expect(page.getByRole('button', { name: 'Reportes' })).toHaveCount(0);
  });

  test('dashboard is keyboard accessible', async ({ page }) => {
    await setToken(page, TOKEN);
    await page.goto('/dashboard');
    await page.keyboard.press('Tab');
    await expect(page.locator(':focus-visible')).toBeVisible();
  });
});