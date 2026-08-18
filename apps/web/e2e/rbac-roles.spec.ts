import { test, expect } from '@playwright/test';
import { setSessionToken } from './helpers/session';

// ─── E2E de separación RBAC por rol (Gate: cierre por rol).
//
// Evidencia explícita de que el web NO colapsa roles: la identidad sale de
// /api/auth/me (el mock replica src/rbac.py; el backend real es la autoridad),
// la navegación se construye por capabilities y una sesión válida con
// permisos insuficientes recibe vista 403 controlada (Forbidden) — NUNCA un
// 401 ni un redirect silencioso al login.
//
// Tokens del mock (rol derivado de la "DB" del mock, nunca del token):
//   - mock-jwt-token  -> COBRADOR (emitido por el flujo de dispositivo)
//   - test-token      -> INVERSIONISTA
//   - mock-admin      -> ADMINISTRADOR

const MOCK = `http://localhost:${process.env.MOCK_API_PORT || 8100}`;
const RUTA_ME = '/api/auth/me';
const RUTA_RESUMEN = '/api/inversionista/resumen';

test.describe('RBAC: separación por rol', () => {
  test.describe('COBRADOR (flujo de dispositivo)', () => {
    test('me resuelve rol COBRADOR con capabilities de campo, sin financiero', async ({ page }) => {
      await setSessionToken(page, 'mock-jwt-token');
      const me = await page.request.get(RUTA_ME);
      expect(me.status()).toBe(200);
      const j = await me.json();
      expect(j.rol).toBe('COBRADOR');
      expect(j.capabilities).toContain('jornada:ver');
      expect(j.capabilities).toContain('ruta:ver');
      expect(j.capabilities).not.toContain('inversionista:resumen');
    });

    test('/caja y /routes están permitidos (capabilities de campo)', async ({ page }) => {
      await setSessionToken(page, 'mock-jwt-token');
      await page.goto('/caja');
      await expect(page.locator('h1')).toBeVisible();
      await page.goto('/routes');
      await expect(page.locator('h1')).toBeVisible();
    });

    test('el endpoint financiero responde 403 fail-closed (no 401)', async ({ page }) => {
      const res = await page.request.get(`${MOCK}${RUTA_RESUMEN}`, {
        headers: { Authorization: 'Bearer mock-jwt-token' },
      });
      expect(res.status()).toBe(403);
      const body = await res.json();
      expect(body.detail).toContain('Forbidden');
    });

    test('/reportes es vista 403 controlada, sin redirect al login', async ({ page }) => {
      await setSessionToken(page, 'mock-jwt-token');
      await page.goto('/reportes');
      await expect(page.locator('h1')).toContainText('Acceso denegado');
      // Sesión válida con permisos insuficientes: permanece en /reportes.
      await expect(page).toHaveURL(/\/reportes/);
      // La superficie de campo sí existe (sin financiero).
      await expect(page.getByRole('button', { name: 'Caja' })).toBeVisible();
      await expect(page.getByRole('button', { name: 'Reportes' })).toHaveCount(0);
    });
  });

  test.describe('INVERSIONISTA', () => {
    test('me resuelve rol INVERSIONISTA con capabilities financieras, sin operación de campo', async ({ page }) => {
      await setSessionToken(page, 'test-token');
      const me = await page.request.get(RUTA_ME);
      expect(me.status()).toBe(200);
      const j = await me.json();
      expect(j.rol).toBe('INVERSIONISTA');
      expect(j.capabilities).toContain('inversionista:resumen');
      expect(j.capabilities).toContain('jornadas:ver');
      expect(j.capabilities).not.toContain('jornada:ver');
      expect(j.capabilities).not.toContain('jornada:abrir');
    });

    test('/reportes y /routes están permitidos; /dashboard es financiero', async ({ page }) => {
      await setSessionToken(page, 'test-token');
      await page.goto('/dashboard');
      await expect(page.locator('h1')).toContainText('Dashboard');
      // W9: dashboard inversionista = 4 KPIs + 4 riesgo/promesas = 8 cards.
      await expect(page.locator('.metric-card')).toHaveCount(8);
      await page.goto('/reportes');
      await expect(page.locator('h1')).toContainText('Reportes');
      await page.goto('/routes');
      await expect(page.locator('h1')).toBeVisible();
    });

    test('el endpoint financiero responde 200', async ({ page }) => {
      const res = await page.request.get(`${MOCK}${RUTA_RESUMEN}`, {
        headers: { Authorization: 'Bearer test-token' },
      });
      expect(res.status()).toBe(200);
    });

    test('/caja es vista 403 controlada (solo COBRADOR tiene jornada:ver)', async ({ page }) => {
      await setSessionToken(page, 'test-token');
      await page.goto('/caja');
      await expect(page.locator('h1')).toContainText('Acceso denegado');
      await expect(page).toHaveURL(/\/caja/);
      // Sin botón de campo: Caja no existe para INVERSIONISTA.
      await expect(page.getByRole('button', { name: 'Caja' })).toHaveCount(0);
      await expect(page.getByRole('button', { name: 'Reportes' })).toBeVisible();
    });
  });

  test.describe('ADMINISTRADOR', () => {
    test('me resuelve rol ADMINISTRADOR con capabilities de supervisión (superpone, no hereda campo)', async ({ page }) => {
      await setSessionToken(page, 'mock-admin');
      const me = await page.request.get(RUTA_ME);
      expect(me.status()).toBe(200);
      const j = await me.json();
      expect(j.rol).toBe('ADMINISTRADOR');
      expect(j.capabilities).toContain('inversionista:resumen');
      expect(j.capabilities).toContain('rutas:ver');
      expect(j.capabilities).toContain('rutas:crear');
      expect(j.capabilities).toContain('codigos:crear');
      expect(j.capabilities).toContain('dispositivos:registrar');
      // El admin NO hereda la superficie de campo (jornada:ver es de COBRADOR).
      expect(j.capabilities).not.toContain('jornada:ver');
      expect(j.capabilities).not.toContain('jornada:abrir');
    });

    test('/reportes y /routes están permitidos; /dashboard es financiero', async ({ page }) => {
      await setSessionToken(page, 'mock-admin');
      await page.goto('/dashboard');
      await expect(page.locator('h1')).toContainText('Dashboard');
      await page.goto('/reportes');
      await expect(page.locator('h1')).toContainText('Reportes');
      await page.goto('/routes');
      await expect(page.locator('h1')).toBeVisible();
    });

    test('/caja es vista 403 controlada para ADMINISTRADOR (jornada:ver es exclusivo de COBRADOR)', async ({ page }) => {
      await setSessionToken(page, 'mock-admin');
      await page.goto('/caja');
      await expect(page.locator('h1')).toContainText('Acceso denegado');
      await expect(page).toHaveURL(/\/caja/);
      await expect(page.getByRole('button', { name: 'Caja' })).toHaveCount(0);
    });
  });

  test.describe('Contrato de sesión', () => {
    test('sin sesión: /api/auth/me -> 401 y la página redirige al login (sesión inexistente)', async ({ page }) => {
      const me = await page.request.get(`${MOCK}${RUTA_ME}`);
      expect(me.status()).toBe(401);
      await page.goto('/dashboard');
      await expect(page).toHaveURL('/');
      await expect(page.locator('#loginTitle')).toBeVisible();
    });

    test('token inexistente: /api/auth/me -> 401', async ({ page }) => {
      const me = await page.request.get(`${MOCK}${RUTA_ME}`, {
        headers: { Authorization: 'Bearer token-que-no-sesion-ninguna' },
      });
      expect(me.status()).toBe(401);
    });
  });
});