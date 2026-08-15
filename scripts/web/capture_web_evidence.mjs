// capture_web_evidence.mjs — Captura de evidencia visual de Web Premium production-grade.
//
//   Drivea la UI real de Web Premium contra mock-api (mock contractual reproducible;
//   sin backend real) con Playwright: flujo de login por código de activación y captura
//   de cada pantalla con verificación de firma (rechaza capturas inválidas).
//   Cada captura se registra en manifest.json con SHA-256 + commit + timestamp,
//   espejando el patrón Android de docs/ui-audit/screenshots/manifest.json.
//
//   Roles usados (derivados del código, nunca del cliente): ADMINISTRADOR para
//   dashboard/suscripcion/rutas/reportes/dispositivos; COBRADOR para caja
//   (única capability 'jornada:ver'); login y registro son públicos.
//
// USO (normalmente invocado desde capture_web_evidence.sh):
//   node scripts/web/capture_web_evidence.mjs
// ENV:
//   CAPTURE_BASE_URL   (default http://localhost:3000)
//   CAPTURE_OUT_DIR    (default docs/assets/readme/web)
//   CAPTURE_CODE_ADMIN (default test-admin-code)
//   CAPTURE_CODE_COB   (default test-cobrador-code)
//   CAPTURE_VIEWPORT   (default 1440x900)
//   CAPTURE_NO_MANIFEST (1 = omitir manifest.json)

import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import fs from 'node:fs';
import crypto from 'node:crypto';
import { execSync } from 'node:child_process';

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(scriptDir, '..', '..');
const require = createRequire(path.join(repoRoot, 'apps/web', 'package.json'));
const { chromium } = require('@playwright/test');

const BASE = process.env.CAPTURE_BASE_URL || 'http://localhost:3000';
const OUT_DIR = process.env.CAPTURE_OUT_DIR || path.join(repoRoot, 'docs/assets/readme/web');
const CODE_ADMIN = process.env.CAPTURE_CODE_ADMIN || 'test-admin-code';
const CODE_COB = process.env.CAPTURE_CODE_COB || 'test-cobrador-code';
const IS_MOBILE = process.env.CAPTURE_MOBILE === '1';

// CAPTURE_VIEWPORT parsea "WxH" fail-closed (default desktop).
function parseViewport(env) {
  if (!env) return { width: 1440, height: 900 };
  const m = env.match(/^(\d+)x(\d+)$/);
  if (!m) throw new Error(`CAPTURE_VIEWPORT formato inválido: "${env}" — esperado WxH (ej: 1440x900)`);
  const [_, w, h] = m;
  const width = parseInt(w, 10);
  const height = parseInt(h, 10);
  if (width < 320 || height < 240) throw new Error(`CAPTURE_VIEWPORT dimensiones mínimas: ${width}x${height}`);
  return { width, height };
}
const VIEWPORT = parseViewport(process.env.CAPTURE_VIEWPORT);

// Cada paso: rol que debe estar autenticado ('admin' | 'cob' | null=logout) y
// la firma que valida que la pantalla correcta se renderizó.
// mobile: true = captura en set responsive (solo superficies principales).
const ALL_STEPS = [
  { name: 'login', url: `/`, wait: '#loginTitle', verify: '#loginTitle', role: null, mobile: true },
  { name: 'dashboard', url: `/dashboard`, wait: '.metric-card', verify: 'h1:has-text("Dashboard financiero")', role: 'admin', mobile: true },
  { name: 'suscripcion', url: `/suscripcion`, wait: 'h1:has-text("Suscripción")', verify: 'h1:has-text("Suscripción")', role: 'admin', mobile: false },
  { name: 'rutas', url: `/routes`, wait: 'h1:has-text("Rutas")', verify: 'h1:has-text("Rutas")', role: 'admin', mobile: true },
  { name: 'caja', url: `/caja`, wait: 'h1:has-text("Caja / Conciliación")', verify: 'h1:has-text("Caja / Conciliación")', role: 'cob', mobile: false },
  { name: 'reportes', url: `/reportes`, wait: 'h1:has-text("Reportes")', verify: 'h1:has-text("Reportes")', role: 'admin', mobile: false },
  { name: 'dispositivos', url: `/dispositivos`, wait: 'h1:has-text("Dispositivos autorizados")', verify: 'h1:has-text("Dispositivos autorizados")', role: 'admin', mobile: true },
  { name: 'registro', url: `/registro`, wait: '#registroTitle', verify: '#registroTitle', role: null, mobile: true },
];

// Filtrar: si IS_MOBILE, solo pasos con mobile=true; si no, todos.
const STEPS = IS_MOBILE ? ALL_STEPS.filter((s) => s.mobile) : ALL_STEPS;
const PREFIXES = ['01', '02', '03', '04', '05', '06', '07', '08'];
const PREFIX = (i) => PREFIXES[i];

const log = (m) => console.log(`  ${m}`);
const die = (m) => { console.error(`ERROR: ${m}`); process.exit(1); };

async function logout(page) {
  try { await page.request.post(`${BASE}/api/auth/logout`); } catch {}
  await page.context().clearCookies();
  await page.goto(`${BASE}/`, { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('#loginTitle', { timeout: 15000 });
}

async function login(page, code) {
  await logout(page);
  await page.fill('#activationCode', code);
  await page.click('#loginBtn');
  await page.waitForSelector('.metric-card', { timeout: 15000 });
  log(`login OK (${code}) → dashboard`);
}

async function main() {
  if (!process.env.CAPTURE_BASE_URL) {
    try {
      const res = await fetch(`${BASE}/`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
    } catch (e) {
      die(`servidor no responde en ${BASE} (arrancar mock-api + npm run dev) — ${e.message}`);
    }
  }

  fs.mkdirSync(OUT_DIR, { recursive: true });
  const commit = execSync('git rev-parse HEAD', { cwd: repoRoot }).toString().trim();
  const ts = new Date().toISOString().slice(0, 19).replace(/[:T]/g, '-');

  const browser = await chromium.launch();
  const context = await browser.newContext({ viewport: VIEWPORT, deviceScaleFactor: 1 });
  const page = await context.newPage();
  const captures = [];

  for (let i = 0; i < STEPS.length; i++) {
    const s = STEPS[i];
    if (s.role === 'admin') await login(page, CODE_ADMIN);
    if (s.role === 'cob') await login(page, CODE_COB);
    if (s.role === null) await logout(page);

    await page.goto(`${BASE}${s.url}`, { waitUntil: 'domcontentloaded' });
    await page.waitForSelector(s.wait, { timeout: 15000 }).catch(() => {});
    await page.waitForTimeout(800);

    const sigOk = await page.locator(s.verify).count().then((n) => n > 0).catch(() => false);
    if (!sigOk) die(`'${s.name}' no contiene la firma '${s.verify}' — captura inválida`);

    const file = path.join(OUT_DIR, `${PREFIX(i)}-${s.name}.png`);
    await page.screenshot({ path: file, fullPage: true });
    const size = fs.statSync(file).size;
    const sha = crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
    captures.push({
      screen: s.name,
      path: `${PREFIX(i)}-${s.name}.png`,
      size_bytes: size,
      sha256: sha,
      url: `${BASE}${s.url}`,
      role: s.role ?? 'publico',
      viewport: `${VIEWPORT.width}x${VIEWPORT.height}`,
      commit,
      timestamp: ts,
    });
    log(`capture '${s.name}' → ${path.relative(repoRoot, file)} (${size} bytes)`);
  }

  await browser.close();

  if (process.env.CAPTURE_NO_MANIFEST !== '1') {
    const manifest = path.join(OUT_DIR, 'manifest.json');
    fs.writeFileSync(
      manifest,
      JSON.stringify(
        {
          generated: ts,
          commit,
          engine: 'nextjs-16 + react-19 + tailwind',
          mode: 'mock contractual reproducible; sin backend real',
          base_url: BASE,
          captures,
        },
        null,
        2,
      ) + '\n',
    );
    log(`manifest → ${path.relative(repoRoot, manifest)} (${captures.length} capturas)`);
  }
  console.log('Done.');
}

main().catch((e) => { console.error(e); process.exit(1); });
