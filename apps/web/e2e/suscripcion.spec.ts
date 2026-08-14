import { test, expect } from '@playwright/test';
import { setSessionToken } from './helpers/session';

test.describe('Suscripción (Etapa 3)', () => {
  test('INVERSIONISTA: renderiza estado activa con plan y vigencia', async ({ page }) => {
    await setSessionToken(page);
    await page.goto('/suscripcion');
    await expect(page.locator('h1')).toContainText('Suscripción');
    await expect(page.locator('.badge-success')).toContainText('Activa');
    await expect(page.locator('.badge-success')).toBeVisible();
    await expect(page.locator('body')).toContainText('basic');
    await expect(page.locator('body')).toContainText('Hasta el');
  });

  test('INVERSIONISTA: suscripción vencida -> estado Vencida', async ({ page }) => {
    await setSessionToken(page, 'mock-vencida');
    await page.goto('/suscripcion');
    await expect(page.locator('.badge-danger')).toContainText('Vencida');
    await expect(page.locator('body')).toContainText('Tu suscripción venció');
  });

  test('INVERSIONISTA: sin suscripción -> estado No activa', async ({ page }) => {
    await setSessionToken(page, 'mock-sin-suscripcion');
    await page.goto('/suscripcion');
    await expect(page.locator('.badge-warning')).toContainText('No activa');
  });

  test('COBRADOR: 403 controlado, sin redirect silencioso al login', async ({ page }) => {
    await setSessionToken(page, 'mock-jwt-token');
    await page.goto('/suscripcion');
    await expect(page.locator('h1')).toContainText('Acceso denegado');
    await expect(page).toHaveURL(/\/suscripcion/);
  });

  test('error transitorio (500): flash recuperable con reintento', async ({ page }) => {
    await setSessionToken(page, 'mock-error');
    await page.goto('/suscripcion');
    await expect(page.locator('.flash-error')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Reintentar' })).toBeVisible();
  });

  test('navegación: ítem Suscripción visible solo para INVERSIONISTA/ADMINISTRADOR', async ({ page }) => {
    await setSessionToken(page);
    await page.goto('/dashboard');
    await expect(page.getByRole('button', { name: 'Suscripción' })).toBeVisible();
    await page.getByRole('button', { name: 'Suscripción' }).click();
    await expect(page).toHaveURL(/\/suscripcion/);
    await expect(page.locator('.badge-success')).toBeVisible();
  });

  test('navegación: COBRADOR no ve el ítem Suscripción', async ({ page }) => {
    await setSessionToken(page, 'mock-jwt-token');
    await page.goto('/dashboard');
    await expect(page.getByRole('button', { name: 'Suscripción' })).toHaveCount(0);
  });
});
