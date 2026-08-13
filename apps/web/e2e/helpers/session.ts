import { Page } from '@playwright/test';

export const SESSION_COOKIE = 'daily_admin_token';
const SITE_URL = 'http://localhost:3000';

export async function setSessionToken(page: Page, value = 'test-token') {
  await page.context().addCookies([{ name: SESSION_COOKIE, value, url: SITE_URL }]);
}

export async function clearSession(page: Page) {
  await page.context().clearCookies();
}

export function todayISO() {
  return new Date().toISOString().slice(0, 10);
}

export function daysAgoISO(days: number) {
  return new Date(Date.now() - days * 86400000).toISOString().slice(0, 10);
}

export const PORTFOLIO_FIXTURE = {
  portfolio: {
    rutas_activas: 3,
    cobradores_activos: 2,
    total_creditos_activos: 50,
    cartera_neta: 5000000,
    recaudo_hoy: 800000,
    jornada_cerrada_hoy: true,
  },
  negocio_nombre: 'Test Negocio',
  plan: 'basic',
  moneda: 'COP',
};