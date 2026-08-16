import { test, expect } from '@playwright/test';
import { setSessionToken, clearSession } from './helpers/session';

const MOCK = `http://localhost:${process.env.MOCK_API_PORT || 8100}`;

// ─── ADMIN: Usuarios ──────────────────────────────────────────────────────────

test.describe('W1 E2E: ADMIN - Usuarios', () => {
  test.beforeEach(async ({ page }) => {
    await setSessionToken(page, 'mock-admin');
  });

  test('ADMIN ve navigacion Usuarios y Auditoria', async ({ page }) => {
    await page.goto('/dashboard');
    await expect(page.getByRole('button', { name: 'Usuarios' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Auditoría' })).toBeVisible();
  });

  test('ADMIN accede a /usuarios', async ({ page }) => {
    await page.route('**/api/usuarios', async (route) => {
      await route.fulfill({
        status: 200,
        json: [
          {
            id: 'adm-11111111-1111-4111-8111-111111111111',
            rol: 'ADMINISTRADOR',
            nombre: 'Admin Principal',
            documento: '1234567890',
            activo: 1,
            creado_el: '2026-05-15T00:00:00Z',
          },
          {
            id: 'cob-22222222-2222-4222-8222-222222222222',
            rol: 'COBRADOR',
          nombre: 'Carlos Cobrador',
          documento: '9876543210',
          activo: 1,
          creado_el: '2026-06-15T00:00:00Z',
          },
        ],
      });
    });
    await page.goto('/usuarios');
    await expect(page.locator('h1')).toContainText('Gestión de Usuarios');
    await expect(page.getByText('Admin Principal')).toBeVisible();
    await expect(page.getByText('Carlos Cobrador')).toBeVisible();
  });

  test('ADMIN crea nuevo cobrador', async ({ page }) => {
    let creado = false;
    await page.route('**/api/usuarios', async (route) => {
      if (route.request().method() === 'GET') {
        await route.fulfill({ status: 200, json: [] });
      } else if (route.request().method() === 'POST') {
        creado = true;
        const body = route.request().json();
        expect(body.nombre).toBe('Nuevo Cobrador');
        expect(body.rol).toBe('COBRADOR');
        await route.fulfill({
          status: 201,
          json: {
            id: 'cob-new-uuid',
            negocio_id: 'n1',
            rol: 'COBRADOR',
            nombre: 'Nuevo Cobrador',
            documento: null,
            activo: 1,
            creado_el: new Date().toISOString(),
          },
        });
      }
    });
    await page.goto('/usuarios');
    await page.getByRole('button', { name: 'Nuevo Usuario' }).click();
    await page.locator('#nombre').fill('Nuevo Cobrador');
    await page.locator('#rol').selectOption('COBRADOR');
    await page.getByRole('button', { name: 'Crear Usuario' }).click();
    await expect(page.getByText('Nuevo Cobrador')).toBeVisible();
    expect(creado).toBe(true);
  });

  test('ADMIN crea inversionista', async ({ page }) => {
    let creado = false;
    await page.route('**/api/usuarios', async (route) => {
      if (route.request().method() === 'GET') {
        await route.fulfill({ status: 200, json: [] });
      } else if (route.request().method() === 'POST') {
        creado = true;
        const body = route.request().json();
        expect(body.rol).toBe('INVERSIONISTA');
        await route.fulfill({
          status: 201,
          json: {
            id: 'inv-new-uuid',
            negocio_id: 'n1',
            rol: 'INVERSIONISTA',
            nombre: body.nombre,
            documento: null,
            activo: 1,
            creado_el: new Date().toISOString(),
          },
        });
      }
    });
    await page.goto('/usuarios');
    await page.getByRole('button', { name: 'Nuevo Usuario' }).click();
    await page.locator('#nombre').fill('Nuevo Inversionista');
    await page.locator('#rol').selectOption('INVERSIONISTA');
    await page.getByRole('button', { name: 'Crear Usuario' }).click();
    await expect(page.getByText('Nuevo Inversionista')).toBeVisible();
    expect(creado).toBe(true);
  });

  test('ADMIN edita usuario', async ({ page }) => {
    let editado = false;
    await page.route('**/api/usuarios', async (route) => {
      if (route.request().method() === 'GET') {
        const usuariosList = [{
          id: 'cob-22222222-2222-4222-8222-222222222222',
          rol: 'COBRADOR',
          nombre: 'Carlos Cobrador',
          documento: '9876543210',
          activo: 1,
          creado_el: '2026-06-15T00:00:00Z',
        }];
        await route.fulfill({ status: 200, json: usuariosList});
      } else if (route.request().method() === 'PATCH') {
        editado = true;
        const body = route.request().json();
        expect(body.nombre).toBe('Carlos Cobrador Editado');
        await route.fulfill({
          status: 200,
          json: {
            id: 'cob-22222222-2222-4222-8222-222222222222',
            negocio_id: 'n1',
            rol: 'COBRADOR',
            nombre: 'Carlos Cobrador Editado',
            documento: '9876543210',
            activo: 1,
            creado_el: '2026-06-15T00:00:00Z',
          },
        });
      }
    });
    await page.goto('/usuarios');
    await page.getByText('Carlos Cobrador').click();
    await page.locator('input[aria-label="Editar nombre"]').fill('Carlos Cobrador Editado');
    await page.getByRole('button', { name: 'Guardar' }).click();
    await expect(page.getByText('Carlos Cobrador Editado')).toBeVisible();
    expect(editado).toBe(true);
  });

  test('ADMIN desactiva usuario con confirmacion', async ({ page }) => {
    let desactivado = false;
    await page.route('**/api/usuarios/**/estado', async (route) => {
      if (route.request().method() === 'PATCH') {
        desactivado = true;
        const url = new URL(route.request().url());
        expect(url.searchParams.get('activo')).toBe('0');
        await route.fulfill({
          status: 200,
          json: {
            id: 'cob-22222222-2222-4222-8222-222222222222',
            negocio_id: 'n1',
            rol: 'COBRADOR',
            nombre: 'Carlos Cobrador',
            documento: '9876543210',
            activo: 0,
            creado_el: '2026-06-15T00:00:00Z',
          },
        });
      }
    });
    await page.route('**/api/usuarios', async (route) => {
      if (route.request().method() === 'GET') {
        const usuariosList = [{
          id: 'cob-22222222-2222-4222-8222-222222222222',
          rol: 'COBRADOR',
          nombre: 'Carlos Cobrador',
          documento: '9876543210',
          activo: 1,
          creado_el: '2026-06-15T00:00:00Z',
        }];
        await route.fulfill({ status: 200, json: usuariosList});
      }
    });
    await page.goto('/usuarios');
    await page.getByRole('button', { name: 'Desactivar' }).click();
    // Modal de confirmacion
    await expect(page.locator('[role="dialog"]')).toBeVisible();
    await page.locator('#confirmName').fill('Carlos Cobrador');
    await page.getByRole('button', { name: 'Desactivar' }).click();
    expect(desactivado).toBe(true);
  });

  test('ADMIN genera codigo de activacion', async ({ page }) => {
    await page.route('**/api/activaciones/codigos', async (route) => {
      if (route.request().method() === 'POST') {
        const body = route.request().json();
        expect(body.usuario_id).toBe('cob-22222222-2222-4222-8222-222222222222');
        await route.fulfill({
          status: 201,
          json: {
            codigo_id: 'cod-uuid',
            token: 'mock-activation-token',
            prefijo: 'Xz8R4pQ2',
            expira_el: new Date(Date.now() + 60 * 60 * 1000).toISOString(),
          },
        });
      }
    });
    await page.route('**/api/usuarios', async (route) => {
      if (route.request().method() === 'GET') {
        const usuariosList = [{
          id: 'cob-22222222-2222-4222-8222-222222222222',
          rol: 'COBRADOR',
          nombre: 'Carlos Cobrador',
          documento: '9876543210',
          activo: 1,
          creado_el: '2026-06-15T00:00:00Z',
        }];
        await route.fulfill({ status: 200, json: usuariosList});
      }
    });
    await page.goto('/usuarios');
    await page.getByRole('button', { name: /Activación/ }).first().click();
    await expect(page.getByText('Código de activación generado')).toBeVisible();
    await expect(page.getByText('Xz8R4pQ2')).toBeVisible();
  });

  test('ADMIN filtra por rol', async ({ page }) => {
    await page.route('**/api/usuarios', async (route) => {
      if (route.request().method() === 'GET') {
        const url = new URL(route.request().url());
        expect(url.searchParams.get('rol')).toBe('COBRADOR');
        const usuariosList = [{
          id: 'cob-22222222-2222-4222-8222-222222222222',
          rol: 'COBRADOR',
          nombre: 'Carlos Cobrador',
          documento: '9876543210',
          activo: 1,
          creado_el: '2026-06-15T00:00:00Z',
        }];
        await route.fulfill({ status: 200, json: usuariosList});
      }
    });
    await page.goto('/usuarios');
    await page.locator('#filterRol').selectOption('COBRADOR');
    await page.getByRole('button', { name: 'Filtrar' }).click();
    await expect(page.getByText('Carlos Cobrador')).toBeVisible();
  });

  test('ADMIN filtra por estado', async ({ page }) => {
    await page.route('**/api/usuarios', async (route) => {
      if (route.request().method() === 'GET') {
        const url = new URL(route.request().url());
        expect(url.searchParams.get('activo')).toBe('0');
        const usuariosList = [{
          id: 'cob-44444444-4444-4444-8444-444444444444',
          rol: 'COBRADOR',
          nombre: 'Ana Inactiva',
          documento: '1111222233',
          activo: 0,
          creado_el: '2026-04-15T00:00:00Z',
        }];
        await route.fulfill({ status: 200, json: usuariosList});
      }
    });
    await page.goto('/usuarios');
    await page.locator('#filterActivo').selectOption('0');
    await page.getByRole('button', { name: 'Filtrar' }).click();
    await expect(page.getByText('Ana Inactiva')).toBeVisible();
  });

  // ─── ADMIN: Auditoría ──────────────────────────────────────────────────────

  test('ADMIN accede a /auditoria', async ({ page }) => {
    await page.route('**/api/audit', async (route) => {
      if (route.request().method() === 'GET') {
        await route.fulfill({
          status: 200,
          json: [
            {
              id: 'log-1',
              negocio_id: 'n1',
              actor_id: 'adm-11111111-1111-4111-8111-111111111111',
              actor_nombre: 'Admin Principal',
              action: 'USUARIO_CREADO',
              entity_type: 'USUARIO',
              entity_id: 'cob-22222222-2222-4222-8222-222222222222',
              metadata: { rol: 'COBRADOR' },
              ip_address: '192.168.1.100',
              user_agent: 'Mozilla/5.0',
              creado_el: '2026-06-15T10:00:00Z',
            },
          ],
        });
      }
    });
    await page.goto('/auditoria');
    await expect(page.locator('h1')).toContainText('Auditoría');
    await expect(page.getByText('Admin Principal')).toBeVisible();
    await expect(page.getByText('Usuario creado')).toBeVisible();
  });

  test('ADMIN filtra auditoria', async ({ page }) => {
    await page.route('**/api/audit', async (route) => {
      if (route.request().method() === 'GET') {
        const url = new URL(route.request().url());
        expect(url.searchParams.get('action')).toBe('USUARIO_CREADO');
        await route.fulfill({ status: 200, json: [] });
      }
    });
    await page.goto('/auditoria');
    await page.locator('#filterAction').fill('USUARIO_CREADO');
    await page.getByRole('button', { name: 'Filtrar' }).click();
  });

  test('ADMIN ve metadata expandible en auditoria', async ({ page }) => {
    await page.route('**/api/audit', async (route) => {
      if (route.request().method() === 'GET') {
        await route.fulfill({
          status: 200,
          json: [
            {
              id: 'log-detail',
              negocio_id: 'n1',
              actor_id: 'adm-11111111-1111-4111-8111-111111111111',
              actor_nombre: 'Admin Principal',
              action: 'USUARIO_CREADO',
              entity_type: 'USUARIO',
              entity_id: 'cob-22222222-2222-4222-8222-222222222222',
              metadata: { rol: 'COBRADOR', documento: '9876543210' },
              ip_address: '192.168.1.100',
              user_agent: 'Mozilla/5.0',
              creado_el: '2026-06-15T10:00:00Z',
            },
          ],
        });
      }
    });
    await page.goto('/auditoria');
    await page.getByRole('button', { name: /Ver/ }).first().click();
    await expect(page.locator('[role="dialog"], [class*="border-primary"]')).toBeVisible();
    await expect(page.getByText('"rol": "COBRADOR"')).toBeVisible();
  });
});

// ─── COBRADOR: sin Usuarios/Auditoria ─────────────────────────────────────────

test.describe('W1 E2E: COBRADOR - sin Usuarios/Auditoria', () => {
  test.beforeEach(async ({ page }) => {
    await setSessionToken(page, 'mock-jwt-token');
  });

  test('COBRADOR no ve navegacion Usuarios', async ({ page }) => {
    await page.goto('/dashboard');
    await expect(page.getByRole('button', { name: 'Usuarios' })).toHaveCount(0);
    await expect(page.getByRole('button', { name: 'Auditoría' })).toHaveCount(0);
  });

  test('COBRADOR accede a /usuarios -> 403', async ({ page }) => {
    await page.goto('/usuarios');
    await expect(page.locator('h1')).toContainText('Acceso denegado');
    await expect(page).toHaveURL(/\/usuarios/);
  });

  test('COBRADOR accede a /auditoria -> 403', async ({ page }) => {
    await page.goto('/auditoria');
    await expect(page.locator('h1')).toContainText('Acceso denegado');
    await expect(page).toHaveURL(/\/auditoria/);
  });

  test('COBRADOR mutation /api/usuarios -> 403', async ({ page }) => {
    const res = await page.request.get(`${MOCK}/api/usuarios`);
    expect(res.status()).toBe(403);
  });

  test('COBRADOR mutation /api/audit -> 403', async ({ page }) => {
    const res = await page.request.get(`${MOCK}/api/audit`);
    expect(res.status()).toBe(403);
  });
});

// ─── INVERSIONISTA: sin Usuarios/Auditoria ────────────────────────────────────

test.describe('W1 E2E: INVERSIONISTA - sin Usuarios/Auditoria', () => {
  test.beforeEach(async ({ page }) => {
    await setSessionToken(page, 'test-token');
  });

  test('INVERSIONISTA no ve navegacion Usuarios', async ({ page }) => {
    await page.goto('/dashboard');
    await expect(page.getByRole('button', { name: 'Usuarios' })).toHaveCount(0);
    await expect(page.getByRole('button', { name: 'Auditoría' })).toHaveCount(0);
  });

  test('INVERSIONISTA accede a /usuarios -> 403', async ({ page }) => {
    await page.goto('/usuarios');
    await expect(page.locator('h1')).toContainText('Acceso denegado');
    await expect(page).toHaveURL(/\/usuarios/);
  });

  test('INVERSIONISTA accede a /auditoria -> 403', async ({ page }) => {
    await page.goto('/auditoria');
    await expect(page.locator('h1')).toContainText('Acceso denegado');
    await expect(page).toHaveURL(/\/auditoria/);
  });

  test('INVERSIONISTA mutation /api/usuarios -> 403', async ({ page }) => {
    const res = await page.request.get(`${MOCK}/api/usuarios`);
    expect(res.status()).toBe(403);
  });

  test('INVERSIONISTA mutation /api/audit -> 403', async ({ page }) => {
    const res = await page.request.get(`${MOCK}/api/audit`);
    expect(res.status()).toBe(403);
  });
});
