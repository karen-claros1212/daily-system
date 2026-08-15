import { test, expect } from '@playwright/test';
import { setSessionToken } from './helpers/session';

test.describe('Dispositivos autorizados (Etapa 3)', () => {
  test('ADMINISTRADOR: renderiza listado con estados reales del contrato', async ({ page }) => {
    await setSessionToken(page, 'mock-admin');
    await page.goto('/dispositivos');
    await expect(page.locator('h1')).toContainText('Dispositivos autorizados');
    // 3 dispositivos del fixture: ACTIVE, REVOKED, REPLACED
    await expect(page.locator('.badge-success')).toContainText('Autorizado');
    await expect(page.locator('.badge-danger')).toContainText('Revocado');
    await expect(page.locator('.badge-warning')).toContainText('Reemplazado');
    await expect(page.locator('body')).toContainText('Galaxy A54');
    await expect(page.locator('body')).toContainText('iPhone 12');
    await expect(page.locator('body')).toContainText('Redmi Note 12');
  });

  test('ADMINISTRADOR: no muestra secretos (claves ni hashes)', async ({ page }) => {
    await setSessionToken(page, 'mock-admin');
    await page.goto('/dispositivos');
    const body = page.locator('body');
    await expect(body).not.toContainText('public_key');
    await expect(body).not.toContainText('private_key');
    await expect(body).not.toContainText('sha256');
  });

  test('ADMINISTRADOR: empty state cuando no hay dispositivos', async ({ page }) => {
    await setSessionToken(page, 'mock-admin-empty');
    await page.goto('/dispositivos');
    await expect(page.locator('body')).toContainText('No hay dispositivos registrados');
  });

  test('ADMINISTRADOR: revoca y reactiva un dispositivo', async ({ page }) => {
    await setSessionToken(page, 'mock-admin');
    await page.goto('/dispositivos');
    // Revocar el ACTIVE
    const activeCard = page.locator('li', { hasText: 'Galaxy A54' });
    await activeCard.getByRole('button', { name: 'Revocar' }).click();
    await activeCard.getByRole('button', { name: 'Confirmar revocación' }).click();
    await expect(page.locator('.flash-success')).toContainText('Dispositivo revocado correctamente');
    await expect(page.locator('li', { hasText: 'Galaxy A54' }).locator('.badge-danger')).toContainText('Revocado');
    // Reactivar el REVOKED original (iPhone 12)
    const revokedCard = page.locator('li', { hasText: 'iPhone 12' });
    await revokedCard.getByRole('button', { name: 'Reactivar' }).click();
    await expect(page.locator('.flash-success')).toContainText('Dispositivo reactivado correctamente');
    await expect(page.locator('li', { hasText: 'iPhone 12' }).locator('.badge-success')).toContainText('Autorizado');
  });

  test('ADMINISTRADOR: reemplazo emite nuevo código de activación (backend lo genera)', async ({ page }) => {
    await setSessionToken(page, 'mock-admin');
    await page.goto('/dispositivos');
    const activeCard = page.locator('li', { hasText: 'Galaxy A54' });
    await activeCard.getByRole('button', { name: 'Reemplazar' }).click();
    await activeCard.getByRole('button', { name: 'Confirmar reemplazo (genera código nuevo)' }).click();
    await expect(page.locator('body')).toContainText('Nuevo código de activación');
    await expect(page.locator('body')).toContainText('Expira:');
    await expect(page.locator('li', { hasText: 'Galaxy A54' }).locator('.badge-warning')).toContainText('Reemplazado');
  });

  test('ADMINISTRADOR: genera código de activación para el cobrador del dispositivo', async ({ page }) => {
    await setSessionToken(page, 'mock-admin');
    await page.goto('/dispositivos');
    const activeCard = page.locator('li', { hasText: 'Galaxy A54' });
    await activeCard.getByRole('button', { name: 'Generar código' }).click();
    await expect(page.locator('body')).toContainText('Código de activación');
    await expect(page.locator('body')).toContainText('Expira:');
  });

  test('COBRADOR: 403 controlado, sin redirect silencioso al login', async ({ page }) => {
    await setSessionToken(page, 'mock-jwt-token');
    await page.goto('/dispositivos');
    await expect(page.locator('h1')).toContainText('Acceso denegado');
    await expect(page).toHaveURL(/\/dispositivos/);
  });

  test('INVERSIONISTA: 403 controlado (RBAC real no le da dispositivos:registrar)', async ({ page }) => {
    await setSessionToken(page);
    await page.goto('/dispositivos');
    await expect(page.locator('h1')).toContainText('Acceso denegado');
    await expect(page).toHaveURL(/\/dispositivos/);
  });

  test('error transitorio (500): flash recuperable con reintento', async ({ page }) => {
    await setSessionToken(page, 'mock-admin-error');
    await page.goto('/dispositivos');
    await expect(page.locator('.flash-error')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Reintentar' })).toBeVisible();
  });

  test('navegación: ítem Dispositivos visible solo para ADMINISTRADOR', async ({ page }) => {
    await setSessionToken(page, 'mock-admin');
    await page.goto('/dashboard');
    await expect(page.getByRole('button', { name: 'Dispositivos' })).toBeVisible();
    await page.getByRole('button', { name: 'Dispositivos' }).click();
    await expect(page).toHaveURL(/\/dispositivos/);
    await expect(page.locator('h1')).toContainText('Dispositivos autorizados');
  });

  test('navegación: COBRADOR no ve el ítem Dispositivos', async ({ page }) => {
    await setSessionToken(page, 'mock-jwt-token');
    await page.goto('/dashboard');
    await expect(page.getByRole('button', { name: 'Dispositivos' })).toHaveCount(0);
  });

  test('navegación: INVERSIONISTA no ve el ítem Dispositivos', async ({ page }) => {
    await setSessionToken(page);
    await page.goto('/dashboard');
    await expect(page.getByRole('button', { name: 'Dispositivos' })).toHaveCount(0);
  });
});
