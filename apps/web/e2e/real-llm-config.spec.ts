import { test, expect } from '@playwright/test';
import { execSync } from 'node:child_process';
import path from 'node:path';

import { buildPayloadActivacion, buildPayloadAuth, base64UrlNoPad } from '../src/lib/auth/jcs';
import { rawToDerSignature, sha256Hex } from '../src/lib/auth/identity';
import { seedActivacion, type SeedOutput } from './helpers/real-seed';

/**
 * W10 — Provider Gateway Multi-LLM + BYOK contra FastAPI real (:8001) +
 * Postgres real + BFF Next.js (:3000) + fake provider local (ollama.internal).
 *
 * Cadena real: Browser → BFF → FastAPI → PostgreSQL → SecretStore → fake provider.
 * NO internet externo, NO keys reales (BYOK = "fake-ollama-key").
 *
 * Gates:
 *  - 6 providers en el catálogo (shape W10).
 *  - PUT config (model) persiste en PG.
 *  - PUT credential (BYOK) → key_hint corto, la clave NUNCA vuelve en la respuesta.
 *  - GET provider → credential_source TENANT_BYOK.
 *  - SecretStore: la clave en claro NO está en ninguna columna de PG (solo
 *    secret_ref opaco + key_hint).
 *  - test provider contra fake provider local (profile local-ollama) → OK.
 *  - DELETE credential → cae a PLATFORM_MANAGED.
 *  - RBAC: INVERSIONISTA/COBRADOR → 403 (llm:ver solo ADMIN).
 *  - BFF: /configuracion/ia renderiza para ADMIN.
 */

const API = process.env.REAL_API_BASE ?? 'http://127.0.0.1:8001';
const BFF = process.env.BFF_BASE ?? 'http://localhost:3000';
const DB_URL = process.env.REAL_DB_URL ?? 'postgresql://postgres:postgres@127.0.0.1:5432/daily_web_e2e_test';
const BYOK_KEY = 'fake-ollama-key';

// Query directa a PG para el chequeo SecretStore (la clave en claro no debe aparecer).
function queryDb(sql: string): string {
  const repo = path.resolve(__dirname, '..', '..', '..');
  const py = `
import os, sys
import psycopg2
conn = psycopg2.connect("${DB_URL}")
cur = conn.cursor()
cur.execute("""${sql}""")
rows = cur.fetchall()
conn.close()
for r in rows:
    print("\\t".join("" if v is None else str(v) for v in r))
`;
  return execSync('python3 -', {
    encoding: 'utf-8',
    input: py,
    env: { ...process.env },
  }).trim();
}

/** Flujo real de dispositivo del COBRADOR (activación + sesión daily-auth-v1). */
async function obtenerJwtCobrador(seed: SeedOutput): Promise<string> {
  const keyPair = await crypto.subtle.generateKey({ name: 'ECDSA', namedCurve: 'P-256' }, true, ['sign', 'verify']);
  const spki = new Uint8Array(await crypto.subtle.exportKey('spki', keyPair.publicKey));
  const spkiB64 = Buffer.from(spki).toString('base64');
  const publicKeyHash = await sha256Hex(spki);
  const signJcs = async (payload: Uint8Array) =>
    base64UrlNoPad(
      rawToDerSignature(
        new Uint8Array(await crypto.subtle.sign({ name: 'ECDSA', hash: 'SHA-256' }, keyPair.privateKey, payload)),
      ),
    );

  const d = await fetch(`${API}/api/activaciones/desafio`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ token: seed.codigo_activacion, clave_publica: spkiB64, modelo: 'web', plataforma: 'web' }),
  });
  expect(d.status).toBe(200);
  const desafioActivacion = (await d.json()) as { intento_id: string; nonce: string; expira_el: string; environment: string };
  const payloadActivacion = buildPayloadActivacion({
    protocolVersion: 'daily-v1',
    environment: desafioActivacion.environment,
    attemptId: desafioActivacion.intento_id,
    nonce: desafioActivacion.nonce,
    publicKeyHash,
    expiresAt: desafioActivacion.expira_el,
  });
  const rCanje = await fetch(`${API}/api/activaciones/canjear`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ intento_id: desafioActivacion.intento_id, firma: await signJcs(payloadActivacion) }),
  });
  expect(rCanje.status).toBe(200);
  const canje = (await rCanje.json()) as { credencial_bootstrap: string; dispositivo_id: string };

  const ds = await fetch(`${API}/api/auth/device/desafio`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${canje.credencial_bootstrap}` },
  });
  expect(ds.status).toBe(200);
  const desafioSesion = (await ds.json()) as { challenge_id: string; nonce: string; expira_el: string; environment: string };
  const payloadSesion = buildPayloadAuth({
    purpose: 'issue_access_token',
    environment: desafioSesion.environment,
    challengeId: desafioSesion.challenge_id,
    deviceId: canje.dispositivo_id,
    nonce: desafioSesion.nonce,
    publicKeyHash,
    expiresAt: desafioSesion.expira_el,
  });
  const cs = await fetch(`${API}/api/auth/device/canjear`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ challenge_id: desafioSesion.challenge_id, firma: await signJcs(payloadSesion) }),
  });
  expect(cs.status).toBe(200);
  return ((await cs.json()) as { token: string }).token;
}

test.describe.serial('W10 real: Provider Gateway Multi-LLM + BYOK (FastAPI :8001 + BFF :3000)', () => {
  let seed: SeedOutput;
  let jwtCobrador: string;
  const admin = () => ({ Authorization: `Bearer ${seed.tokens.administrador}` });
  const inv = () => ({ Authorization: `Bearer ${seed.tokens.inversionista}` });

  test.beforeAll(async () => {
    seed = seedActivacion();
    jwtCobrador = await obtenerJwtCobrador(seed);
  });

  test('1. ADMIN: GET /api/llm/providers → catálogo 6 (shape W10)', async () => {
    const r = await fetch(`${API}/api/llm/providers`, { headers: admin() });
    expect(r.status).toBe(200);
    const body = await r.json();
    expect(body.providers).toHaveLength(6);
    const names = body.providers.map((p: { provider: string }) => p.provider).sort();
    expect(names).toEqual(
      ['ANTHROPIC_NATIVE', 'CEREBRAS_OPENAI_COMPATIBLE', 'GEMINI_NATIVE', 'MISTRAL_NATIVE', 'OPENAI_COMPATIBLE_GENERIC', 'OPENAI_NATIVE'].sort(),
    );
    const p = body.providers[0];
    for (const k of ['provider', 'protocol', 'type', 'model', 'enabled', 'configured', 'credential_source', 'available', 'key_hint', 'capabilities']) {
      expect(p).toHaveProperty(k);
    }
    expect(body.endpoint_profiles.length).toBeGreaterThanOrEqual(1);
  });

  test('2. ADMIN: PUT config (model) persiste en PG', async () => {
    const r = await fetch(`${API}/api/llm/providers/OPENAI_NATIVE/config`, {
      method: 'PUT',
      headers: { ...admin(), 'Content-Type': 'application/json' },
      body: JSON.stringify({ model: 'gpt-4o-mini' }),
    });
    expect(r.status).toBe(200);
    const body = await r.json();
    expect(body.model).toBe('gpt-4o-mini');
    // Persistido en PG.
    const row = queryDb(
      `SELECT model FROM llm_provider_config WHERE negocio_id = '${seed.negocio_id}' AND provider = 'OPENAI_NATIVE'`,
    );
    expect(row).toBe('gpt-4o-mini');
  });

  test('3. ADMIN: PUT credential (BYOK) → key_hint, clave no vuelve', async () => {
    // OPENAI_NATIVE: provider nativo (no requiere endpoint_profile).
    const r = await fetch(`${API}/api/llm/providers/OPENAI_NATIVE/credential`, {
      method: 'PUT',
      headers: { ...admin(), 'Content-Type': 'application/json' },
      body: JSON.stringify({ api_key: BYOK_KEY }),
    });
    expect(r.status).toBe(200);
    const body = await r.json();
    expect(body.credential_source).toBe('TENANT_BYOK');
    expect(body.key_hint).toBeTruthy();
    // La clave en claro NO está en la respuesta.
    expect(JSON.stringify(body)).not.toContain(BYOK_KEY);
  });

  test('4. ADMIN: GET provider → credential_source TENANT_BYOK', async () => {
    const r = await fetch(`${API}/api/llm/providers/OPENAI_NATIVE`, { headers: admin() });
    expect(r.status).toBe(200);
    const body = await r.json();
    expect(body.credential_source).toBe('TENANT_BYOK');
    expect(body.configured).toBe(true);
    expect(JSON.stringify(body)).not.toContain(BYOK_KEY);
  });

  test('5. SecretStore: clave en claro NO está en PG (solo secret_ref opaco + key_hint)', async () => {
    const rows = queryDb(
      `SELECT secret_ref, key_hint FROM llm_provider_config WHERE negocio_id = '${seed.negocio_id}' AND provider = 'OPENAI_NATIVE'`,
    );
    expect(rows).toBeTruthy();
    // secret_ref opaco (no la clave) + key_hint corto.
    expect(rows).not.toContain(BYOK_KEY);
    // secret_ref presente (referencia al secreto cifrado en memoria).
    const [secretRef] = rows.split('\t');
    expect(secretRef).toBeTruthy();
    expect(secretRef).not.toBe(BYOK_KEY);
  });

  test('6. ADMIN: test provider contra fake provider local (local-ollama) → OK', async () => {
    // Skip en CI: requiere fake-provider.mjs + /etc/hosts con ollama.internal.
    let reachable = false;
    try {
      const probe = await fetch('http://ollama.internal:11434/v1/models', { signal: AbortSignal.timeout(2000) });
      reachable = probe.ok || probe.status === 404;
    } catch { /* not reachable */ }
    test.skip(!reachable, 'fake-provider no disponible (CI o sin /etc/hosts)');

    // OPENAI_COMPATIBLE_GENERIC + profile local-ollama + BYOK (fake-ollama-key).
    const cred = await fetch(`${API}/api/llm/providers/OPENAI_COMPATIBLE_GENERIC/credential`, {
      method: 'PUT',
      headers: { ...admin(), 'Content-Type': 'application/json' },
      body: JSON.stringify({ api_key: 'fake-ollama-key' }),
    });
    expect(cred.status).toBe(200);
    const cfg = await fetch(`${API}/api/llm/providers/OPENAI_COMPATIBLE_GENERIC/config`, {
      method: 'PUT',
      headers: { ...admin(), 'Content-Type': 'application/json' },
      body: JSON.stringify({ endpoint_profile: 'local-ollama', model: 'fake-ollama-model' }),
    });
    expect(cfg.status).toBe(200);
    const r = await fetch(`${API}/api/llm/providers/OPENAI_COMPATIBLE_GENERIC/test`, {
      method: 'POST',
      headers: admin(),
    });
    expect(r.status).toBe(200);
    const body = await r.json();
    expect(body.status).toBe('OK');
    expect(body.credential_source).toBe('TENANT_BYOK');
    expect(body.capabilities).toHaveProperty('text');
  });

  test('7. ADMIN: DELETE credential → cae a UNAVAILABLE (sin plataforma configurada)', async () => {
    // OPENAI_NATIVE: tras eliminar BYOK sin LLM_PLATFORM_OPENAI_NATIVE_API_KEY → UNAVAILABLE.
    const r = await fetch(`${API}/api/llm/providers/OPENAI_NATIVE/credential`, {
      method: 'DELETE',
      headers: admin(),
    });
    expect(r.status).toBe(200);
    const body = await r.json();
    expect(body.credential_source).toBeNull();
    expect(body.key_hint).toBeNull();
  });

  test('8. INVERSIONISTA: GET /api/llm/providers → 403', async () => {
    const r = await fetch(`${API}/api/llm/providers`, { headers: inv() });
    expect(r.status).toBe(403);
  });

  test('9. COBRADOR: GET /api/llm/providers → 403 (JWT real del flujo de dispositivo)', async () => {
    const r = await fetch(`${API}/api/llm/providers`, { headers: { Authorization: `Bearer ${jwtCobrador}` } });
    expect(r.status).toBe(403);
  });

  test('10. RBAC: /api/auth/me ADMIN tiene llm:ver + llm:gestionar', async () => {
    const r = await fetch(`${API}/api/auth/me`, { headers: admin() });
    expect(r.status).toBe(200);
    const body = await r.json();
    expect(body.capabilities).toContain('llm:ver');
    expect(body.capabilities).toContain('llm:gestionar');
  });

  test('11. BFF: /configuracion/ia renderiza para ADMIN (Browser → BFF → FastAPI)', async ({ browser }) => {
    const ctx = await browser.newContext();
    await ctx.addCookies([{ name: 'daily_admin_token', value: seed.tokens.administrador, url: BFF }]);
    const page = await ctx.newPage();
    await page.goto('/configuracion/ia');
    await expect(page.getByRole('heading', { name: /Configuración IA/ })).toBeVisible();
    await expect(page.getByText('OPENAI_NATIVE', { exact: true })).toBeVisible();
    await expect(page.getByText('ANTHROPIC_NATIVE', { exact: true })).toBeVisible();
    await ctx.close();
  });
});
