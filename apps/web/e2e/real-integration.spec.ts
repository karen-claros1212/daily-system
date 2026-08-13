import { test, expect } from '@playwright/test';
import { seedActivacion } from './helpers/real-seed';

const API_BASE = process.env.REAL_API_BASE ?? 'http://127.0.0.1:8001';

test.describe('Integración Web ↔ FastAPI real (gate E2E)', () => {
  let realCode: string;

  test.beforeAll(() => {
    // Seed reproducible por spec: revoca dispositivos previos y emite un
    // codigo PENDING fresco, para que la suite completa sea autocontenida.
    realCode = seedActivacion().codigo_activacion;
  });

  test('flujo auth real completo: activación → firma WebCrypto → sesión → cookie → hallazgo de rol', async ({ page }) => {
    // Gate crítico (Paso 2): el navegador corre el flujo real contra el BFF,
    // que a su vez llama al FastAPI real en :8001. El mock NO interviene.
    // Los requests hacia el backend salen del server (Node), no del browser:
    // aqui se verifican los endpoints BFF que el browser toca.
    await page.goto('/');
    await expect(page.locator('#loginTitle')).toBeVisible();

    const bffRequests: string[] = [];
    page.on('request', (req) => {
      const u = new URL(req.url());
      if (u.pathname.startsWith('/api/auth/web/') || u.pathname === '/api/auth/session') {
        bffRequests.push(req.method() + ' ' + u.pathname);
      }
    });

    await page.fill('#activationCode', realCode);
    await page.locator('#loginBtn').click();

    // El flujo completo: activacion daily-v1 -> bootstrap server-side ->
    // desafio sesion daily-auth-v1 -> canje -> cookie httpOnly.
    await expect(async () => {
      const cookies = await page.context().cookies();
      expect(cookies.find((c) => c.name === 'daily_admin_token')).toBeTruthy();
    }).toPass({ timeout: 15000 });

    const cookies = await page.context().cookies();
    const session = cookies.find((c) => c.name === 'daily_admin_token');
    expect(session!.httpOnly, 'cookie debe ser httpOnly').toBe(true);
    expect(session!.secure, 'en dev http no debe exigir Secure').toBe(false);

    // Los tres pasos BFF del contrato real se ejecutaron.
    const calls = bffRequests.join('\n');
    expect(calls).toContain('POST /api/auth/web/activar');
    expect(calls).toContain('POST /api/auth/web/canjear');
    expect(calls).toContain('POST /api/auth/session');

    // Identidad canónica: /api/auth/me resuelve el rol desde la DB (JWT real
    // de COBRADOR), NUNCA desde el JWT ni desde el método de login.
    const me = await page.request.get(`${API_BASE}/api/auth/me`, {
      headers: { Authorization: `Bearer ${session!.value}` },
    });
    expect(me.status(), 'me debe resolver identidad desde la DB').toBe(200);
    const meBody = await me.json();

    // El rol es COBRADOR (único que puede emitir el flujo daily-v1).
    expect(meBody.rol, 'el JWT emitido por el flujo es de COBRADOR').toBe('COBRADOR');

    // Fail-closed preservado: COBRADOR NO tiene la capability financiera.
    expect(meBody.capabilities).not.toContain('inversionista:resumen');
    expect(meBody.capabilities).toContain('jornada:ver');

    // Hallazgo de contrato que motivó el dictamen: /api/inversionista/resumen
    // exige INVERSIONISTA|ADMINISTRADOR; con un JWT real de COBRADOR -> 403.
    const res = await page.request.get(`${API_BASE}/api/inversionista/resumen`, {
      headers: { Authorization: `Bearer ${session!.value}` },
    });
    const body = await res.text();
    test.info().annotations.push({
      type: 'hallazgo-contrato',
      description:
        `GET /api/inversionista/resumen con JWT real de COBRADOR ` +
        `-> HTTP ${res.status()}: ${body}`,
    });
    expect(res.status(), 'el backend real sigue fail-closed para COBRADOR').toBe(403);

    // Consecuencia corregida: con la identidad canónica el web NO redirige al
    // login por un 403 de rol; /dashboard muestra la superficie de campo del
    // COBRADOR (sus propios endpoints), nunca el financiero.
    await page.goto('/dashboard');
    await expect(page.locator('h1')).toContainText('Mi jornada', { timeout: 15000 });
    await expect(page.locator('.metric-card')).toHaveCount(2);
    await expect(page.locator('.metric-label').filter({ hasText: 'Jornada' })).toBeVisible();

    // El COBRADOR no tiene acceso al financiero: /reportes -> vista 403 controlada
    // (sesión válida con permisos insuficientes), NO redirect silencioso al login.
    await page.goto('/reportes');
    await expect(page.locator('text=Acceso denegado')).toBeVisible({ timeout: 15000 });
  });
});