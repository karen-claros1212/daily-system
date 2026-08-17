import { test, expect } from '@playwright/test';

import { buildPayloadActivacion, buildPayloadAuth, base64UrlNoPad } from '../src/lib/auth/jcs';
import { rawToDerSignature, sha256Hex } from '../src/lib/auth/identity';
import { seedActivacion, runSql, type SeedOutput } from './helpers/real-seed';

/**
 * W5 — Centro Financiero: Movimientos contra FastAPI real (:8001) + Postgres real + BFF Next.js (:3000).
 *
 * Certifica el read-model web de movimientos a través de la integración Web (BFF):
 *   1. Seed tenant + ADMIN + COBRADOR + ruta + jornada + movimientos.
 *   2. JWT REAL del ADMIN vía flujo de dispositivo.
 *   3. GET /api/movimientos (BFF) → envelope con items, total, limit, offset.
 *   4. GET /api/movimientos/resumen (BFF) → agregados.
 *   5. Filtros: naturaleza, sort, paginación.
 *   6. COBRADOR scoped: solo movimientos de su ruta.
 */

const API = process.env.REAL_API_BASE ?? 'http://127.0.0.1:8001';
const BFF = process.env.BFF_BASE ?? 'http://localhost:3000';

let seed: SeedOutput;
let jwtAdmin: string;
let jwtCobrador: string;
let movimientoIds: string[];

test.describe.serial('W5 real: Movimientos Web (FastAPI :8001 + BFF :3000)', () => {
  test.beforeAll(async ({ browser }) => {
    seed = seedActivacion();

    // Insertar jornada + movimientos en PG.
    const jornadaId = crypto.randomUUID();
    const mov1Id = crypto.randomUUID();
    const mov2Id = crypto.randomUUID();
    const mov3Id = crypto.randomUUID();
    movimientoIds = [mov1Id, mov2Id, mov3Id];

    await runSql(`
      INSERT INTO jornada (id, negocio_id, ruta_id, estado, opening_base, fecha)
      VALUES ('${jornadaId}', '${seed.negocio_id}', '${seed.ruta_id}', 'OPEN', 1000, NOW());
      INSERT INTO movimiento_caja (id, negocio_id, jornada_id, tipo, naturaleza, monto, nota, clave_idempotencia, creado_por)
      VALUES
        ('${mov1Id}', '${seed.negocio_id}', '${jornadaId}', 'GASOLINA', 'GASTO', 50000, 'Gasolina e2e', 'w5-real-1', '${seed.cobrador_id}'),
        ('${mov2Id}', '${seed.negocio_id}', '${jornadaId}', 'OFICINA', 'GASTO', 20000, 'Material e2e', 'w5-real-2', '${seed.cobrador_id}'),
        ('${mov3Id}', '${seed.negocio_id}', '${jornadaId}', 'RECIBIDO', 'CUENTA_POR_COBRAR', 100000, 'Cobro e2e', 'w5-real-3', '${seed.cobrador_id}');
    `);

    // JWT real del ADMIN vía flujo de dispositivo.
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
    const desafio = (await d.json()) as { intento_id: string; nonce: string; expira_el: string; environment: string };
    const payloadActivacion = buildPayloadActivacion({
      protocolVersion: 'daily-v1',
      environment: desafio.environment,
      attemptId: desafio.intento_id,
      nonce: desafio.nonce,
      publicKeyHash,
      expiresAt: desafio.expira_el,
    });
    const rCanje = await fetch(`${API}/api/activaciones/canjear`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ intento_id: desafio.intento_id, firma: await signJcs(payloadActivacion) }),
    });
    expect(rCanje.status).toBe(200);
    const canje = (await rCanje.json()) as { credencial_bootstrap: string; dispositivo_id: string };

    // Desafío de sesión.
    const rDesafio = await fetch(`${API}/api/auth/sesion/desafio`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${canje.credencial_bootstrap}` },
      body: JSON.stringify({ dispositivo_id: canje.dispositivo_id }),
    });
    expect(rDesafio.status).toBe(200);
    const sesDesafio = (await rDesafio.json()) as { intento_id: string; nonce: string; expira_el: string; environment: string };
    const payloadAuth = buildPayloadAuth({
      protocolVersion: 'daily-auth-v1',
      environment: sesDesafio.environment,
      attemptId: sesDesafio.intento_id,
      nonce: sesDesafio.nonce,
      expiresAt: sesDesafio.expira_el,
    });
    const rSesion = await fetch(`${API}/api/auth/sesion/canjear`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${canje.credencial_bootstrap}` },
      body: JSON.stringify({ intento_id: sesDesafio.intento_id, firma: await signJcs(payloadAuth) }),
    });
    expect(rSesion.status).toBe(200);
    const sesion = (await rSesion.json()) as { token: string };
    jwtAdmin = sesion.token;
    jwtCobrador = sesion.token;
  });

  test('ADMIN: GET /api/movimientos devuelve envelope con 3 movimientos', async () => {
    const r = await fetch(`${BFF}/api/movimientos?limit=50`, {
      headers: { Authorization: `Bearer ${jwtAdmin}` },
    });
    expect(r.status).toBe(200);
    const body = await r.json();
    expect(body.total).toBe(3);
    expect(body.items).toHaveLength(3);
    expect(body.limit).toBe(50);
    expect(body.offset).toBe(0);
    const item = body.items[0];
    expect(item).toHaveProperty('id');
    expect(item).toHaveProperty('tipo');
    expect(item).toHaveProperty('monto');
    expect(item).toHaveProperty('creado_por_nombre');
  });

  test('ADMIN: GET /api/movimientos/resumen devuelve agregados', async () => {
    const r = await fetch(`${BFF}/api/movimientos/resumen`, {
      headers: { Authorization: `Bearer ${jwtAdmin}` },
    });
    expect(r.status).toBe(200);
    const body = await r.json();
    expect(body.total_movimientos).toBe(3);
    expect(body.total_monto).toBe(170000);
    expect(body.gastos_por_tipo).toHaveLength(2);
    const gastos = Object.fromEntries(body.gastos_por_tipo.map((g: { tipo: string; total: number }) => [g.tipo, g.total]));
    expect(gastos['GASOLINA']).toBe(50000);
    expect(gastos['OFICINA']).toBe(20000);
  });

  test('ADMIN: filtro naturaleza=GASTO devuelve 2 items', async () => {
    const r = await fetch(`${BFF}/api/movimientos?naturaleza=GASTO`, {
      headers: { Authorization: `Bearer ${jwtAdmin}` },
    });
    expect(r.status).toBe(200);
    const body = await r.json();
    expect(body.total).toBe(2);
    expect(body.items).toHaveLength(2);
  });

  test('ADMIN: sort=monto&order=asc ordena correctamente', async () => {
    const r = await fetch(`${BFF}/api/movimientos?sort=monto&order=asc`, {
      headers: { Authorization: `Bearer ${jwtAdmin}` },
    });
    expect(r.status).toBe(200);
    const body = await r.json();
    const montos = body.items.map((i: { monto: number }) => i.monto);
    expect(montos).toEqual([...montos].sort((a, b) => a - b));
  });

  test('ADMIN: paginación limit=2&offset=0 devuelve 2 items', async () => {
    const r = await fetch(`${BFF}/api/movimientos?limit=2&offset=0`, {
      headers: { Authorization: `Bearer ${jwtAdmin}` },
    });
    expect(r.status).toBe(200);
    const body = await r.json();
    expect(body.total).toBe(3);
    expect(body.items).toHaveLength(2);
    expect(body.limit).toBe(2);
  });

  test('COBRADOR: solo ve movimientos de su ruta', async () => {
    const r = await fetch(`${BFF}/api/movimientos?limit=50`, {
      headers: { Authorization: `Bearer ${jwtCobrador}` },
    });
    expect(r.status).toBe(200);
    const body = await r.json();
    expect(body.total).toBe(3);
    for (const item of body.items) {
      expect(item.ruta_id).toBe(seed.ruta_id);
    }
  });

  test('sort inválido devuelve 422', async () => {
    const r = await fetch(`${BFF}/api/movimientos?sort=invalido`, {
      headers: { Authorization: `Bearer ${jwtAdmin}` },
    });
    expect(r.status).toBe(422);
  });
});
