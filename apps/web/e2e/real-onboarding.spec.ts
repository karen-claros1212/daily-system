import { test, expect } from '@playwright/test';

const API_BASE = process.env.REAL_API_BASE ?? 'http://127.0.0.1:8001';

test.describe('Onboarding real (Etapa 3): /registro → BFF → FastAPI → Postgres → primer login del ADMINISTRADOR', () => {
  test('alta desde la UI → codigo leido del DOM → login bootstrap → identidad ADMINISTRADOR canónica', async ({ page }) => {
    const nit = `90${Date.now().toString().slice(-8)}`; // NIT unico por corrida

    // 1) Happy path REAL desde /registro: el formulario Web pasa por el BFF
    //    (proxyPostPublic) hasta FastAPI y Postgres reales. Sin auth previa.
    let negocioId: string | null = null;
    page.on('response', (res) => {
      if (res.url().includes('/api/onboarding/negocios') && res.status() === 201) {
        res.json().then((body) => {
          negocioId = body?.negocio?.id ?? null;
        });
      }
    });

    await page.goto('/registro');
    await expect(page.locator('#registroTitle')).toBeVisible();
    await page.locator('#negocioNombre').fill(`E2E Real ${nit}`);
    await page.locator('#nitNegocio').fill(nit);
    await page.locator('#adminNombre').fill('María Pérez');
    await page.locator('#adminDocumento').fill('CC 123456789');
    await page.locator('#registroBtn').click();

    // 2) El codigo bootstrap se lee de la UI (se entrega UNA vez).
    await expect(page.locator('#registroOkTitle')).toBeVisible({ timeout: 15000 });
    await expect(page.locator('body')).toContainText(`E2E Real ${nit}`);
    await expect(page.locator('body')).toContainText('María Pérez');
    const codigo = (await page.locator('#activationCodeResult').textContent())?.trim() ?? '';
    expect(codigo.length).toBeGreaterThan(20);
    // TTL derivado de expira_el del contrato real (10 min server-side).
    await expect(page.locator('#activationCodeHint')).toContainText('vence en');

    expect(negocioId, 'debe capturarse el negocio creado desde la respuesta del BFF').not.toBeNull();

    // 3) El NIT recien creado ya no se puede volver a registrar -> 409 real
    //    (autoridad server-side uq_negocio_nit, no del browser).
    const dup = await page.request.post(`${API_BASE}/api/onboarding/negocios`, {
      data: { nombre: 'Duplicado', nit, administrador: { nombre: 'Otro' } },
    });
    expect(dup.status(), 'NIT duplicado real debe responder 409').toBe(409);

    // 4) Primer login Web del ADMINISTRADOR con el codigo bootstrap (flujo
    //    existente de activacion diario: activar -> desafio -> canje -> cookie).
    await page.goto('/');
    await expect(page.locator('#loginTitle')).toBeVisible();
    await page.fill('#activationCode', codigo);
    await page.locator('#loginBtn').click();
    await expect(async () => {
      const cookies = await page.context().cookies();
      expect(cookies.find((c) => c.name === 'daily_admin_token')).toBeTruthy();
    }).toPass({ timeout: 15000 });

    const cookies = await page.context().cookies();
    const session = cookies.find((c) => c.name === 'daily_admin_token');
    expect(session!.httpOnly, 'cookie debe ser httpOnly').toBe(true);

    // 5) Identidad canónica: /api/auth/me resuelve el rol desde la DB.
    const me = await page.request.get(`${API_BASE}/api/auth/me`, {
      headers: { Authorization: `Bearer ${session!.value}` },
    });
    expect(me.status(), 'me debe resolver identidad desde la DB').toBe(200);
    const meBody = await me.json();

    // El admin del onboarding nace ADMINISTRADOR con el negocio exacto.
    expect(meBody.rol, 'el admin creado por onboarding es ADMINISTRADOR').toBe('ADMINISTRADOR');
    expect(meBody.negocio.negocio_id, 'el tenancy de /me debe apuntar al negocio creado').toBe(negocioId);
    expect(meBody.negocio.nombre).toBe(`E2E Real ${nit}`);
    expect(meBody.negocio.plan).toBe('basic');
    expect(meBody.negocio.suscripcion_activa, 'negocio recien creado arranca al_dia').toBe(true);
    expect(meBody.capabilities).toContain('codigos:crear');
    expect(meBody.capabilities).toContain('dispositivos:registrar');

    // 6) /dashboard deja entrar al ADMINISTRADOR real (sin redirect al login).
    //    W8: el dashboard de ADMIN es el Ejecutivo (el financiero es de INV, W9).
    await page.goto('/dashboard');
    await expect(page.locator('h1')).toContainText('Dashboard ejecutivo', { timeout: 15000 });
  });

  test('concurrencia HTTP real: dos POST mismo NIT -> [201, 409] (uq_negocio_nit en PG)', async ({ request }) => {
    const nit = `9${Date.now().toString().slice(-8)}`; // NIT unico por corrida
    const payload = {
      nombre: `E2E Concurso ${nit}`,
      nit,
      administrador: { nombre: 'Admin' },
    };

    // Dos POST concurrentes contra FastAPI + PostgreSQL reales (sin mock),
    // como si vinieran de dos clientes distintos. La cadena certificada:
    // HTTP route -> service -> uq_negocio_nit -> IntegrityError -> 409.
    const [r1, r2] = await Promise.all([
      request.post(`${API_BASE}/api/onboarding/negocios`, { data: payload }),
      request.post(`${API_BASE}/api/onboarding/negocios`, { data: payload }),
    ]);

    const statuses = [r1.status(), r2.status()].sort((a, b) => a - b);
    expect(statuses, 'una POST debe ganar la carrera (201) y la otra chocar con el indice unico (409)').toEqual([201, 409]);
    // Nunca [201, 201] ni 500: la invariante la garantiza uq_negocio_nit en PG.
  });
});
