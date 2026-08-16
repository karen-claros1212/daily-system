import { test, expect } from '@playwright/test';

import { buildPayloadActivacion, buildPayloadAuth, base64UrlNoPad } from '../src/lib/auth/jcs';
import { rawToDerSignature, sha256Hex } from '../src/lib/auth/identity';
import { seedActivacion, type SeedOutput } from './helpers/real-seed';

/**
 * W3 — Cartera y Créditos contra FastAPI real (:8001) + Postgres real.
 * SIN mock-api.mjs: cada request de lectura usa la autoridad financiera del
 * backend (hoja_viva_service.resumen_creditos), nunca cálculo en el browser.
 *
 * Roles (autoridad real):
 *  - ADMINISTRADOR / INVERSIONISTA: JWTs minted por el servidor (seed).
 *  - COBRADOR: JWT real del flujo de dispositivo (activación -> canje ->
 *    desafío daily-auth-v1 -> JWT), el único camino que emite ese rol.
 *
 * Flujo del spec (serial): seed -> cliente PROVISIONAL -> crédito nuevo
 * (test 1) -> el resto de tests leen/detallan ese crédito.
 */

const API = process.env.REAL_API_BASE ?? 'http://127.0.0.1:8001';

let seed: SeedOutput;
let jwtCobrador: string;
let clienteId: string;
let creditoId: string;

function auth(token: string): Record<string, string> {
  return { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' };
}

async function crearClienteAdmin(): Promise<string> {
  const res = await fetch(`${API}/api/clientes`, {
    method: 'POST',
    headers: auth(seed.tokens.administrador),
    body: JSON.stringify({
      primer_apellido: 'Web',
      nombres: `Credito E2E ${Date.now()}`,
      tipo_documento: 'CC',
      documento_normalizado: `1000${Date.now()}`,
      telefono_1: '3000000000',
      ciudad: 'Bogotá',
    }),
  });
  expect(res.status, 'admin crea cliente (clientes:gestionar)').toBe(201);
  const body = (await res.json()) as { id: string };
  return body.id;
}

test.describe.serial('W3 real: Cartera y Créditos (FastAPI :8001)', () => {
  test.beforeAll(async () => {
    seed = seedActivacion();
    clienteId = await crearClienteAdmin();

    // JWT real de COBRADOR vía flujo de dispositivo (como real-rbac).
    const keyPair = await crypto.subtle.generateKey(
      { name: 'ECDSA', namedCurve: 'P-256' },
      true,
      ['sign', 'verify'],
    );
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
    jwtCobrador = ((await cs.json()) as { token: string }).token;
  });

  test('ADMIN crea crédito: 201, total = cuota x n_cuotas y audit CREDITO_CREADO', async () => {
    const res = await fetch(`${API}/api/creditos`, {
      method: 'POST',
      headers: auth(seed.tokens.administrador),
      body: JSON.stringify({
        cliente_id: clienteId,
        ruta_id: seed.ruta_id,
        cuota: 20000,
        n_cuotas: 5,
        monto: 100000,
        fecha_inicio: '2026-08-16',
        periodicidad: 'DIARIO',
      }),
    });
    expect(res.status).toBe(201);
    const body = (await res.json()) as {
      id: string;
      total: number;
      estado: string;
      periodicidad: string;
      negocio_id: string;
    };
    creditoId = body.id;
    expect(body.total).toBe(20000 * 5);
    expect(body.estado).toBe('ACTIVO');
    expect(body.negocio_id).toBe(seed.negocio_id);

    // Auditoría append-only: el evento CREDITO_CREADO existe y es atribuible.
    const audit = await fetch(`${API}/api/audit?entity_type=CREDITO`, {
      headers: { Authorization: `Bearer ${seed.tokens.administrador}` },
    });
    expect(audit.status).toBe(200);
    const logs = (await audit.json()) as Array<{ action: string; entity_id: string }>;
    expect(logs.some((l) => l.action === 'CREDITO_CREADO' && l.entity_id === creditoId)).toBe(true);
  });

  test('COBRADOR (JWT real) no puede crear: POST /api/creditos -> 403', async () => {
    const res = await fetch(`${API}/api/creditos`, {
      method: 'POST',
      headers: auth(jwtCobrador),
      body: JSON.stringify({
        cliente_id: clienteId,
        ruta_id: seed.ruta_id,
        cuota: 1000,
        n_cuotas: 10,
        monto: 10000,
        fecha_inicio: '2026-08-16',
      }),
    });
    expect(res.status).toBe(403);
  });

  test('INVERSIONISTA no puede crear: POST /api/creditos -> 403', async () => {
    const res = await fetch(`${API}/api/creditos`, {
      method: 'POST',
      headers: auth(seed.tokens.inversionista),
      body: JSON.stringify({
        cliente_id: clienteId,
        ruta_id: seed.ruta_id,
        cuota: 1000,
        n_cuotas: 10,
        monto: 10000,
        fecha_inicio: '2026-08-16',
      }),
    });
    expect(res.status).toBe(403);
  });

  test('ADMIN con ruta inexistente -> 404 (aislamiento por negocio)', async () => {
    const res = await fetch(`${API}/api/creditos`, {
      method: 'POST',
      headers: auth(seed.tokens.administrador),
      body: JSON.stringify({
        cliente_id: clienteId,
        ruta_id: '00000000-0000-4000-8000-000000000000',
        cuota: 1000,
        n_cuotas: 10,
        monto: 10000,
        fecha_inicio: '2026-08-16',
      }),
    });
    expect(res.status).toBe(404);
  });

  test('ADMIN lista y resumen de cartera: envelope + agregados financieros del backend', async () => {
    const lista = await fetch(`${API}/api/creditos?limit=50`, {
      headers: { Authorization: `Bearer ${seed.tokens.administrador}` },
    });
    expect(lista.status).toBe(200);
    const body = (await lista.json()) as {
      items: Array<{ id: string; cliente_nombre: string; saldo: number }>;
      total: number;
      limit: number;
      offset: number;
    };
    expect(typeof body.total).toBe('number');
    expect(body.limit).toBe(50);
    expect(body.offset).toBe(0);
    const creado = body.items.find((i) => i.id === creditoId);
    expect(creado).toBeTruthy();
    expect(creado!.cliente_nombre).toContain('Web');
    expect(creado!.saldo).toBe(100000);

    const resumen = await fetch(`${API}/api/creditos/resumen`, {
      headers: { Authorization: `Bearer ${seed.tokens.administrador}` },
    });
    expect(resumen.status).toBe(200);
    const agg = (await resumen.json()) as {
      total_creditos: number;
      activos: number;
      saldo_total_cartera: number;
      en_mora: number;
    };
    expect(agg.total_creditos).toBeGreaterThanOrEqual(1);
    expect(agg.activos).toBeGreaterThanOrEqual(1);
    expect(agg.saldo_total_cartera).toBeGreaterThanOrEqual(100000);
    expect(typeof agg.en_mora).toBe('number');
  });

  test('ADMIN detalle de crédito: financiero + cliente + ruta', async () => {
    const res = await fetch(`${API}/api/creditos/${creditoId}`, {
      headers: { Authorization: `Bearer ${seed.tokens.administrador}` },
    });
    expect(res.status).toBe(200);
    const body = (await res.json()) as {
      cliente_nombre: string;
      ruta_nombre: string;
      saldo: number;
      mora: number;
      cuotas_pagadas: number;
      n_cuotas: number;
    };
    expect(body.cliente_nombre).toContain('Web');
    expect(body.ruta_nombre).toBeTruthy();
    expect(body.saldo).toBe(100000);
    expect(body.mora).toBe(0);
    expect(body.cuotas_pagadas).toBe(0);
    expect(body.n_cuotas).toBe(5);
  });

  test('INVERSIONISTA: PII minimizada en lista y resumen financiero visible', async () => {
    const lista = await fetch(`${API}/api/creditos`, {
      headers: { Authorization: `Bearer ${seed.tokens.inversionista}` },
    });
    expect(lista.status).toBe(200);
    const body = (await lista.json()) as {
      items: Array<{ id: string; cliente_nombre: string | null; cliente_id: string | null; saldo: number }>;
    };
    const creado = body.items.find((i) => i.id === creditoId);
    expect(creado).toBeTruthy();
    expect(creado!.cliente_nombre).toBeNull();
    expect(creado!.cliente_id).toBeNull();
    expect(creado!.saldo).toBe(100000); // financiero NO se oculta al inversionista

    const resumen = await fetch(`${API}/api/creditos/resumen`, {
      headers: { Authorization: `Bearer ${seed.tokens.inversionista}` },
    });
    expect(resumen.status).toBe(200);
  });

  test('COBRADOR: lista scoped a su ruta, ruta ajena 404 y crédito inexistente 404', async () => {
    const lista = await fetch(`${API}/api/creditos`, {
      headers: { Authorization: `Bearer ${jwtCobrador}` },
    });
    expect(lista.status).toBe(200);
    const body = (await lista.json()) as { items: Array<{ id: string; ruta_id: string }> };
    expect(body.items.length).toBeGreaterThanOrEqual(1);
    for (const item of body.items) expect(item.ruta_id).toBe(seed.ruta_id);

    // Ruta ajena -> 404 (sin revelar existencia), nunca 200.
    const ajena = await fetch(`${API}/api/creditos?ruta_id=${seed.ruta_id === '00000000-0000-4000-8000-000000000000' ? '11111111-1111-4111-8111-111111111111' : '00000000-0000-4000-8000-000000000000'}`, {
      headers: { Authorization: `Bearer ${jwtCobrador}` },
    });
    expect(ajena.status).toBe(404);

    // Crédito inexistente -> 404 (no 403): no se filtra por rol en el 404.
    const inexistente = await fetch(`${API}/api/creditos/00000000-0000-4000-8000-000000000000`, {
      headers: { Authorization: `Bearer ${jwtCobrador}` },
    });
    expect(inexistente.status).toBe(404);
  });
});
