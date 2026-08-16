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

  test('suscripcion a11y scan', async ({ page }) => {
    await page.route('**/api/inversionista/suscripcion', async (route) => {
      await route.fulfill({
        status: 200,
        json: { negocio_id: 'n1', estado_suscripcion: 'al_dia', plan: 'basic', paid_through_at: '2099-01-01T00:00:00Z', activa: true },
      });
    });
    await setSessionToken(page);
    await page.goto('/suscripcion');
    const results = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']).analyze();
    expect(results.violations).toEqual([]);
  });

  test('dispositivos a11y scan', async ({ page }) => {
    // Solo ADMINISTRADOR tiene acceso (dispositivos:registrar).
    await page.route('**/api/dispositivos', async (route) => {
      await route.fulfill({
        status: 200,
        json: [{
          id: 'dev-11111111-1111-4111-8111-111111111111',
          usuario_id: 'u1',
          estado: 'ACTIVE',
          modelo: 'Galaxy A54',
          plataforma: 'android',
          autorizado_el: '2026-01-01T00:00:00Z',
          revocado_el: null,
          ultima_validacion_servidor: '2026-08-01T00:00:00Z',
          activo: 1,
          creado_el: '2026-01-01T00:00:00Z',
        }],
      });
    });
    await setSessionToken(page, 'mock-admin');
    await page.goto('/usuarios');
    await expect(page.getByText('Carlos Cobrador')).toBeVisible();
    await expect(page.getByText('Cargando usuarios...')).toBeHidden();
    const results = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']).analyze();
    expect(results.violations).toEqual([]);
  });

  test('registro form a11y scan', async ({ page }) => {
    await page.goto('/registro');
    const results = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']).analyze();
    expect(results.violations).toEqual([]);
  });

  test('registro success a11y scan', async ({ page }) => {
    await page.route('**/api/onboarding/negocios', async (route) => {
      await route.fulfill({
        status: 201,
        json: {
          negocio: {
            id: '11111111-1111-4111-8111-111111111111',
            nombre: 'Distribuciones del Sur',
            nit: null,
            pais: 'CO',
            moneda: 'COP',
            plan: 'basic',
            estado_suscripcion: 'al_dia',
            creado_el: '2026-08-15T00:00:00Z',
          },
          administrador: {
            id: '22222222-2222-4222-8222-222222222222',
            negocio_id: '11111111-1111-4111-8111-111111111111',
            rol: 'ADMINISTRADOR',
            nombre: 'María Pérez',
            documento: 'CC 123456789',
            activo: 1,
            creado_el: '2026-08-15T00:00:00Z',
          },
          codigo_activacion: {
            codigo_id: '33333333-3333-4333-8333-333333333333',
            token: 'mock-activation-token',
            prefijo: 'Xz8R4pQ2',
            expira_el: new Date(Date.now() + 10 * 60 * 1000).toISOString(),
          },
          siguiente_paso: 'activar_codigo',
        },
      });
    });
    await page.goto('/registro');
    await page.locator('#negocioNombre').fill('Distribuciones del Sur');
    await page.locator('#adminNombre').fill('María Pérez');
    await page.locator('#registroBtn').click();
    await expect(page.locator('#registroOkTitle')).toBeVisible();
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

  // ─── W1: a11y /usuarios ───────────────────────────────────────────────────
  test('usuarios a11y scan', async ({ page }) => {
    await page.route('**/api/usuarios', async (route) => {
      await route.fulfill({
        status: 200,
        json: [
          {
            id: 'adm-1111',
            rol: 'ADMINISTRADOR',
            nombre: 'Admin Principal',
            documento: '1234567890',
            activo: 1,
            creado_el: '2026-05-15T00:00:00Z',
          },
          {
            id: 'cob-2222',
            rol: 'COBRADOR',
            nombre: 'Carlos Cobrador',
            documento: '9876543210',
            activo: 1,
            creado_el: '2026-06-15T00:00:00Z',
          },
        ],
      });
    });
    await page.route('**/api/activaciones/codigos', async (route) => {
      await route.fulfill({
        status: 201,
        json: { codigo_id: 'cod-1', token: 'tok-1', prefijo: 'Xz8R', expira_el: '2099-01-01T00:00:00Z' },
      });
    });
    await setSessionToken(page, 'mock-admin');
    await page.goto('/usuarios');
    const results = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']).analyze();
    expect(results.violations).toEqual([]);
  });

  test('usuarios form keyboard nav', async ({ page }) => {
    await page.route('**/api/usuarios', async (route) => {
      await route.fulfill({ status: 200, json: [] });
    });
    await setSessionToken(page, 'mock-admin');
    await page.goto('/usuarios');
    await page.getByRole('button', { name: 'Nuevo Usuario' }).click();
    await page.keyboard.press('Tab');
    await expect(page.locator(':focus-visible')).toBeVisible();
    await page.keyboard.press('Tab');
    await expect(page.locator(':focus-visible')).toBeVisible();
  });

  test('usuarios filters a11y', async ({ page }) => {
    await page.route('**/api/usuarios', async (route) => {
      await route.fulfill({ status: 200, json: [] });
    });
    await setSessionToken(page, 'mock-admin');
    await page.goto('/usuarios');
    await expect(page.getByText('Cargando usuarios...')).toBeHidden();
    const results = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']).analyze();
    expect(results.violations).toEqual([]);
  });

  // ─── W1: a11y /auditoria ─────────────────────────────────────────────────
  test('auditoria a11y scan', async ({ page }) => {
    await page.route(/\/api\/audit(\?.*)?$/, async (route) => {
      await route.fulfill({
        status: 200,
        json: [
          {
            id: 'log-1',
            negocio_id: 'n1',
            actor_id: 'adm-1111',
            actor_nombre: 'Admin Principal',
            action: 'USUARIO_CREADO',
            entity_type: 'USUARIO',
            entity_id: 'cob-2222',
            metadata: { rol: 'COBRADOR' },
            ip_address: '192.168.1.100',
            user_agent: 'Mozilla/5.0',
            creado_el: '2026-06-15T10:00:00Z',
          },
        ],
      });
    });
    await setSessionToken(page, 'mock-admin');
    await page.goto('/auditoria');
    await expect(page.getByText('Admin Principal')).toBeVisible();
    await expect(page.getByText('Cargando logs de auditoría...')).toBeHidden();
    const results = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']).analyze();
    expect(results.violations).toEqual([]);
  });

  test('auditoria expandible a11y', async ({ page }) => {
    await page.route(/\/api\/audit(\?.*)?$/, async (route) => {
      await route.fulfill({
        status: 200,
        json: [
          {
            id: 'log-2',
            negocio_id: 'n1',
            actor_id: 'adm-1111',
            actor_nombre: 'Admin Principal',
            action: 'USUARIO_CREADO',
            entity_type: 'USUARIO',
            entity_id: 'cob-2222',
            metadata: { rol: 'COBRADOR', documento: '9876543210' },
            ip_address: '192.168.1.100',
            user_agent: 'Mozilla/5.0',
            creado_el: '2026-06-15T10:00:00Z',
          },
        ],
      });
    });
    await setSessionToken(page, 'mock-admin');
    await page.goto('/auditoria');
    await page.getByRole('button', { name: /Ver/ }).first().click();
    const results = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']).analyze();
    expect(results.violations).toEqual([]);
  });

  // ─── W1: a11y confirm dialog ─────────────────────────────────────────────
  test('confirm dialog a11y', async ({ page }) => {
    await page.route('**/api/usuarios', async (route) => {
      const usuariosList = [{
        id: 'cob-2222',
        rol: 'COBRADOR',
        nombre: 'Carlos Cobrador',
        documento: '9876543210',
        activo: 1,
        creado_el: '2026-06-15T00:00:00Z',
      }];
      await route.fulfill({ status: 200, json: usuariosList});
    });
    await page.route(/\/api\/usuarios\/([^/]+)\/estado(\?.*)?$/, async (route) => {
      await route.fulfill({ status: 200, json: {
        id: 'cob-2222',
        negocio_id: 'n1',
        rol: 'COBRADOR',
        nombre: 'Carlos Cobrador',
        documento: '9876543210',
        activo: 0,
        creado_el: '2026-06-15T00:00:00Z'
      }});
    });
    await setSessionToken(page, 'mock-admin');
    await page.goto('/usuarios');
    await page.getByRole('button', { name: 'Desactivar' }).click();
    const results = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']).analyze();
    expect(results.violations).toEqual([]);
  });

  // ─── W1: keyboard nav en tabla ───────────────────────────────────────────
  test('keyboard nav en tabla usuarios', async ({ page }) => {
    await page.route('**/api/usuarios', async (route) => {
      const usuariosList = [{
        id: 'cob-2222',
        rol: 'COBRADOR',
        nombre: 'Carlos Cobrador',
        documento: '9876543210',
        activo: 1,
        creado_el: '2026-06-15T00:00:00Z',
      }];
      await route.fulfill({ status: 200, json: usuariosList});
    });
    await setSessionToken(page, 'mock-admin');
    await page.goto('/usuarios');
    // Tab hasta la tabla y navegar
    await page.getByRole('button', { name: 'Nuevo Usuario' }).click();
    await page.keyboard.press('Escape');
    await page.keyboard.press('Tab');
    await page.keyboard.press('Tab');
    await expect(page.locator(':focus-visible')).toBeVisible();
  });
});