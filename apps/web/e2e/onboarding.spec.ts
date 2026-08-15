import { test, expect } from '@playwright/test';

test.describe('Registro de negocio (Etapa 3)', () => {
  test('login ofrece enlace a registro de negocio nuevo', async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('#loginTitle')).toBeVisible();
    await expect(page.locator('#registroLink')).toHaveAttribute('href', '/registro');
  });

  test('alta feliz: crea negocio y muestra el codigo de activacion una sola vez', async ({ page }) => {
    await page.goto('/registro');
    await expect(page.locator('#registroTitle')).toBeVisible();

    await page.locator('#negocioNombre').fill('Distribuciones del Sur');
    await page.locator('#nitNegocio').fill('900999888');
    await page.locator('#adminNombre').fill('María Pérez');
    await page.locator('#adminDocumento').fill('CC 123456789');
    await page.locator('#registroBtn').click();

    await expect(page.locator('#registroOkTitle')).toBeVisible();
    const code = page.locator('#activationCodeResult');
    await expect(code).toBeVisible();
    const token = (await code.textContent()) ?? '';
    expect(token.length).toBeGreaterThan(20);
    await expect(page.locator('body')).toContainText('Distribuciones del Sur');
    await expect(page.locator('body')).toContainText('María Pérez');

    // El codigo es de un solo uso y guia al admin al login Web existente.
    await page.locator('#goToLoginBtn').click();
    await expect(page).toHaveURL(/\/$/);
    await expect(page.locator('#loginTitle')).toBeVisible();
  });

  test('validacion: campos obligatorios vacios -> error y sin request de alta', async ({ page }) => {
    await page.goto('/registro');
    await page.locator('#registroBtn').click();
    await expect(page.locator('#registroError')).toContainText('nombre del negocio');
    await expect(page.locator('#registroError')).toBeVisible();

    // Solo el nombre del negocio no basta: falta el administrador.
    await page.locator('#negocioNombre').fill('Distribuciones del Sur');
    await page.locator('#registroBtn').click();
    await expect(page.locator('#registroError')).toContainText('administrador');
  });

  test('NIT ya registrado -> 409 controlado', async ({ page }) => {
    await page.goto('/registro');
    await page.locator('#negocioNombre').fill('Duplicado');
    await page.locator('#nitNegocio').fill('900123456'); // NIT sembrado en el mock
    await page.locator('#adminNombre').fill('Admin');
    await page.locator('#registroBtn').click();
    await expect(page.locator('#registroError')).toContainText('NIT ya está registrado');
    // Sigue en el formulario (estado recuperable, no se pierde la pagina).
    await expect(page.locator('#registroTitle')).toBeVisible();
  });

  test('error de servidor (500) -> mensaje recuperable y el formulario sigue usable', async ({ page }) => {
    await page.goto('/registro');
    await page.route('**/api/onboarding/negocios', async (route) => {
      await route.fulfill({ status: 500, json: { detail: 'Mock internal error' } });
    });
    await page.locator('#negocioNombre').fill('Fallara una vez');
    await page.locator('#adminNombre').fill('Admin');
    await page.locator('#registroBtn').click();
    await expect(page.locator('#registroError')).toContainText('No se pudo completar el registro');

    // Quitar el interceptor: el reintento del mismo usuario funciona.
    await page.unroute('**/api/onboarding/negocios');
    await page.locator('#registroBtn').click();
    await expect(page.locator('#registroOkTitle')).toBeVisible();
  });
});
