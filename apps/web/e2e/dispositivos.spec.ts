import { test, expect } from '@playwright/test';
import { setSessionToken } from './helpers/session';

// El mock NO se re-siembra por GET (persistencia fiel al backend): las
// mutaciones sobreviven dentro del test y el reset entre tests es EXPLICITO
// via el endpoint test-only del mock. Los tests de este describe son seriales
// (comparten el store del mock) y cada uno parte del fixture.
test.describe.configure({ mode: 'serial' });

test.describe('Dispositivos autorizados (Etapa 3)', () => {
  test.beforeEach(async () => {
    const mockPort = process.env.MOCK_API_PORT ?? '8100';
    const res = await fetch(`http://127.0.0.1:${mockPort}/api/_test/reset-dispositivos`, {
      method: 'POST',
    });
    expect(res.status).toBe(200);
  });

  test('ADMINISTRADOR: renderiza listado con estados reales del contrato', async ({ page }) => {
    await setSessionToken(page, 'mock-admin');
    await page.goto('/dispositivos');
    await expect(page.locator('h1')).toContainText('Dispositivos autorizados');
    // Fixture: ACTIVE (Galaxy) + REVOKED (iPhone, Moto) + REPLACED (Redmi)
    await expect(page.locator('.badge-success')).toContainText('Autorizado');
    await expect(page.locator('.badge-danger')).toHaveCount(2);
    await expect(page.locator('.badge-danger').first()).toContainText('Revocado');
    await expect(page.locator('.badge-warning')).toContainText('Reemplazado');
    await expect(page.locator('body')).toContainText('Galaxy A54');
    await expect(page.locator('body')).toContainText('iPhone 12');
    await expect(page.locator('body')).toContainText('Redmi Note 12');
  });

  test('ADMINISTRADOR: la API NO envía secretos (DTO admin minimizado)', async ({ page }) => {
    await setSessionToken(page, 'mock-admin');
    // Captura la respuesta real del listado: verifica a nivel de red que el
    // DTO admin minimizado nunca expone secretos ni tenancy interno.
    const resPromise = page.waitForResponse(
      (r) => r.url().includes('/api/dispositivos') && r.request().method() === 'GET',
    );
    await page.goto('/dispositivos');
    const res = await resPromise;
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(Array.isArray(body)).toBe(true);
    for (const dev of body) {
      for (const campo of ['huella', 'public_key_hash', 'algoritmo_clave', 'negocio_id', 'autorizado_por']) {
        expect(dev).not.toHaveProperty(campo);
      }
    }
    // Y a nivel DOM tampoco
    const dom = page.locator('body');
    await expect(dom).not.toContainText('public_key');
    await expect(dom).not.toContainText('private_key');
    await expect(dom).not.toContainText('sha256');
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

  test('ADMINISTRADOR: un ACTIVE no ofrece "Generar código" (el camino es Reemplazar)', async ({ page }) => {
    // RBAC review: generar un código nuevo para un cobrador con dispositivo
    // ACTIVE choca con la invariante de UN ACTIVE por cobrador (409). La UI
    // no ofrece ese flujo inválido; la renovación del dispositivo es Reemplazar.
    await setSessionToken(page, 'mock-admin');
    await page.goto('/dispositivos');
    const activeCard = page.locator('li', { hasText: 'Galaxy A54' });
    await expect(activeCard.getByRole('button', { name: 'Generar código' })).toHaveCount(0);
    await expect(activeCard.getByRole('button', { name: 'Reemplazar' })).toBeVisible();
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

  test('ADMINISTRADOR: confirmación discriminada — Revocar NO ofrece Confirmar reemplazo', async ({ page }) => {
    await setSessionToken(page, 'mock-admin');
    await page.goto('/dispositivos');
    const activeCard = page.locator('li', { hasText: 'Galaxy A54' });
    await activeCard.getByRole('button', { name: 'Revocar' }).click();
    await expect(activeCard.getByRole('button', { name: 'Confirmar revocación' })).toBeVisible();
    await expect(
      activeCard.getByRole('button', { name: 'Confirmar reemplazo (genera código nuevo)' }),
    ).toHaveCount(0);
    await activeCard.getByRole('button', { name: 'Cancelar' }).click();
    await expect(activeCard.getByRole('button', { name: 'Confirmar revocación' })).toHaveCount(0);
    await expect(
      activeCard.getByRole('button', { name: 'Confirmar reemplazo (genera código nuevo)' }),
    ).toHaveCount(0);
  });

  test('ADMINISTRADOR: confirmación discriminada — Reemplazar NO ofrece Confirmar revocación', async ({ page }) => {
    await setSessionToken(page, 'mock-admin');
    await page.goto('/dispositivos');
    const activeCard = page.locator('li', { hasText: 'Galaxy A54' });
    await activeCard.getByRole('button', { name: 'Reemplazar' }).click();
    await expect(
      activeCard.getByRole('button', { name: 'Confirmar reemplazo (genera código nuevo)' }),
    ).toBeVisible();
    await expect(activeCard.getByRole('button', { name: 'Confirmar revocación' })).toHaveCount(0);
    await activeCard.getByRole('button', { name: 'Cancelar' }).click();
    await expect(
      activeCard.getByRole('button', { name: 'Confirmar reemplazo (genera código nuevo)' }),
    ).toHaveCount(0);
    await expect(activeCard.getByRole('button', { name: 'Confirmar revocación' })).toHaveCount(0);
  });

  test('ADMINISTRADOR: reactivar con otro ACTIVE del mismo cobrador muestra 409 de producto', async ({ page }) => {
    // Moto G84 (REVOKED) es del MISMO cobrador que Galaxy A54 (ACTIVE): el
    // backend/mock responde 409 y la UI muestra el mensaje de producto, no el
    // detalle técnico crudo "API error 409: {...}".
    await setSessionToken(page, 'mock-admin');
    await page.goto('/dispositivos');
    const card = page.locator('li', { hasText: 'Moto G84' });
    await card.getByRole('button', { name: 'Reactivar' }).click();
    await expect(page.locator('.flash-error')).toContainText(
      'No se puede reactivar este dispositivo porque el cobrador ya tiene otro dispositivo activo.',
    );
    await expect(page.locator('.flash-error')).not.toContainText('API error');
  });

  test('ADMINISTRADOR: la revocación persiste tras un nuevo GET (el mock no se re-siembra por GET)', async ({ page }) => {
    await setSessionToken(page, 'mock-admin');
    await page.goto('/dispositivos');
    const activeCard = page.locator('li', { hasText: 'Galaxy A54' });
    await activeCard.getByRole('button', { name: 'Revocar' }).click();
    await activeCard.getByRole('button', { name: 'Confirmar revocación' }).click();
    await expect(page.locator('li', { hasText: 'Galaxy A54' }).locator('.badge-danger')).toContainText('Revocado');
    // Nuevo GET: el estado REVOKED sobrevive a la re-carga (mutación persistida).
    await page.goto('/dispositivos');
    await expect(page.locator('li', { hasText: 'Galaxy A54' }).locator('.badge-danger')).toContainText('Revocado');
    await expect(page.locator('li', { hasText: 'Galaxy A54' }).getByRole('button', { name: 'Revocar' })).toHaveCount(0);
  });

  test('ADMINISTRADOR: la tarjeta no muestra el UUID del cobrador como "Cobrador"', async ({ page }) => {
    await setSessionToken(page, 'mock-admin');
    await page.goto('/dispositivos');
    // El contrato no entrega nombre humano; la UI no inventa ni recorta UUIDs.
    await expect(page.locator('body')).not.toContainText('Cobrador');
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
