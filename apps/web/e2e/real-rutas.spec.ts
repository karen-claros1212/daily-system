import { test, expect } from '@playwright/test';

import { buildPayloadActivacion, buildPayloadAuth, base64UrlNoPad } from '../src/lib/auth/jcs';
import { rawToDerSignature, sha256Hex } from '../src/lib/auth/identity';
import { seedActivacion, runSql, type SeedOutput } from './helpers/real-seed';

/**
 * W4 — Rutas y Cobradores contra FastAPI real (:8001) + Postgres real + BFF Next.js (:3000).
 *
 * Certifica la reasignación S4 (R1→R2) a través de la integración Web (BFF),
 * no del service directamente. Verifica:
 *   1. Seed tenant + ADMIN + COBRADOR + R1.
 *   2. JWT REAL del COBRADOR vía flujo de dispositivo (activación → canje → desafío → canje sesión).
 *   3. Antes: /api/auth/me → 200, rol COBRADOR, route_id = R1.
 *   4. ADMIN ejecuta reasignación R1→R2 vía BFF (Next.js :3000).
 *   5. Backend/PG: R1 inactiva, R2 activa, mismo cobrador, version bump, AuditLog RUTA_REASIGNADA.
 *   6. JWT ANTERIOR del COBRADOR → 401 (version_asignacion stale).
 */

const API = process.env.REAL_API_BASE ?? 'http://127.0.0.1:8001';
const BFF = process.env.BFF_BASE ?? 'http://localhost:3000';

let seed: SeedOutput;
let jwtCobrador: string;
let rutaId: string;
let bootstrapCred: string;
let deviceId: string;
let cobradorKeyPair: CryptoKeyPair;
let cobradorPublicKeyHash: string;

test.describe.serial('W4 real: Rutas y Reasignación S4 (FastAPI :8001 + BFF :3000)', () => {
  test.beforeAll(async ({ browser }) => {
    seed = seedActivacion();
    rutaId = seed.ruta_id;

    // JWT real de COBRADOR vía flujo de dispositivo.
    const keyPair = await crypto.subtle.generateKey(
      { name: 'ECDSA', namedCurve: 'P-256' },
      true,
      ['sign', 'verify'],
    );
    const spki = new Uint8Array(await crypto.subtle.exportKey('spki', keyPair.publicKey));
    const spkiB64 = Buffer.from(spki).toString('base64');
    const publicKeyHash = await sha256Hex(spki);
    cobradorKeyPair = keyPair;
    cobradorPublicKeyHash = publicKeyHash;
    const signJcs = async (payload: Uint8Array) =>
      base64UrlNoPad(
        rawToDerSignature(
          new Uint8Array(await crypto.subtle.sign({ name: 'ECDSA', hash: 'SHA-256' }, keyPair.privateKey, payload)),
        ),
      );

    // 1) activación daily-v1
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
    bootstrapCred = canje.credencial_bootstrap;
    deviceId = canje.dispositivo_id;

    // 2) desafío sesión daily-auth-v1
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
    jwtCobrador = ((await cs.json()) as { token: string }).token;
  });

  test('COBRADOR (JWT real): /api/auth/me → 200, rol COBRADOR, route_id = R1', async () => {
    const r = await fetch(`${API}/api/auth/me`, {
      headers: { Authorization: `Bearer ${jwtCobrador}` },
    });
    expect(r.status).toBe(200);
    const body = (await r.json()) as {
      rol: string;
      route_id: string | null;
      version_asignacion: number | null;
      capabilities: string[];
    };
    expect(body.rol).toBe('COBRADOR');
    expect(body.route_id).toBe(rutaId);
    expect(body.version_asignacion).toBe(1);
    expect(body.capabilities).toContain('ruta:ver');
  });

  test('ADMIN reasigna R1→R2 vía BFF (Next.js :3000)', async ({ browser }) => {
    // Crear un contexto con la cookie del ADMIN para llamar al BFF.
    const ctx = await browser.newContext();
    await ctx.addCookies([
      { name: 'daily_admin_token', value: seed.tokens.administrador, url: BFF },
    ]);
    const page = await ctx.newPage();

    const nombreUnico = `Ruta Reasignada ${Date.now()}`;
    const res = await page.request.patch(`${BFF}/api/rutas/${rutaId}/reasignar`, {
      data: { nombre: nombreUnico },
    });
    expect(res.status(), 'BFF reasignar → 200').toBe(200);
    const body = (await res.json()) as {
      ruta_anterior_id: string;
      ruta_anterior_nombre: string;
      ruta_nueva_id: string;
      ruta_nueva_nombre: string;
      cobrador_id: string;
      version_asignacion: number;
    };
    expect(body.ruta_anterior_id).toBe(rutaId);
    expect(body.ruta_nueva_id).not.toBe(rutaId);
    expect(body.ruta_nueva_nombre).toBe(nombreUnico);
    expect(body.version_asignacion).toBe(2);

    // Guardar la nueva ruta para verificaciones posteriores.
    (globalThis as Record<string, unknown>).__rutaNuevaId = body.ruta_nueva_id;

    await ctx.close();
  });

  test('Backend/PG: R1 inactiva, R2 activa, mismo cobrador, una sola activa, version bump', async () => {
    const rutaNuevaId = (globalThis as Record<string, unknown>).__rutaNuevaId as string;

    // R1 (la ruta original del seed) ahora inactiva.
    const r1 = await fetch(`${API}/api/rutas/${rutaId}`, {
      headers: { Authorization: `Bearer ${seed.tokens.administrador}` },
    });
    expect(r1.status).toBe(200);
    const r1body = (await r1.json()) as { activa: number; nombre: string };
    // Si el seed es idempotente y ya hubo una reasignación previa, rutaId
    // podría ser R2 (la activa). En ese caso R1 ya es inactiva por el
    // reasignar anterior. Verificamos que la ruta NO sea la nueva.
    if (rutaId === rutaNuevaId) {
      // El seed devolvió R2 (idempotencia post-reasignación previa).
      // La ruta original (R1) debe existir y ser inactiva.
      const lista = await fetch(`${API}/api/rutas?limit=50`, {
        headers: { Authorization: `Bearer ${seed.tokens.administrador}` },
      });
      const listBody = (await lista.json()) as { items: Array<{ ruta_id: string; activa: number; cobrador_id: string; nombre: string }> };
      const r1Original = listBody.items.find((r) => r.cobrador_id === seed.cobrador_id && r.ruta_id !== rutaNuevaId);
      expect(r1Original, 'R1 original debe existir').toBeTruthy();
      expect(r1Original!.activa).toBe(0);
    } else {
      // rutaId es R1 (primera ejecución): debe ser inactiva tras reasignar.
      expect(r1body.activa).toBe(0);
    }

    // R2 activa, mismo cobrador.
    const r2 = await fetch(`${API}/api/rutas/${rutaNuevaId}`, {
      headers: { Authorization: `Bearer ${seed.tokens.administrador}` },
    });
    expect(r2.status).toBe(200);
    const r2body = (await r2.json()) as { activa: number; cobrador_id: string; version: number };
    expect(r2body.activa).toBe(1);
    expect(r2body.version).toBeGreaterThanOrEqual(1);

    // Una sola ruta activa para el cobrador (verificar vía listado ADMIN).
    const lista = await fetch(`${API}/api/rutas?activa=1&limit=50`, {
      headers: { Authorization: `Bearer ${seed.tokens.administrador}` },
    });
    expect(lista.status).toBe(200);
    const listBody = (await lista.json()) as { items: Array<{ ruta_id: string; activa: number; cobrador_id: string }> };
    const activasCobrador = listBody.items.filter(
      (r) => r.activa === 1 && r.cobrador_id === seed.cobrador_id,
    );
    expect(activasCobrador.length).toBe(1);
    expect(activasCobrador[0].ruta_id).toBe(rutaNuevaId);
  });

  test('AuditLog: RUTA_REASIGNADA existe con metadata correcta', async () => {
    const audit = await fetch(`${API}/api/audit?entity_type=RUTA&limit=50`, {
      headers: { Authorization: `Bearer ${seed.tokens.administrador}` },
    });
    expect(audit.status).toBe(200);
    const logs = (await audit.json()) as Array<{
      action: string;
      entity_type: string;
      metadata: Record<string, unknown> | null;
    }>;
    const reasign = logs.find((l) => l.action === 'RUTA_REASIGNADA');
    expect(reasign, 'AuditLog RUTA_REASIGNADA debe existir').toBeTruthy();
    expect(reasign!.metadata, 'metadata debe existir').toBeTruthy();
    expect(reasign!.metadata!['version_asignacion']).toBeGreaterThanOrEqual(2);
    expect(reasign!.metadata!['ruta_anterior_id']).toBe(rutaId);
  });

  test('JWT ANTERIOR del COBRADOR → 401 (version_asignacion stale)', async () => {
    // El JWT original (version_asignacion=1) ahora es stale porque el bump
    // lo llevó a 2. El backend valida: dispositivo.version_asignacion !=
    // claims.version_asignacion → 401.
    const r = await fetch(`${API}/api/auth/me`, {
      headers: { Authorization: `Bearer ${jwtCobrador}` },
    });
    expect(r.status, 'JWT stale debe ser 401 (no 403, no 200)').toBe(401);
  });

  test('COBRADOR con JWT NUEVO (post-reasignación) → 200, route_id = R2', async () => {
    // El cobrador re-autentica con su dispositivo existente (bootstrap del
    // canje original). Usa la MISMA key pair que registró el dispositivo.
    const signJcs = async (payload: Uint8Array) =>
      base64UrlNoPad(
        rawToDerSignature(
          new Uint8Array(await crypto.subtle.sign({ name: 'ECDSA', hash: 'SHA-256' }, cobradorKeyPair.privateKey, payload)),
        ),
      );

    // Desafío de sesión con el bootstrap credential guardado.
    const ds = await fetch(`${API}/api/auth/device/desafio`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${bootstrapCred}` },
    });
    expect(ds.status, 're-autenticación desafío sesión').toBe(200);
    const desafioSesion = (await ds.json()) as { challenge_id: string; nonce: string; expira_el: string; environment: string };
    const payloadSesion = buildPayloadAuth({
      purpose: 'issue_access_token',
      environment: desafioSesion.environment,
      challengeId: desafioSesion.challenge_id,
      deviceId,
      nonce: desafioSesion.nonce,
      publicKeyHash: cobradorPublicKeyHash,
      expiresAt: desafioSesion.expira_el,
    });
    const cs = await fetch(`${API}/api/auth/device/canjear`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ challenge_id: desafioSesion.challenge_id, firma: await signJcs(payloadSesion) }),
    });
    expect(cs.status, 're-autenticación canje sesión').toBe(200);
    const nuevoJwt = ((await cs.json()) as { token: string }).token;

    // Verificar que el nuevo JWT funciona y apunta a R2.
    const r = await fetch(`${API}/api/auth/me`, {
      headers: { Authorization: `Bearer ${nuevoJwt}` },
    });
    expect(r.status, 'JWT nuevo → 200').toBe(200);
    const body = (await r.json()) as {
      rol: string;
      route_id: string | null;
      version_asignacion: number | null;
    };
    expect(body.rol).toBe('COBRADOR');
    expect(body.version_asignacion).toBe(2);

    const rutaNuevaId = (globalThis as Record<string, unknown>).__rutaNuevaId as string;
    expect(body.route_id, 'route_id debe ser R2 (nueva ruta)').toBe(rutaNuevaId);
  });
});
