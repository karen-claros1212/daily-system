import { test, expect } from '@playwright/test';
import { setSessionToken } from './helpers/session';

/**
 * W6 — Cobranza y Mora: Worklist + Drill-down + Promise to Pay (mock).
 *
 * Contrato (mock replica del FastAPI real):
 *  - GET /api/cobranza/web         worklist paginada con aging, sort, filtros
 *  - GET /api/cobranza/resumen     KPIs (total_creditos, total_saldo, aging)
 *  - GET /api/cobranza/{credito_id} drill-down (obligaciones, pagos, promesas)
 *  - POST /api/cobranza/promesas   crear promesa (409 si ya existe ACTIVE)
 *  - POST /api/cobranza/promesas/{id}/cumplir|incumplir|cancelar
 *  - RBAC: cobranza:ver (3 roles), promesas:crear (ADMIN+COBRADOR)
 *  - INVERSIONISTA: PII minimizada (cliente_nombre → null)
 *  - COBRADOR: scoped a su ruta activa
 */

const MOCK = `http://localhost:${process.env.MOCK_API_PORT || 8100}`;

test.describe.configure({ mode: 'serial' });

test.describe('W6 E2E: ADMINISTRADOR - Cobranza', () => {
  test.beforeEach(async ({ page }) => {
    await setSessionToken(page, 'mock-admin');
  });

  test('ADMIN ve Centro de Cobranza con KPIs y worklist', async ({ page }) => {
    await page.goto('/cobranza');

    await expect(page.getByRole('heading', { name: 'Centro de Cobranza' })).toBeVisible();

    // KPIs
    await expect(page.getByText('Cartera total')).toBeVisible();
    await expect(page.getByText('Cartera vencida')).toBeVisible();
    await expect(page.getByText('Clientes en mora')).toBeVisible();

    // Worklist con créditos
    const tabla = page.getByRole('table');
    await expect(tabla).toContainText('Juan Perez');
    await expect(tabla).toContainText('Maria Gomez');
    await expect(tabla).toContainText('Carlos Ruiz');
  });

  test('ADMIN ve aging distribution', async ({ page }) => {
    await page.goto('/cobranza');
    await page.waitForTimeout(500);

    // Aging distribution section shows bucket labels
    await expect(page.locator('div.text-center', { hasText: '8-15 días' })).toBeVisible();
    await expect(page.locator('div.text-center', { hasText: '16-30 días' })).toBeVisible();
    await expect(page.locator('div.text-center', { hasText: 'Al día' })).toBeVisible();
  });

  test('ADMIN abre drill-down de un crédito', async ({ page }) => {
    await page.goto('/cobranza');
    await page.waitForTimeout(500);

    // Click en el primer enlace de cliente
    await page.getByRole('link', { name: 'Juan Perez' }).click();
    await page.waitForTimeout(500);

    // Drill-down page
    await expect(page.getByRole('heading', { name: 'Juan Perez' })).toBeVisible();
    await expect(page.getByText('Saldo total')).toBeVisible();
    await expect(page.getByText('Monto vencido')).toBeVisible();
    await expect(page.getByText('Cuotas vencidas')).toBeVisible();
    await expect(page.getByText('Obligaciones vencidas')).toBeVisible();
  });

  test('ADMIN crea promesa desde drill-down', async ({ page }) => {
    await page.goto('/cobranza/c1');
    await page.waitForTimeout(500);

    // Verificar que no hay promesas
    await expect(page.getByText('Sin promesas registradas')).toBeVisible();

    // Abrir form de promesa
    await page.getByRole('button', { name: '+ Registrar promesa' }).click();
    await page.waitForTimeout(300);

    // Completar form
    await page.locator('#promesa-fecha').fill('2026-08-25');
    await page.locator('#promesa-monto').fill('200000');
    await page.locator('#promesa-nota').fill('Paga viernes');

    await page.getByRole('button', { name: 'Confirmar promesa' }).click();
    await page.waitForTimeout(1000);

    // Promesa creada: aparece en la lista con estado ACTIVE
    await expect(page.getByText('ACTIVE')).toBeVisible();
    await expect(page.getByText('Paga viernes')).toBeVisible();
  });

  test('ADMIN recibe 409 si ya existe promesa ACTIVE', async ({ page }) => {
    await page.goto('/cobranza/c2');
    await page.waitForTimeout(500);

    // Crear primera promesa en c2
    await page.getByRole('button', { name: '+ Registrar promesa' }).click();
    await page.waitForTimeout(300);
    await page.locator('#promesa-fecha').fill('2026-08-25');
    await page.locator('#promesa-monto').fill('200000');
    await page.getByRole('button', { name: 'Confirmar promesa' }).click();
    await page.waitForTimeout(1000);

    // Verificar que la primera promesa fue creada
    await expect(page.getByText('ACTIVE')).toBeVisible();

    // Crear segunda promesa → 409 (ya existe ACTIVE)
    await page.getByRole('button', { name: '+ Registrar promesa' }).click();
    await page.waitForTimeout(300);
    await page.locator('#promesa-fecha').fill('2026-08-26');
    await page.locator('#promesa-monto').fill('100000');
    await page.getByRole('button', { name: 'Confirmar promesa' }).click();
    await page.waitForTimeout(500);

    await expect(page.getByText(/Ya existe una promesa activa/i)).toBeVisible();
  });

  test('ADMIN recibe 422 si monto inválido', async ({ page }) => {
    await page.goto('/cobranza/c2');
    await page.waitForTimeout(500);

    await page.getByRole('button', { name: '+ Registrar promesa' }).click();
    await page.waitForTimeout(300);
    await page.locator('#promesa-fecha').fill('2026-08-25');
    await page.locator('#promesa-monto').fill('0');
    await page.getByRole('button', { name: 'Confirmar promesa' }).click();
    await page.waitForTimeout(500);

    await expect(page.getByText(/amount/i)).toBeVisible();
  });

  test('ADMIN filtra worklist por aging bucket', async ({ page }) => {
    await page.goto('/cobranza');
    await page.waitForTimeout(500);

    await page.locator('#cob-bucket').selectOption('16-30');
    await page.waitForTimeout(500);

    const tabla = page.getByRole('table');
    await expect(tabla).toContainText('Maria Gomez');
    // Juan Perez es 8-15, no debe aparecer
    await expect(tabla).not.toContainText('Juan Perez');
    // Carlos Ruiz es CURRENT, no debe aparecer
    await expect(tabla).not.toContainText('Carlos Ruiz');
  });
});

test.describe('W6 E2E: INVERSIONISTA - Cobranza (PII minimizada)', () => {
  test.beforeEach(async ({ page }) => {
    await setSessionToken(page, 'test-token');
  });

  test('INVERSIONISTA ve cobranza sin nombres de clientes', async ({ page }) => {
    await page.goto('/cobranza');

    await expect(page.getByRole('heading', { name: 'Centro de Cobranza' })).toBeVisible();

    const tabla = page.getByRole('table');
    // PII minimizada: no debe mostrar nombres de clientes
    const rows = tabla.getByRole('row');
    const count = await rows.count();
    for (let i = 1; i < count; i++) {
      const row = rows.nth(i);
      await expect(row).not.toContainText('Juan Perez');
      await expect(row).not.toContainText('Maria Gomez');
      await expect(row).not.toContainText('Carlos Ruiz');
    }
  });

  test('INVERSIONISTA ve drill-down sin PII', async ({ page }) => {
    await page.goto('/cobranza/c1');
    await page.waitForTimeout(500);

    // No debe mostrar nombre del cliente
    await expect(page.getByRole('heading', { name: 'Juan Perez' })).not.toBeVisible();
    // Pero sí ve los datos financieros
    await expect(page.getByText('Saldo total')).toBeVisible();
    await expect(page.getByText('Monto vencido')).toBeVisible();
  });
});

test.describe('W6 E2E: COBRADOR - Cobranza (scoped)', () => {
  test.beforeEach(async ({ page }) => {
    await setSessionToken(page, 'test-cobrador-code');
  });

  test('COBRADOR ve solo créditos de su ruta', async ({ page }) => {
    await page.goto('/cobranza');

    await expect(page.getByRole('heading', { name: 'Centro de Cobranza' })).toBeVisible();

    const tabla = page.getByRole('table');
    // mock-cobrador tiene route_id r1 (Ruta Centro)
    await expect(tabla).toContainText('Ruta Centro');
    // No debe ver créditos de Ruta Sur
    const rows = tabla.getByRole('row');
    const count = await rows.count();
    for (let i = 1; i < count; i++) {
      const row = rows.nth(i);
      await expect(row).not.toContainText('Ruta Sur');
    }
  });

  test('COBRADOR no ve crédito de otra ruta (404)', async ({ page }) => {
    await page.goto('/cobranza/c3');
    await page.waitForTimeout(500);

    // c3 es de Ruta Sur, COBRADOR está en Ruta Centro
    await expect(page.getByText(/no encontrado|404|Error/i)).toBeVisible();
  });

  test('COBRADOR crea promesa en su ruta', async ({ page }) => {
    await page.goto('/cobranza/c1');
    await page.waitForTimeout(500);

    await page.getByRole('button', { name: '+ Registrar promesa' }).click();
    await page.waitForTimeout(300);
    await page.locator('#promesa-fecha').fill('2026-08-25');
    await page.locator('#promesa-monto').fill('150000');
    await page.getByRole('button', { name: 'Confirmar promesa' }).click();
    await page.waitForTimeout(1000);

    // Promesa creada: aparece en la lista con estado ACTIVE
    await expect(page.getByText('ACTIVE')).toBeVisible();
  });
});
