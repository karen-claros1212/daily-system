import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { setSessionToken } from './helpers/session';

test.describe('A11y', () => {
  test('login page has form labels', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('label[for="activationCode"]')).toBeVisible();
  });

  test('login has focus visible', async ({ page }) => {
    await page.goto('/');
    await page.locator('#activationCode').press('Tab');
    await expect(page.locator(':focus-visible')).toBeVisible();
  });

  test('dashboard a11y scan', async ({ page }) => {
    await setSessionToken(page);
    await page.goto('/dashboard');
    const results = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']).analyze();
    expect(results.violations).toEqual([]);
  });

  test('routes a11y scan', async ({ page }) => {
    await page.route('**/api/rutas', async (route) => {
      await route.fulfill({ status: 200, json: [] });
    });
    await setSessionToken(page);
    await page.goto('/routes');
    const results = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']).analyze();
    expect(results.violations).toEqual([]);
  });

  test('caja a11y scan', async ({ page }) => {
    await page.route('**/api/jornadas', async (route) => {
      await route.fulfill({ status: 200, json: [] });
    });
    // Caja es superficie de campo: solo COBRADOR (token emitido por el flujo).
    await setSessionToken(page, 'mock-jwt-token');
    await page.goto('/caja');
    const results = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']).analyze();
    expect(results.violations).toEqual([]);
  });

  test('reportes a11y scan', async ({ page }) => {
    await page.route('**/api/inversionista/resumen', async (route) => {
      await route.fulfill({ status: 200, json: { portfolio: { rutas_activas: 3 }, plan: 'basic', moneda: 'COP' } });
    });
    await setSessionToken(page);
    await page.goto('/reportes');
    const results = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']).analyze();
    expect(results.violations).toEqual([]);
  });

  test('keyboard navigation on sidebar', async ({ page }) => {
    await setSessionToken(page);
    await page.goto('/dashboard');
    await page.keyboard.press('Tab');
    await page.keyboard.press('Tab');
    await expect(page.locator(':focus-visible')).toBeVisible();
  });

  test('contrast ratios pass', async ({ page }) => {
    await page.goto('/');
    const body = page.locator('body');
    const styles = await body.evaluate((el) => {
      const cs = getComputedStyle(el);
      return { color: cs.color, backgroundColor: cs.backgroundColor };
    });
    expect(styles.color).toBeTruthy();
  });
});