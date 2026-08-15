import { test, expect } from '@playwright/test';

const API_BASE = process.env.REAL_API_BASE ?? 'http://127.0.0.1:8001';

test.describe('Onboarding real (Etapa 3): alta de negocio → primer login del ADMINISTRADOR', () => {
  test('POST /api/onboarding/negocios real → login Web con el código bootstrap → identidad ADMINISTRADOR canónica', async ({ page }) => {
    // 1) Contrato real de alta atomica (sin auth previa: superficie pre-sesion).
    const nit = `90${Date.now().toString().slice(-8)}`; // NIT unico por corrida
    const res = await page.request.post(`${API_BASE}/api/onboarding/negocios`, {
      data: {
        nombre: `E2E Real ${nit}`,
        nit,
        administrador: { nombre: 'María Pérez', documento: 'CC 123456789' },
      },
    });
    expect(res.status(), 'onboarding real debe responder 201').toBe(201);
    const body = await res.json();

    // El contrato entrega el trinomio: negocio + admin inicial + codigo bootstrap.
    const negocioId = body.negocio.id;
    expect(body.negocio.nombre).toBe(`E2E Real ${nit}`);
    expect(body.negocio.pais).toBe('CO');
    expect(body.negocio.moneda).toBe('COP');
    expect(body.negocio.plan).toBe('basic');
    expect(body.negocio.estado_suscripcion).toBe('al_dia');
    expect(body.administrador.rol).toBe('ADMINISTRADOR');
    expect(body.administrador.negocio_id).toBe(negocioId);
    expect(body.siguiente_paso).toBe('activar_codigo');
    const codigo = body.codigo_activacion.token;
    expect(codigo.length).toBeGreaterThan(20);

    // 2) El NIT recien creado ya no se puede volver a registrar -> 409 (la
    //    frontera NIT es server-side, no del browser).
    const dup = await page.request.post(`${API_BASE}/api/onboarding/negocios`, {
      data: { nombre: 'Duplicado', nit, administrador: { nombre: 'Otro' } },
    });
    expect(dup.status(), 'NIT duplicado real debe responder 409').toBe(409);

    // 3) Primer login Web del ADMINISTRADOR con el codigo bootstrap (flujo
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

    // 4) Identidad canónica: /api/auth/me resuelve el rol desde la DB.
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

    // 5) /dashboard deja entrar al ADMINISTRADOR real (sin redirect al login).
    await page.goto('/dashboard');
    await expect(page.locator('h1')).toContainText('Dashboard financiero', { timeout: 15000 });
  });
});
