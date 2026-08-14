import { test, expect, type Page } from '@playwright/test';

/**
 * E2E de LOGIN REAL multi-rol (Commit 6) — sin inyección de token: el browser
 * ejecuta el flujo completo de dispositivo contra el mock endurecido:
 *   LoginPage -> /api/auth/web/activar (desafio daily-v1) ->
 *   /api/auth/web/canjear (canjear + primer desafio daily-auth-v1, bootstrap en
 *   memoria del BFF) -> firma WebCrypto en IndexedDB -> /api/auth/session
 *   (setea cookie httpOnly) -> /dashboard.
 *
 * Se prueba con los 3 códigos por rol y se afirma la superficie de navegación
 * que el backend resuelve por capabilities (el rol nunca viaja en el token).
 *
 * La inyección directa de token (rbac-roles.spec.ts) se mantiene como auxilio
 * SOLO para casos que no requieren login (p.ej. forzar un rol concreto), pero
 * el camino productivo de login pasa por aquí.
 */

const CODES = [
  { code: 'test-cobrador-code', rol: 'COBRADOR', hasCaja: true, hasReportes: false },
  { code: 'test-inversor-code', rol: 'INVERSIONISTA', hasCaja: false, hasReportes: true },
  { code: 'test-admin-code', rol: 'ADMINISTRADOR', hasCaja: false, hasReportes: true },
];

test.describe('Login real UI -> superficie por rol', () => {
  test.beforeEach(async ({ page }) => {
    await page.context().clearCookies();
    await page.goto('/');
  });

  for (const { code, rol, hasCaja, hasReportes } of CODES) {
    test(`login real con código ${code} -> superficie ${rol}`, async ({ page }) => {
      await test.step('LoginPage presenta el formulario', async () => {
        await expect(page.locator('#loginTitle')).toBeVisible();
        await expect(page.locator('#activationCode')).toBeVisible();
      });

      await test.step('El browser ejecuta el flujo de dispositivo (WebCrypto)', async () => {
        await loginReal(page, code);
        // loginWithCode setea la cookie httpOnly y navega a /dashboard.
        await expect(page.locator('h1')).toBeVisible({ timeout: 15000 });
      });

      await test.step('La navegación refleja las capabilities del rol', async () => {
        const caja = page.getByRole('button', { name: 'Caja' });
        const reportes = page.getByRole('button', { name: 'Reportes' });
        if (hasCaja) await expect(caja).toBeVisible();
        else await expect(caja).toHaveCount(0);
        if (hasReportes) await expect(reportes).toBeVisible();
        else await expect(reportes).toHaveCount(0);
      });

      await test.step('/api/auth/me resuelve el rol del backend', async () => {
        const me = await page.request.get('http://localhost:8100/api/auth/me', {
          headers: { Authorization: `Bearer ${await cookieToken(page)}` },
        });
        expect(me.status()).toBe(200);
        expect((await me.json()).rol).toBe(rol);
      });
    });
  }

  test('cerrar sesión borra la cookie y vuelve al login', async ({ page }) => {
    await page.locator('#activationCode').fill('test-cobrador-code');
    await page.locator('#loginBtn').click();
    await page.waitForURL('**/dashboard', { timeout: 30000 });

    await page.getByRole('button', { name: 'Cerrar sesión' }).click();
    await page.waitForURL('/', { timeout: 15000 });
    await expect(page.locator('#loginTitle')).toBeVisible();
  });
});

// El httpOnly cookie no es legible desde el DOM; se lee el token de la cookie
// del contexto para validar /me server-side en el assertion final.
async function cookieToken(page: Page): Promise<string> {
  const cookies = await page.context().cookies();
  const c = cookies.find((x) => x.name === 'daily_admin_token');
  return c?.value ?? '';
}

// Helper de login real a través de la UI (flujo de dispositivo WebCrypto).
async function loginReal(page: Page, code: string) {
  await page.locator('#activationCode').fill(code);
  await page.locator('#loginBtn').click();
  await page.waitForURL('**/dashboard', { timeout: 30000 });
}
