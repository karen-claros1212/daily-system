import { test, expect } from '@playwright/test';
import { setSessionToken } from './helpers/session';

const MOCK = `http://localhost:${process.env.MOCK_API_PORT || 8100}`;

const CLI_ANA = {
  id: 'cli-11111111-1111-4111-8111-111111111111',
  negocio_id: 'n1',
  tipo_documento: 'CC',
  documento_normalizado: '1000000001',
  identity_status: 'VERIFIED',
  primer_apellido: 'Torres',
  segundo_apellido: 'Rojas',
  nombres: 'Ana María',
  telefono_1: '3001234567',
  telefono_2: '3019876543',
  direccion: 'Calle 10 # 5-20',
  barrio: 'Palermo',
  ciudad: 'Bogotá',
  ocupacion: 'Independiente',
  creado_el: '2025-07-12T16:52:14.950Z',
  creditos: [
    {
      id: 'cred-11111111-1111-4111-8111-111111111111',
      estado: 'ACTIVO',
      cuota: 100000,
      n_cuotas: 12,
      monto: 1000000,
      total: 1200000,
      periodicidad: 'DIARIA',
      fecha_inicio: '2026-07-01',
      saldo: 800000,
      mora_legacy: 5,
      pico: 1200000,
      cuotas_pagadas: 4,
      ruta_id: 'r1',
      ruta_nombre: 'Ruta Centro',
      cobrador_nombre: 'Carlos Cobrador',
    },
  ],
  pagos_recientes: [
    {
      id: 'pag-11111111-1111-4111-8111-111111111111',
      credito_id: 'cred-11111111-1111-4111-8111-111111111111',
      tipo: 'PAGO',
      monto: 100000,
      nota: 'Abono',
      recibido_el_servidor: '2026-08-15T10:00:00Z',
    },
  ],
  saldo_total: 800000,
};

const CLIENTES_LIST: Record<string, unknown>[] = [
  {
    id: 'cli-11111111-1111-4111-8111-111111111111',
    tipo_documento: 'CC',
    documento_normalizado: '1000000001',
    identity_status: 'VERIFIED',
    primer_apellido: 'Torres',
    segundo_apellido: 'Rojas',
    nombres: 'Ana María',
    telefono_1: '3001234567',
    ciudad: 'Bogotá',
    creditos_activos: 1,
    creado_el: '2025-07-12T16:52:14.950Z',
  },
  {
    id: 'cli-22222222-2222-4222-8222-222222222222',
    tipo_documento: 'CC',
    documento_normalizado: '1000000002',
    identity_status: 'PROVISIONAL',
    primer_apellido: 'Gómez',
    segundo_apellido: null,
    nombres: 'Luis Fernando',
    telefono_1: '3002223344',
    ciudad: 'Bogotá',
    creditos_activos: 1,
    creado_el: '2026-07-17T16:52:14.950Z',
  },
  {
    id: 'cli-33333333-3333-4333-8333-333333333333',
    tipo_documento: 'CE',
    documento_normalizado: '2000000001',
    identity_status: 'POSSIBLE_DUPLICATE',
    primer_apellido: 'Ruiz',
    segundo_apellido: 'Pérez',
    nombres: 'Marta Elena',
    telefono_1: '3105556677',
    ciudad: 'Medellín',
    creditos_activos: 1,
    creado_el: '2026-08-06T16:52:14.950Z',
  },
  {
    id: 'cli-44444444-4444-4444-8444-444444444444',
    tipo_documento: 'CC',
    documento_normalizado: '1000000003',
    identity_status: 'VERIFIED',
    primer_apellido: 'Vargas',
    segundo_apellido: null,
    nombres: 'Sofía Isabel',
    telefono_1: '3114445566',
    ciudad: 'Cali',
    creditos_activos: 0,
    creado_el: '2026-08-01T16:52:14.950Z',
  },
];

function listPage(items: Record<string, unknown>[], total: number, limit = 25, offset = 0) {
  return { items, total, limit, offset };
}

// ─── ADMIN: lista / busca / filtra / crea / edita / detalle ──────────────────

test.describe('W2 E2E: ADMIN - Clientes', () => {
  test.beforeEach(async ({ page }) => {
    await setSessionToken(page, 'mock-admin');
  });

  test('ADMIN ve navegacion Clientes', async ({ page }) => {
    await page.goto('/dashboard');
    await expect(page.getByRole('button', { name: 'Clientes' })).toBeVisible();
  });

  test('ADMIN lista clientes con badges de identidad', async ({ page }) => {
    await page.route(/\/api\/clientes(\?.*)?$/, async (route) => {
      if (route.request().method() === 'GET') {
        await route.fulfill({ status: 200, json: listPage(CLIENTES_LIST, 4) });
      }
    });
    await page.goto('/clientes');
    await expect(page.locator('h1')).toContainText('Clientes');
    await expect(page.getByText('Clientes (4)')).toBeVisible();
    await expect(page.getByText('Ana María Torres')).toBeVisible();
    await expect(page.getByText('Luis Fernando Gómez')).toBeVisible();
    await expect(page.getByText('Marta Elena Ruiz')).toBeVisible();
    await expect(page.getByText('CC 1000000001')).toBeVisible();
    await expect(page.getByText('Verificado', { exact: true }).first()).toBeVisible();
    await expect(page.getByText('Provisional', { exact: true })).toBeVisible();
    await expect(page.getByText('Posible duplicado', { exact: true })).toBeVisible();
  });

  test('ADMIN busca por nombre (q)', async ({ page }) => {
    const qs: string[] = [];
    await page.route(/\/api\/clientes(\?.*)?$/, async (route) => {
      if (route.request().method() === 'GET') {
        const url = new URL(route.request().url());
        qs.push(url.searchParams.get('q') ?? '');
        await route.fulfill({
          status: 200,
          json: listPage([CLIENTES_LIST[1]], 1),
        });
      }
    });
    await page.goto('/clientes');
    await page.locator('#searchClientes').fill('Gómez');
    await page.getByRole('button', { name: 'Buscar' }).click();
    await expect(page.getByText('Luis Fernando Gómez')).toBeVisible();
    expect(qs).toContain('Gómez');
  });

  test('ADMIN filtra por estado de identidad', async ({ page }) => {
    const identidades: string[] = [];
    await page.route(/\/api\/clientes(\?.*)?$/, async (route) => {
      if (route.request().method() === 'GET') {
        const url = new URL(route.request().url());
        identidades.push(url.searchParams.get('identity_status') ?? '');
        await route.fulfill({
          status: 200,
          json: listPage([CLIENTES_LIST[2]], 1),
        });
      }
    });
    await page.goto('/clientes');
    await page.locator('#filterIdentity').selectOption('POSSIBLE_DUPLICATE');
    await expect(page.getByText('Marta Elena Ruiz')).toBeVisible();
    expect(identidades).toContain('POSSIBLE_DUPLICATE');
  });

  test('ADMIN filtra por tipo de documento', async ({ page }) => {
    const tipos: string[] = [];
    await page.route(/\/api\/clientes(\?.*)?$/, async (route) => {
      if (route.request().method() === 'GET') {
        const url = new URL(route.request().url());
        tipos.push(url.searchParams.get('tipo_documento') ?? '');
        await route.fulfill({
          status: 200,
          json: listPage([CLIENTES_LIST[2]], 1),
        });
      }
    });
    await page.goto('/clientes');
    await page.locator('#filterTipoDoc').selectOption('CE');
    await expect(page.getByText('Marta Elena Ruiz')).toBeVisible();
    expect(tipos).toContain('CE');
  });

  test('ADMIN pagina la lista (offset)', async ({ page }) => {
    const offsets: number[] = [];
    await page.route(/\/api\/clientes(\?.*)?$/, async (route) => {
      if (route.request().method() === 'GET') {
        const url = new URL(route.request().url());
        offsets.push(parseInt(url.searchParams.get('offset') || '0', 10));
        const offset = offsets[offsets.length - 1];
        const items = Array.from({ length: 25 }, (_, i) => ({
          ...CLIENTES_LIST[0],
          id: `cli-page-${offset + i}`,
          nombres: `Cliente ${offset + i + 1}`,
        }));
        await route.fulfill({ status: 200, json: listPage(items, 60, 25, offset) });
      }
    });
    await page.goto('/clientes');
    await expect(page.getByText('Mostrando 1–25 de 60')).toBeVisible();
    await page.getByRole('button', { name: 'Siguiente' }).click();
    await expect(page.getByText('Mostrando 26–50 de 60')).toBeVisible();
    await page.getByRole('button', { name: 'Anterior' }).click();
    await expect(page.getByText('Mostrando 1–25 de 60')).toBeVisible();
    expect(offsets[0]).toBe(0);
    expect(offsets).toContain(25);
    expect(offsets[offsets.length - 1]).toBe(0);
  });

  test('ADMIN crea cliente (POST body sin identidad)', async ({ page }) => {
    let creado = false;
    let body: Record<string, unknown> | null = null;
    await page.route(/\/api\/clientes(\?.*)?$/, async (route) => {
      if (route.request().method() === 'GET') {
        await route.fulfill({ status: 200, json: listPage([], 0) });
      } else if (route.request().method() === 'POST') {
        creado = true;
        body = route.request().postDataJSON();
        expect(body.primer_apellido).toBe('Zapata');
        expect(body.nombres).toBe('Juan Carlos');
        expect(body.ciudad).toBe('Cali');
        // extra=forbid: la identidad no se envia en la creacion.
        expect('identity_status' in body).toBe(false);
        await route.fulfill({
          status: 201,
          json: {
            id: 'cli-nuevo-uuid',
            negocio_id: 'n1',
            tipo_documento: null,
            documento_normalizado: null,
            identity_status: 'PROVISIONAL',
            primer_apellido: 'Zapata',
            segundo_apellido: null,
            nombres: 'Juan Carlos',
            telefono_1: null,
            telefono_2: null,
            direccion: null,
            barrio: null,
            ciudad: 'Cali',
            ocupacion: null,
            creado_el: new Date().toISOString(),
          },
        });
      }
    });
    await page.goto('/clientes');
    await page.getByRole('button', { name: 'Nuevo Cliente' }).click();
    await page.locator('#nuevo-primer_apellido').fill('Zapata');
    await page.locator('#nuevo-nombres').fill('Juan Carlos');
    await page.locator('#nuevo-ciudad').fill('Cali');
    await page.getByRole('button', { name: 'Crear Cliente' }).click();
    await expect(page.getByRole('button', { name: 'Nuevo Cliente' })).toBeVisible();
    expect(creado).toBe(true);
  });

  test('ADMIN edita cliente (prefill 360, PATCH sin documento)', async ({ page }) => {
    let patchBody: Record<string, unknown> | null = null;
    let patched = false;
    const ana = CLIENTES_LIST[0];
    await page.route(/\/api\/clientes(\?.*)?$/, async (route) => {
      if (route.request().method() === 'GET') {
        await route.fulfill({ status: 200, json: listPage([ana], 1) });
      }
    });
    await page.route(/\/api\/clientes\/[^/]+(\?.*)?$/, async (route) => {
      if (route.request().method() === 'GET') {
        await route.fulfill({ status: 200, json: CLI_ANA });
      } else if (route.request().method() === 'PATCH') {
        patched = true;
        patchBody = route.request().postDataJSON();
        await route.fulfill({
          status: 200,
          json: { ...CLI_ANA, ciudad: patchBody.ciudad },
        });
      }
    });
    await page.goto('/clientes');
    await page.getByRole('button', { name: 'Editar Ana María Torres' }).click();
    // El modal precarga desde el detalle 360 (ClienteListItem es lean).
    await expect(page.locator('[role="dialog"]')).toBeVisible();
    await expect(page.locator('#edit-telefono_2')).toHaveValue('3019876543');
    await expect(page.locator('#edit-direccion')).toHaveValue('Calle 10 # 5-20');
    await page.locator('#edit-ciudad').fill('Medellín');
    await page.getByRole('button', { name: 'Guardar' }).click();
    expect(patched).toBe(true);
    expect(patchBody.ciudad).toBe('Medellín');
    // La identidad NO es editable: el PATCH nunca lleva el documento.
    expect('tipo_documento' in (patchBody ?? {})).toBe(false);
    expect('documento_normalizado' in (patchBody ?? {})).toBe(false);
  });

  test('ADMIN ve detalle 360 (saldo, mora, ruta, cobrador, pagos)', async ({ page }) => {
    await page.route(/\/api\/clientes\/[^/]+(\?.*)?$/, async (route) => {
      if (route.request().method() === 'GET') {
        await route.fulfill({ status: 200, json: CLI_ANA });
      }
    });
    await page.goto('/clientes/cli-11111111-1111-4111-8111-111111111111');
    await expect(page.locator('h1')).toContainText('Ana María Torres');
    await expect(page.getByText('Verificado')).toBeVisible();
    await expect(page.getByText(/800\.000/).first()).toBeVisible();
    await expect(page.getByText('Saldo total (créditos activos)')).toBeVisible();
    await expect(page.getByText('Abono')).toBeVisible();
    await expect(page.getByRole('cell', { name: 'ACTIVO', exact: true })).toBeVisible();
    await expect(page.getByText('Ruta Centro')).toBeVisible();
    await expect(page.getByText('Carlos Cobrador')).toBeVisible();
    await expect(page.getByRole('cell', { name: '5', exact: true })).toBeVisible();
  });
});

// ─── COBRADOR: scoped a su ruta, sin gestionar ────────────────────────────────

test.describe('W2 E2E: COBRADOR - Clientes scoped', () => {
  test.beforeEach(async ({ page }) => {
    await setSessionToken(page, 'mock-jwt-token');
  });

  test('COBRADOR ve navegacion Clientes', async ({ page }) => {
    await page.goto('/dashboard');
    await expect(page.getByRole('button', { name: 'Clientes' })).toBeVisible();
  });

  test('COBRADOR ve solo clientes de su ruta (mock scoped)', async ({ page }) => {
    await page.goto('/clientes');
    await expect(page.getByText('Ana María Torres')).toBeVisible();
    await expect(page.getByText('Luis Fernando Gómez')).toBeVisible();
    // Marta Elena está en Ruta Sur (r2); el cobrador de r1 no la ve.
    await expect(page.getByText('Marta Elena Ruiz')).toHaveCount(0);
  });

  test('COBRADOR no ve boton Nuevo Cliente (sin gestionar)', async ({ page }) => {
    await page.goto('/clientes');
    await expect(page.getByRole('button', { name: 'Nuevo Cliente' })).toHaveCount(0);
  });

  test('COBRADOR accede al detalle de cliente de su ruta', async ({ page }) => {
    await page.goto('/clientes/cli-11111111-1111-4111-8111-111111111111');
    await expect(page.locator('h1')).toContainText('Ana María Torres');
  });

  test('COBRADOR no ve cliente de otra ruta (404)', async ({ page }) => {
    await page.goto('/clientes/cli-33333333-3333-4333-8333-333333333333');
    await expect(page.getByText('Cliente no encontrado')).toBeVisible();
    await expect(page.getByRole('link', { name: 'Volver a Clientes' })).toBeVisible();
  });

  test('COBRADOR mutation POST /api/clientes -> 403', async ({ page }) => {
    const res = await page.request.post(`${MOCK}/api/clientes`, {
      headers: { Authorization: 'Bearer mock-jwt-token' },
      data: { primer_apellido: 'X', nombres: 'Y' },
    });
    expect(res.status()).toBe(403);
  });
});

// ─── INVERSIONISTA: sin Clientes (proteccion PII) ─────────────────────────────

test.describe('W2 E2E: INVERSIONISTA - sin Clientes', () => {
  test.beforeEach(async ({ page }) => {
    await setSessionToken(page, 'test-token');
  });

  test('INVERSIONISTA no ve navegacion Clientes', async ({ page }) => {
    await page.goto('/dashboard');
    await expect(page.getByRole('button', { name: 'Clientes' })).toHaveCount(0);
  });

  test('INVERSIONISTA accede a /clientes -> 403', async ({ page }) => {
    await page.goto('/clientes');
    await expect(page.locator('h1')).toContainText('Acceso denegado');
    await expect(page).toHaveURL(/\/clientes/);
  });

  test('INVERSIONISTA GET /api/clientes -> 403', async ({ page }) => {
    const res = await page.request.get(`${MOCK}/api/clientes`, {
      headers: { Authorization: 'Bearer test-token' },
    });
    expect(res.status()).toBe(403);
  });
});
