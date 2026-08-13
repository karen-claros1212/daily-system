import { test, expect } from '@playwright/test';

const ACTIVATION_CODE = 'test-activation-code';

test.describe('Auth', () => {
  test('login page renders without token', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('#loginTitle')).toBeVisible();
    await expect(page.locator('#activationCode')).toBeVisible();
    await expect(page.locator('#loginBtn')).toBeVisible();
  });

  test('login fails with empty fields', async ({ page }) => {
    await page.goto('/');
    await page.locator('#loginBtn').click();
    await expect(page.locator('#loginError')).toBeVisible();
  });

  test('login succeeds with valid activation code (flujo real contra mock)', async ({ page }) => {
    await page.goto('/');
    await page.locator('#activationCode').fill(ACTIVATION_CODE);
    await page.locator('#loginBtn').click();
    // El flujo completo: desafio activacion -> firma WebCrypto -> canjear ->
    // desafio sesion (bootstrap server-side) -> firma daily-auth-v1 -> canjear
    // sesion -> cookie HttpOnly -> dashboard autenticado.
    await expect(page.locator('.metric-card').first()).toBeVisible({ timeout: 10000 });
  });

  test('login rejects invalid activation code', async ({ page }) => {
    await page.goto('/');
    await page.locator('#activationCode').fill('codigo-invalido');
    await page.locator('#loginBtn').click();
    await expect(page.locator('#loginError')).toBeVisible();
  });

  test('401 redirects to login', async ({ page }) => {
    await page.goto('/dashboard');
    await expect(page.locator('#loginTitle')).toBeVisible();
  });

  test('403 shows flash error', async ({ page }) => {
    await page.route('**/api/auth/session', async (route) => {
      if (route.request().method() !== 'OPTIONS') {
        await route.fulfill({
          status: 403,
          json: { detail: 'Suscripcion vencida' },
        });
      } else {
        await route.continue();
      }
    });
    await page.goto('/');
    await page.locator('#activationCode').fill(ACTIVATION_CODE);
    await page.locator('#loginBtn').click();
    await expect(page.locator('#loginError')).toBeVisible();
  });

  test('logout clears token', async ({ page }) => {
    await page.goto('/');
    await page.locator('#activationCode').fill(ACTIVATION_CODE);
    await page.locator('#loginBtn').click();
    await expect(page.locator('.metric-card').first()).toBeVisible({ timeout: 10000 });
    await page.getByRole('button', { name: 'Cerrar sesión' }).click();
    await expect(page.locator('#loginTitle')).toBeVisible();
  });
});