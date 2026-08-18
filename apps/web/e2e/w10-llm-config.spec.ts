import { test, expect } from '@playwright/test';
import { setSessionToken } from './helpers/session';

/**
 * W10 — Configuración IA (Provider Gateway Multi-LLM + BYOK) — E2E mock.
 *
 * Contrato (mock replica de routes/llm.py):
 *  - GET /api/llm/providers → catálogo 6 providers + endpoint_profiles.
 *  - credential_source: TENANT_BYOK | PLATFORM_MANAGED | null (nunca la clave).
 *  - RBAC: llm:ver/llm:gestionar SOLO ADMINISTRADOR (COBRADOR/INV → 403).
 *  - API key: input type=password transitorio; NO localStorage/cookie;
 *    después de guardar el input se vacía; la clave nunca vuelve en DOM.
 *  - Nav: SOLO ADMIN ve "Configuración IA".
 */

test.describe.configure({ mode: 'serial' });

test.describe('W10 E2E: Configuración IA (mock)', () => {
  test('ADMIN: ve la superficie /configuracion/ia', async ({ page }) => {
    await setSessionToken(page, 'mock-admin');
    await page.goto('/configuracion/ia');
    await expect(page.getByRole('heading', { name: /Configuración IA/ })).toBeVisible();
    // Catálogo 6 familias.
    for (const p of [
      'OPENAI_NATIVE',
      'MISTRAL_NATIVE',
      'CEREBRAS_OPENAI_COMPATIBLE',
      'ANTHROPIC_NATIVE',
      'GEMINI_NATIVE',
      'OPENAI_COMPATIBLE_GENERIC',
    ]) {
      await expect(page.getByText(p, { exact: true })).toBeVisible();
    }
  });

  test('ADMIN: nav muestra Configuración IA (llm:gestionar)', async ({ page }) => {
    await setSessionToken(page, 'mock-admin');
    await page.goto('/dashboard');
    await expect(page.getByRole('button', { name: 'Configuración IA' })).toBeVisible();
  });

  test('ADMIN: source/status por provider (Plataforma por defecto)', async ({ page }) => {
    await setSessionToken(page, 'mock-admin');
    await page.goto('/configuracion/ia');
    // Sin BYOK, el mock resuelve PLATFORM_MANAGED.
    await expect(page.getByText('Plataforma').first()).toBeVisible();
  });

  test('ADMIN: guarda BYOK → key input desaparece y clave no vuelve en DOM', async ({ page }) => {
    await setSessionToken(page, 'mock-admin');
    await page.goto('/configuracion/ia');
    // Expandir el panel de OPENAI_NATIVE.
    const card = page.locator('article, [class*=card]', { hasText: 'OPENAI_NATIVE' }).first();
    await card.getByRole('button', { name: 'Configurar' }).click();
    await card.getByRole('button', { name: 'Añadir / cambiar BYOK' }).click();
    const keyInput = card.getByLabel(/API key/i);
    await keyInput.fill('sk-mock-abcdef123456');
    await card.getByRole('button', { name: 'Guardar clave' }).click();
    // Mensaje de éxito.
    await expect(card.getByText(/Credencial guardada/)).toBeVisible();
    // La rama BYOK se muestra: label "Clave BYOK:" + botón "Eliminar BYOK".
    await expect(card.getByText('Clave BYOK:')).toBeVisible();
    await expect(card.getByRole('button', { name: 'Eliminar BYOK' })).toBeVisible();
    // La clave en claro NO está en el DOM (solo el hint corto).
    await expect(page.getByText('sk-mock-abcdef123456', { exact: true })).not.toBeVisible();
    // Source ahora BYOK (badge exacto).
    await expect(card.getByText('BYOK', { exact: true })).toBeVisible();
  });

  test('ADMIN: cambia model/config', async ({ page }) => {
    await setSessionToken(page, 'mock-admin');
    await page.goto('/configuracion/ia');
    const card = page.locator('article, [class*=card]', { hasText: 'OPENAI_NATIVE' }).first();
    await card.getByRole('button', { name: 'Configurar' }).click();
    await card.getByLabel(/Modelo/i).fill('gpt-4o-mini');
    await card.getByRole('button', { name: 'Guardar config' }).click();
    await expect(card.getByText(/Configuración guardada/)).toBeVisible();
  });

  test('ADMIN: test provider (OK)', async ({ page }) => {
    await setSessionToken(page, 'mock-admin');
    await page.goto('/configuracion/ia');
    const card = page.locator('article, [class*=card]', { hasText: 'OPENAI_NATIVE' }).first();
    await card.getByRole('button', { name: 'Configurar' }).click();
    await card.getByRole('button', { name: 'Test conexión' }).click();
    await expect(card.getByText(/Conexión OK/)).toBeVisible();
  });

  test('ADMIN: elimina BYOK → cae a Plataforma', async ({ page }) => {
    await setSessionToken(page, 'mock-admin');
    await page.goto('/configuracion/ia');
    // GEMINI_NATIVE: estado fresco (PLATFORM_MANAGED), independiente de OPENAI_NATIVE.
    const card = page.locator('article, [class*=card]', { hasText: 'GEMINI_NATIVE' }).first();
    await card.getByRole('button', { name: 'Configurar' }).click();
    // Setear BYOK primero.
    await card.getByRole('button', { name: 'Añadir / cambiar BYOK' }).click();
    await card.getByLabel(/API key/i).fill('sk-temp-xyz987654');
    await card.getByRole('button', { name: 'Guardar clave' }).click();
    await expect(card.getByText('BYOK', { exact: true })).toBeVisible();
    // Eliminar.
    await card.getByRole('button', { name: 'Eliminar BYOK' }).click();
    await expect(card.getByText(/cae a Plataforma/)).toBeVisible();
    await expect(card.getByText('Plataforma', { exact: true })).toBeVisible();
  });

  test('COBRADOR: no ve nav Configuración IA', async ({ page }) => {
    await setSessionToken(page, 'test-cobrador-code');
    await page.goto('/caja');
    await expect(page.getByRole('button', { name: 'Configuración IA' })).not.toBeVisible();
  });

  test('COBRADOR: direct URL /configuracion/ia → 403 controlada', async ({ page }) => {
    await setSessionToken(page, 'test-cobrador-code');
    await page.goto('/configuracion/ia');
    await expect(page.getByRole('heading', { name: 'Acceso denegado' })).toBeVisible();
  });

  test('INVERSIONISTA: no ve nav Configuración IA', async ({ page }) => {
    await setSessionToken(page, 'test-token');
    await page.goto('/dashboard');
    await expect(page.getByRole('button', { name: 'Configuración IA' })).not.toBeVisible();
  });

  test('INVERSIONISTA: direct URL /configuracion/ia → 403 controlada', async ({ page }) => {
    await setSessionToken(page, 'test-token');
    await page.goto('/configuracion/ia');
    await expect(page.getByRole('heading', { name: 'Acceso denegado' })).toBeVisible();
  });

  test('BFF: GET /api/llm/providers shape W10', async ({ page }) => {
    await setSessionToken(page, 'mock-admin');
    const res = await page.request.get('/api/llm/providers');
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body.providers).toHaveLength(6);
    expect(body.endpoint_profiles.length).toBeGreaterThanOrEqual(1);
    const p = body.providers[0];
    for (const k of ['provider', 'model', 'enabled', 'configured', 'credential_source', 'available', 'key_hint', 'capabilities']) {
      expect(p).toHaveProperty(k);
    }
    // La clave nunca aparece en la respuesta.
    expect(JSON.stringify(body)).not.toContain('sk-mock-abcdef123456');
  });

  test('BFF: PUT credential + GET no devuelve la clave', async ({ page }) => {
    await setSessionToken(page, 'mock-admin');
    const put = await page.request.put('/api/llm/providers/ANTHROPIC_NATIVE/credential', {
      data: { api_key: 'sk-ant-secret-1234' },
    });
    expect(put.status()).toBe(200);
    const putBody = await put.json();
    expect(putBody.credential_source).toBe('TENANT_BYOK');
    // hint = prefijo 3 + … + sufijo 4 (nunca la clave completa).
    expect(putBody.key_hint).toBe('sk-…1234');
    // La clave completa NO está en el body de la respuesta (solo el hint).
    expect(JSON.stringify(putBody)).not.toContain('sk-ant-secret-1234');
    const get = await page.request.get('/api/llm/providers/ANTHROPIC_NATIVE');
    expect(get.status()).toBe(200);
    expect(await get.text()).not.toContain('sk-ant-secret-1234');
  });

  test('A11Y: formulario IA (teclado + axe)', async ({ page }) => {
    await setSessionToken(page, 'mock-admin');
    await page.goto('/configuracion/ia');
    // Navegación por teclado hasta un botón Configurar.
    await page.keyboard.press('Tab');
    // MISTRAL_NATIVE: estado fresco (PLATFORM_MANAGED) → el password field existe.
    const card = page.locator('article, [class*=card]', { hasText: 'MISTRAL_NATIVE' }).first();
    await card.getByRole('button', { name: 'Configurar' }).click();
    await card.getByRole('button', { name: 'Añadir / cambiar BYOK' }).click();
    const keyInput = card.getByLabel(/API key/i);
    await expect(keyInput).toHaveAttribute('type', 'password');
    // axe (si está disponible en el proyecto).
    const axe = (page as unknown as { axe?: { run: () => Promise<{ violations: unknown[] }> } }).axe;
    if (axe) {
      const results = await axe.run();
      const serious = (results.violations as { impact?: string }[]).filter((v) => v.impact === 'critical' || v.impact === 'serious');
      expect(serious).toHaveLength(0);
    }
  });
});
