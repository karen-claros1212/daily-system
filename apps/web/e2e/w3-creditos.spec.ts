import { test, expect } from '@playwright/test';
import { setSessionToken, todayISO } from './helpers/session';

/**
 * W3 — Cartera y Créditos (Web Premium, mock real via mock-api.mjs).
 *
 * Contrato (mock replica del FastAPI real):
 *  - GET  /api/creditos        read model paginado {items,total,limit,offset}
 *                               (COBRADOR scoped a su ruta; INVERSIONISTA con
 *                               PII minimizada cliente_nombre/cliente_id null)
 *  - GET  /api/creditos/resumen agregados SOLO backend (saldo/en_mora)
 *  - GET  /api/creditos/:id     detalle con financiero (ruta ajena -> 404)
 *  - POST /api/creditos         creditos:gestionar (solo ADMINISTRADOR)
 *
 * Invariante: los intercepts (si los hay) usan /regex/, nunca glob.
 */

const MOCK = `http://localhost:${process.env.MOCK_API_PORT || 8100}`;

const CRED_ANA = 'cred-11111111-1111-4111-8111-111111111111'; // r1, saldo 800.000, mora 5
const CRED_MARTA = 'cred-33333333-3333-4333-8333-333333333333'; // r2

const CLI_ANA = 'cli-11111111-1111-4111-8111-111111111111';

// El mock es un proceso compartido: la creación de créditos muta el fixture.
// Serie + reset por test => contadores deterministas (aislados del POST).
test.describe.configure({ mode: 'serial' });

test.beforeEach(async ({ request }) => {
  await request.post(`${MOCK}/api/_test/reset-creditos`);
});

test.describe('W3 E2E: ADMINISTRADOR - Créditos', () => {
  test.beforeEach(async ({ page }) => {
    await setSessionToken(page, 'mock-admin');
  });

  test('ADMIN ve navegación Créditos y el resumen de cartera', async ({ page }) => {
    await page.goto('/dashboard');
    await expect(page.getByRole('button', { name: 'Créditos' })).toBeVisible();
    await page.getByRole('button', { name: 'Créditos' }).click();
    await expect(page.getByRole('main', { name: 'Créditos' })).toContainText('Créditos');

    const resumen = page.getByLabel('Resumen de cartera');
    await expect(resumen).toContainText('Total créditos');
    await expect(resumen).toContainText('3');
    await expect(resumen).toContainText('Activos');
    await expect(resumen).toContainText('3');
    await expect(resumen).toContainText('1.940.000');
    await expect(resumen).toContainText('En mora');
    await expect(resumen).toContainText('1');
  });

  test('ADMIN lista créditos con cliente, financiero y link Cliente 360', async ({ page }) => {
    await page.goto('/creditos');
    const tabla = page.getByRole('table', { name: 'Lista de créditos' });
    await expect(tabla).toContainText('Ana María Torres Rojas');
    await expect(tabla).toContainText('800.000');
    await expect(tabla).toContainText('Marta Elena Ruiz Pérez');
    await expect(tabla).toContainText('5 días');

    const link360 = page.getByRole('link', { name: 'Ver Cliente 360 de Ana María Torres Rojas' });
    await expect(link360).toBeVisible();
    await expect(link360).toHaveAttribute('href', `/clientes/${CLI_ANA}`);
  });

  test('ADMIN busca por cliente y filtra por estado', async ({ page }) => {
    await page.goto('/creditos');
    await page.getByLabel('Buscar').fill('Marta');
    await page.getByLabel('Buscar').press('Enter'); // submit del filtro
    const tabla = page.getByRole('table', { name: 'Lista de créditos' });
    await expect(tabla).toContainText('Marta Elena Ruiz Pérez');
    await expect(tabla).not.toContainText('Ana María Torres Rojas');

    await page.getByLabel('Filtrar por estado').selectOption('PAGADO');
    await expect(page.getByText('No hay créditos con los filtros aplicados')).toBeVisible();
  });

  test('ADMIN ordena por saldo descendente', async ({ page }) => {
    await page.goto('/creditos');
    await page.getByLabel('Ordenar créditos por').selectOption('saldo');
    await page.getByLabel('Dirección del orden').selectOption('desc');
    const filas = page.getByRole('table', { name: 'Lista de créditos' }).locator('tbody tr');
    await expect(filas.nth(0)).toContainText('800.000');
    await expect(filas.nth(0)).toContainText('Ana María Torres Rojas');
  });

  test('ADMIN crea un crédito (cuota x cuotas = total backend) y se refleja en cartera', async ({ page }) => {
    await page.goto('/creditos');
    await page.getByRole('button', { name: 'Nuevo Crédito' }).click();

    await page.getByLabel('Buscar cliente').fill('Luis');
    // Botón "Buscar" del formulario de creación (dentro del contenedor del input).
    await page.getByLabel('Buscar cliente').locator('..').getByRole('button', { name: 'Buscar' }).click();
    // El buscador del formulario lista "apellido nombres" (Gómez Luis Fernando).
    await page.getByRole('button', { name: 'Seleccionar Gómez Luis Fernando' }).click();

    await page.getByLabel('Ruta del crédito').selectOption('r1');
    await page.getByLabel('Cuota (COP)').fill('20000');
    await page.getByLabel('N.º de cuotas').fill('5');
    await page.getByLabel('Monto (COP)').fill('100000');
    await page.getByLabel('Fecha de inicio').fill(todayISO());
    await page.getByLabel('Periodicidad del crédito').selectOption('DIARIO');

    await expect(page.getByText('Total estimado')).toContainText('100.000');
    await page.getByRole('button', { name: 'Crear Crédito' }).click();

    // La fila nueva aparece (POST -> refresh del read model del mock).
    const tabla = page.getByRole('table', { name: 'Lista de créditos' });
    await expect(tabla).toContainText('Luis Fernando Gómez');
    await expect(tabla).toContainText('100.000');

    // Resumen recalculado desde el backend (fixture + 1 crédito nuevo).
    const resumen = page.getByLabel('Resumen de cartera');
    await expect(resumen).toContainText('Total créditos');
    await expect(resumen).toContainText('4');
  });

  test('ADMIN ve el detalle de un crédito con financiero', async ({ page }) => {
    await page.goto(`/creditos/${CRED_ANA}`);
    const main = page.getByRole('main', { name: 'Detalle del crédito' });
    await expect(main).toContainText('Crédito');
    await expect(main).toContainText('Ana María Torres Rojas');
    await expect(main).toContainText('Carlos Cobrador');
    await expect(main).toContainText('800.000');
    await expect(main).toContainText('Mora');
    await expect(main).toContainText('5 días');
    await expect(page.getByRole('link', { name: 'Ver Cliente 360 de Ana María Torres Rojas' })).toBeVisible();
  });
});

test.describe('W3 E2E: COBRADOR - Créditos (scoped a su ruta)', () => {
  test.beforeEach(async ({ page }) => {
    await setSessionToken(page, 'mock-jwt-token'); // rol COBRADOR, ruta r1
  });

  test('COBRADOR ve solo créditos de su ruta y sin acción de crear', async ({ page }) => {
    await page.goto('/creditos');
    const tabla = page.getByRole('table', { name: 'Lista de créditos' });
    await expect(tabla).toContainText('Ana María Torres Rojas');
    await expect(tabla).toContainText('Luis Fernando Gómez');
    await expect(tabla).not.toContainText('Marta Elena');
    await expect(page.getByRole('button', { name: 'Nuevo Crédito' })).toHaveCount(0);
    await expect(page.getByLabel('Filtrar por ruta')).toHaveCount(0);

    // Resumen scoped: 2 créditos, saldo 1.300.000, 1 en mora.
    const resumen = page.getByLabel('Resumen de cartera');
    await expect(resumen).toContainText('2');
    await expect(resumen).toContainText('1.300.000');
    await expect(resumen).toContainText('1');
  });

  test('COBRADOR ve detalle de crédito de su ruta; crédito ajeno -> 404 sin revelar', async ({ page }) => {
    await page.goto(`/creditos/${CRED_ANA}`);
    const main = page.getByRole('main', { name: 'Detalle del crédito' });
    await expect(main).toContainText('Ana María Torres Rojas');
    await expect(main).toContainText('800.000');
    await expect(page.getByRole('link', { name: 'Ver Cliente 360 de Ana María Torres Rojas' })).toBeVisible();

    await page.goto(`/creditos/${CRED_MARTA}`); // ruta r2 (ajena)
    await expect(page.getByRole('main', { name: 'Detalle del crédito' })).toContainText('Error al cargar el crédito');
  });
});

test.describe('W3 E2E: INVERSIONISTA - Créditos (PII minimizada)', () => {
  test.beforeEach(async ({ page }) => {
    await setSessionToken(page, 'test-token'); // rol INVERSIONISTA (sesión rbac-roles)
  });

  test('INVERSIONISTA ve resumen y lista sin PII ni Cliente 360 ni crear', async ({ page }) => {
    await page.goto('/creditos');
    const tabla = page.getByRole('table', { name: 'Lista de créditos' });
    await expect(tabla).toContainText('—'); // columna Cliente anonimizada
    await expect(tabla).toContainText('800.000');
    await expect(tabla).toContainText('Ruta Centro');
    await expect(page.getByRole('link', { name: /Ver Cliente 360/ })).toHaveCount(0);
    await expect(page.getByRole('button', { name: 'Nuevo Crédito' })).toHaveCount(0);

    const resumen = page.getByLabel('Resumen de cartera');
    await expect(resumen).toContainText('3');
    await expect(resumen).toContainText('1.940.000');
  });

  test('INVERSIONISTA ve detalle sin PII ni link Cliente 360', async ({ page }) => {
    await page.goto(`/creditos/${CRED_ANA}`);
    const main = page.getByRole('main', { name: 'Detalle del crédito' });
    await expect(main).toContainText('Crédito');
    await expect(main).toContainText('800.000');
    await expect(page.getByRole('link', { name: /Cliente 360/ })).toHaveCount(0);
    // El nombre del cliente no se revela (mock anonimiza cliente_nombre).
    await expect(main).not.toContainText('Torres');
  });
});

test.describe('W3 E2E: RBAC de creación en el mock', () => {
  test('POST sin creditos:gestionar -> 403', async ({ request }) => {
    const res = await request.post(`${MOCK}/api/creditos`, {
      headers: { Authorization: 'Bearer mock-jwt-token' },
      data: { cliente_id: CLI_ANA, ruta_id: 'r1', cuota: 1000, n_cuotas: 10, monto: 10000, fecha_inicio: '2026-08-16' },
    });
    expect(res.status()).toBe(403);
  });

  test('POST con cliente inexistente -> 404', async ({ request }) => {
    const res = await request.post(`${MOCK}/api/creditos`, {
      headers: { Authorization: 'Bearer mock-admin' },
      data: { cliente_id: 'no-existe', ruta_id: 'r1', cuota: 1000, n_cuotas: 10, monto: 10000, fecha_inicio: '2026-08-16' },
    });
    expect(res.status()).toBe(404);
  });

  test('POST con campo no permitido -> 422', async ({ request }) => {
    const res = await request.post(`${MOCK}/api/creditos`, {
      headers: { Authorization: 'Bearer mock-admin' },
      data: { cliente_id: CLI_ANA, ruta_id: 'r1', cuota: 1000, n_cuotas: 10, monto: 10000, fecha_inicio: '2026-08-16', tasa: 99 },
    });
    expect(res.status()).toBe(422);
  });
});
