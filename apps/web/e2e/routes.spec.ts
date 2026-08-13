import { test, expect } from '@playwright/test';
import { setSessionToken, todayISO } from './helpers/session';

test.describe('Routes', () => {
  const mockRoutes = [
    { id: 'r1', nombre: 'Ruta Norte', cobrador_nombre: 'Carlos M.', activa: true, version: 1 },
    { id: 'r2', nombre: 'Ruta Sur', cobrador_nombre: 'Ana P.', activa: false, version: 2 },
  ];

  test('routes list renders', async ({ page }) => {
    await page.route('**/api/rutas', async (route) => {
      await route.fulfill({ status: 200, json: mockRoutes });
    });
    await setSessionToken(page);
    await page.goto('/routes');
    await expect(page.locator('h1')).toBeVisible();
    await expect(page.locator('.badge').first()).toBeVisible();
  });

  test('route detail shows jornada', async ({ page }) => {
    await page.route('**/api/rutas/r1', async (route) => {
      await route.fulfill({ status: 200, json: { id: 'r1', nombre: 'Ruta Norte', cobrador_nombre: 'Carlos M.', activa: true, version: 1 } });
    });
    await page.route('**/api/jornadas', async (route) => {
      await route.fulfill({ status: 200, json: [{ id: 'j1', fecha: todayISO(), estado: 'CLOSED_SYNCED', esperado: 120000, contado: 115000, diferencia: -5000 }] });
    });
    await page.route('**/api/rutas', async (route) => {
      await route.fulfill({ status: 200, json: mockRoutes });
    });
    await setSessionToken(page);
    await page.goto('/routes');
    await page.locator('button:has-text("Ver detalle")').first().click();
    await expect(page.locator('h2')).toBeVisible();
  });

  test('route detail shows no jornada', async ({ page }) => {
    await page.route('**/api/rutas/r1', async (route) => {
      await route.fulfill({ status: 200, json: { id: 'r1', nombre: 'Ruta Norte', cobrador_nombre: 'Carlos M.', activa: true, version: 1 } });
    });
    await page.route('**/api/jornadas', async (route) => {
      await route.fulfill({ status: 200, json: [] });
    });
    await page.route('**/api/rutas', async (route) => {
      await route.fulfill({ status: 200, json: mockRoutes });
    });
    await setSessionToken(page);
    await page.goto('/routes');
    await page.locator('button:has-text("Ver detalle")').first().click();
    await expect(page.locator('text=No hay jornada')).toBeVisible();
  });

  test('back button returns to list', async ({ page }) => {
    await page.route('**/api/rutas/r1', async (route) => {
      await route.fulfill({ status: 200, json: { id: 'r1', nombre: 'Ruta Norte', cobrador_nombre: 'Carlos M.', activa: true, version: 1 } });
    });
    await page.route('**/api/jornadas', async (route) => {
      await route.fulfill({ status: 200, json: [] });
    });
    await page.route('**/api/rutas', async (route) => {
      await route.fulfill({ status: 200, json: mockRoutes });
    });
    await setSessionToken(page);
    await page.goto('/routes');
    await page.locator('button:has-text("Ver detalle")').first().click();
    await page.locator('button:has-text("Volver")').click();
    await expect(page.locator('h1')).toBeVisible();
  });

  test('routes empty state', async ({ page }) => {
    await page.route('**/api/rutas', async (route) => {
      await route.fulfill({ status: 200, json: [] });
    });
    await setSessionToken(page);
    await page.goto('/routes');
    await expect(page.locator('text=No hay rutas')).toBeVisible();
  });

  test('routes API error', async ({ page }) => {
    await page.route('**/api/rutas', async (route) => {
      await route.fulfill({ status: 500, json: { detail: 'Server error' } });
    });
    await setSessionToken(page);
    await page.goto('/routes');
    await expect(page.locator('.flash-error')).toBeVisible();
  });
});