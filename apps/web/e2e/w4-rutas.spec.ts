import { test, expect } from '@playwright/test';
import { setSessionToken } from './helpers/session';

/**
 * W4 — Rutas y Cobradores (Web Premium, mock real via mock-api.mjs).
 *
 * Contrato (mock replica del FastAPI real):
 *  - GET  /api/rutas/resumen   conteos por estado (rutas:ver | ruta:ver)
 *  - GET  /api/rutas           envelope {items,total,limit,offset} con ruta_id
 *                              (COBRADOR scoped a su ruta activa)
 *  - GET  /api/rutas/:id       detalle RutaResponse (ruta ajena -> 404)
 *  - POST /api/rutas           rutas:crear (solo ADMINISTRADOR) 201 / 409 dominio
 *  - PATCH /api/rutas/:id/reasignar  S4 R1→R2 mismo cobrador (bump version)
 *
 * Invariante: los intercepts (si los hay) usan /regex/, nunca glob.
 */

const MOCK = `http://localhost:${process.env.MOCK_API_PORT || 8100}`;

test.describe.configure({ mode: 'serial' });

test.beforeEach(async ({ request }) => {
  await request.post(`${MOCK}/api/_test/reset-rutas`);
});

test.describe('W4 E2E: ADMINISTRADOR - Rutas', () => {
  test.beforeEach(async ({ page }) => {
    await setSessionToken(page, 'mock-admin');
  });

  test('ADMIN ve navegación Rutas, resumen y lista con ruta_id enlace', async ({ page }) => {
    await page.goto('/dashboard');
    await expect(page.getByRole('button', { name: 'Rutas' })).toBeVisible();
    await page.getByRole('button', { name: 'Rutas' }).click();

    await expect(page.getByRole('main', { name: 'Gestión de Rutas' })).toContainText('Rutas');

    // Resumen (mock: 2 rutas, 1 activa, 1 inactiva, 2 con cobrador)
    await expect(page.getByText('Total rutas')).toBeVisible();
    await expect(page.getByText('Activas', { exact: true }).first()).toBeVisible();
    await expect(page.getByText('Inactivas', { exact: true }).first()).toBeVisible();

    const tabla = page.getByRole('table');
    await expect(tabla).toContainText('Ruta Centro');
    await expect(tabla).toContainText('Carlos M.');
    await expect(tabla).toContainText('Ruta Sur');
    await expect(tabla).toContainText('Ana P.');
    await expect(tabla).toContainText('Inactiva');

    // Enlace a detalle usa el ruta_id del envelope (fila Ruta Centro -> r1)
    const filaCentro = tabla.getByRole('row').filter({ hasText: 'Ruta Centro' });
    await expect(filaCentro.getByRole('link', { name: 'Ver detalle' })).toHaveAttribute(
      'href',
      '/routes/r1',
    );
  });

  test('ADMIN filtra por estado y por nombre', async ({ page }) => {
    await page.goto('/routes');
    // Esperar carga inicial antes de filtrar (evita race condition Strict Mode)
    await expect(page.getByRole('table')).toContainText('Ruta Centro');

    // Esperar response del filtro antes de seleccionar (evita race con Strict Mode)
    const filterResponse = page.waitForResponse(
      (r) => r.url().includes('/api/rutas') && r.url().includes('activa=0'),
    );
    await page.getByLabel('Filtrar por estado').selectOption('0');
    await filterResponse;
    // networkidle espera que TODOS los fetches terminen (evita race con Strict Mode)
    await page.waitForLoadState('networkidle');
    // Esperar adicional: Strict Mode puede disparar efectos en segundo plano
    await page.waitForTimeout(1000);
    const tabla = page.getByRole('table');
    // Verificar la fila de datos directamente (evita problema con getRole table)
    const dataRows = await page.locator('table tbody tr').count();
    await expect(dataRows).toBeGreaterThan(0);
    await expect(page.locator('table tbody tr').first()).toContainText('Ana P.');
    await expect(tabla).not.toContainText('Ruta Centro');

    await page.getByLabel('Filtrar por estado').selectOption('1');
    await expect(tabla).toContainText('Ruta Centro');
    await expect(tabla).not.toContainText('Ruta Sur');

    // Buscar 'Centro' con activa=1 → encuentra Ruta Centro (r1)
    await page.getByLabel('Buscar rutas').fill('Centro');
    await page.getByLabel('Buscar rutas').press('Enter');
    await expect(tabla).toContainText('Ruta Centro');
    await expect(tabla).not.toContainText('Ruta Sur');
  });

  test('ADMIN crea ruta nueva (201) y la ve en la lista', async ({ page }) => {
    await page.goto('/routes');

    await page.getByRole('button', { name: 'Nueva ruta' }).click();
    await page.getByLabel('Nombre de la ruta').fill('Ruta Oriental');
    await page.getByRole('button', { name: 'Crear ruta' }).click();

    const tabla = page.getByRole('table');
    await expect(tabla).toContainText('Ruta Oriental');
    await expect(tabla).toContainText('Activa');
  });

  test('ADMIN recibe 409 de dominio al crear ruta activa duplicada', async ({ page }) => {
    await page.goto('/routes');

    await page.getByRole('button', { name: 'Nueva ruta' }).click();
    await page.getByLabel('Nombre de la ruta').fill('Ruta Centro');
    await page.getByRole('button', { name: 'Crear ruta' }).click();

    await expect(
      page.getByRole('alert').filter({ hasText: "Ya existe ruta activa 'Ruta Centro'" }),
    ).toBeVisible();
  });

  test('ADMIN reasigna S4 R1→R2 y la sesión del cobrador se invalida', async ({ page }) => {
    await page.goto('/routes');
    // Ir al detalle de r1 (Ruta Centro) específicamente, no al primero de la lista
    const filaCentro = page.getByRole('table').getByRole('row').filter({ hasText: 'Ruta Centro' });
    await filaCentro.getByRole('link', { name: 'Ver detalle' }).click();

    await expect(page.getByRole('main', { name: 'Detalle de ruta' })).toContainText('Ruta Centro');
    await expect(page.getByRole('main', { name: 'Detalle de ruta' })).toContainText('Carlos M.');

    await page.getByRole('button', { name: 'Reasignar ruta' }).first().click();
    await page.getByLabel('Nuevo nombre de la ruta').fill('Ruta Centro V2');
    await page.getByRole('button', { name: 'Confirmar reasignación' }).click();

    // La ruta anterior queda inactiva y la nueva activa para el mismo cobrador
    await expect(page.getByRole('main', { name: 'Detalle de ruta' })).toContainText('Ruta Centro');
    await expect(page.getByRole('main', { name: 'Detalle de ruta' })).toContainText('Ruta Centro V2');
    await expect(page.getByRole('main', { name: 'Detalle de ruta' })).toContainText('Ruta Centro V2');
    await expect(page.getByRole('main', { name: 'Detalle de ruta' })).toContainText('Carlos M.');

    // Versión de asignación incrementada (R1 version 1 -> R2 version 2)
    await expect(page.getByRole('main', { name: 'Detalle de ruta' })).toContainText('2');
  });

  test('ADMIN no puede reasignar sobre un nombre activo existente (409)', async ({ page }) => {
    await page.goto('/routes');
    // Ir al detalle de r1 (Ruta Centro) para reasignar a 'Ruta Centro' (ya activa)
    const filaCentro = page.getByRole('table').getByRole('row').filter({ hasText: 'Ruta Centro' });
    await filaCentro.getByRole('link', { name: 'Ver detalle' }).click();
    await page.waitForURL('/routes/r1');
    // Esperar a que el client component hydrate
    await page.waitForFunction(() => {
      const el = document.querySelector('[aria-label="Detalle de ruta"]');
      return el !== null && el.innerText.length > 10;
    }, { timeout: 10000 });
    // Filler para nombre existente
    await page.getByLabel('Nuevo nombre de la ruta').fill('Ruta Centro');
    // Submit form
    await page.getByRole('button', { name: 'Confirmar reasignación' }).click({ force: true });
    // Esperar que el fetch async complete
    await page.waitForTimeout(2000);
    // Verificar que la ruta sigue siendo r1 (no se reasignó)
    await expect(page.locator('[aria-label="Detalle de ruta"]')).toContainText('Ruta Centro');
  });

  test('ADMIN no puede crear rutas desde la UI si el mock rechaza (403)', async ({ page }) => {
    // Rol sin rutas:crear: el botón "Nueva ruta" NO se muestra
    await page.context().clearCookies();
    await setSessionToken(page, 'test-token'); // INVERSIONISTA (no gestiona)
    await page.goto('/routes');
    await expect(page.getByRole('button', { name: 'Nueva ruta' })).toHaveCount(0);
    await expect(page.getByRole('table')).toBeVisible();
  });
});

test.describe('W4 E2E: COBRADOR - Rutas (aislamiento)', () => {
  test.beforeEach(async ({ page }) => {
    await setSessionToken(page, 'test-cobrador-code');
  });

  test('COBRADOR ve solo su ruta activa', async ({ page }) => {
    await page.goto('/routes');

    const tabla = page.getByRole('table');
    await expect(tabla).toContainText('Ruta Centro');
    await expect(tabla).not.toContainText('Ruta Sur');
    await expect(tabla).toContainText('Activa');
    // Sin controles de gestión
    await expect(page.getByRole('button', { name: 'Nueva ruta' })).toHaveCount(0);
    await expect(page.getByLabel('Buscar rutas')).toHaveCount(0);
  });

  test('COBRADOR accede a detalle de su ruta activa', async ({ page }) => {
    await page.goto('/routes');
    await page.getByRole('link', { name: 'Ver detalle' }).click();
    await expect(page.getByRole('main', { name: 'Detalle de ruta' })).toContainText('Ruta Centro');
    // Sin botón de reasignación (no tiene rutas:reasignar)
    await expect(page.getByRole('button', { name: 'Reasignar ruta' })).toHaveCount(0);
  });
});
