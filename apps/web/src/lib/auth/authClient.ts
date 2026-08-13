// Client del flujo de autenticacion Web (browser) — replica Dart de
// apps/mobile/lib/auth/device_auth_client.dart sobre el BFF Next.js.
//
// Flujo (contrato real, sin segundo modelo de auth, sin PIN):
//   1. POST /api/auth/web/activar      -> BFF: /api/activaciones/desafio
//   2. POST /api/auth/web/canjear      -> BFF: /api/activaciones/canjear.
//      La credencial_bootstrap NUNCA sale del server: el BFF la usa en memoria
//      para su primer /api/auth/device/desafio y devuelve el challenge de
//      sesion ya resuelto.
//   3. POST /api/auth/session          -> BFF: /api/auth/device/canjear
//      -> cookie daily_admin_token httpOnly.
//
// La privada NO-extractable vive en IndexedDB (lib/auth/identity.ts); la firma
// se ejecuta donde realmente existe la private key: el navegador. El BFF solo
// ve la SPKI publica y la firma; jamas la privada ni el bootstrap.

import {
  buildPayloadActivacion,
  buildPayloadAuth,
} from './jcs';
import {
  getOrCreateIdentity,
  signPayload,
} from './identity';

export interface DesafioActivacionResponse {
  intento_id: string;
  nonce: string;
  expira_el: string;
  environment: string;
}

export interface CanjeActivacionBFFResponse {
  dispositivo_id: string;
  negocio_id: string;
  usuario_id: string;
  cobrador_id: string;
  negocio_nombre?: string;
  cobrador_nombre?: string;
  expira_el: string;
  challenge_id: string;
  nonce: string;
  challenge_expira_el: string;
  environment: string;
}

export class AuthError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = 'AuthError';
    this.status = status;
  }
}

async function parseError(res: Response): Promise<never> {
  const body = await res.json().catch(() => ({}));
  const detail = (body as { detail?: string })?.detail ?? `Error HTTP ${res.status}`;
  throw new AuthError(detail, res.status);
}

/**
 * Activa el dispositivo con un codigo de activacion y obtiene la primera
 * sesion productiva. La privada se genera/recupera en IndexedDB; el BFF
 * mantiene el bootstrap en memoria entre /canjear y el primer desafio.
 */
export async function activateWithCode(code: string): Promise<CanjeActivacionBFFResponse> {
  const { spkiBase64, publicKeyHash } = await getOrCreateIdentity();

  const desafioRes = await fetch('/api/auth/web/activar', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ token: code, clave_publica: spkiBase64 }),
  });
  if (!desafioRes.ok) await parseError(desafioRes);
  const desafio = (await desafioRes.json()) as DesafioActivacionResponse;

  const payloadActivacion = buildPayloadActivacion({
    protocolVersion: 'daily-v1',
    environment: desafio.environment,
    attemptId: desafio.intento_id,
    nonce: desafio.nonce,
    publicKeyHash,
    expiresAt: desafio.expira_el,
  });
  const firmaActivacion = await signPayload(payloadActivacion);

  const canjeRes = await fetch('/api/auth/web/canjear', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      intento_id: desafio.intento_id,
      firma: firmaActivacion,
    }),
  });
  if (!canjeRes.ok) await parseError(canjeRes);
  return (await canjeRes.json()) as CanjeActivacionBFFResponse;
}

/**
 * Canjea la sesion a partir de un desafio de sesion ya resuelto (bootstrap o
 * renovacion): firma el payload daily-auth-v1 y guarda la cookie httpOnly.
 */
export async function canjearSesion(opts: {
  challengeId: string;
  nonce: string;
  environment: string;
  expiresAt: string;
  deviceId: string;
  publicKeyHash: string;
}): Promise<boolean> {
  const { challengeId, nonce, environment, expiresAt, deviceId, publicKeyHash } = opts;
  const payloadAuth = buildPayloadAuth({
    purpose: 'issue_access_token',
    environment,
    challengeId,
    deviceId,
    nonce,
    publicKeyHash,
    expiresAt,
  });
  const firma = await signPayload(payloadAuth);

  const sessionRes = await fetch('/api/auth/session', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ challenge_id: challengeId, firma }),
  });
  if (!sessionRes.ok) await parseError(sessionRes);
  return true;
}

/**
 * Login completo en un solo flujo: activacion con codigo + primera sesion.
 * Equivale a activar() + canjearSesion() del mobile.
 */
export async function loginWithCode(code: string): Promise<boolean> {
  const canje = await activateWithCode(code);
  const { publicKeyHash } = await getOrCreateIdentity();
  return canjearSesion({
    challengeId: canje.challenge_id,
    nonce: canje.nonce,
    environment: canje.environment,
    expiresAt: canje.challenge_expira_el,
    deviceId: canje.dispositivo_id,
    publicKeyHash,
  });
}

/**
 * Renueva la sesion vigente usando la cookie httpOnly como Bearer (igual que
 * renovarSesion() del mobile). Devuelve false sin credencial de sesion (401).
 */
export async function renewSession(): Promise<boolean> {
  const { publicKeyHash } = await getOrCreateIdentity();

  const desafioRes = await fetch('/api/auth/web/desafio', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: '{}',
  });
  if (!desafioRes.ok) {
    if (desafioRes.status === 401) return false;
    await parseError(desafioRes);
  }
  const desafio = (await desafioRes.json()) as {
    challenge_id: string;
    nonce: string;
    expira_el: string;
    environment: string;
    device_id: string;
  };
  if (!desafio.device_id) return false;

  return canjearSesion({
    challengeId: desafio.challenge_id,
    nonce: desafio.nonce,
    environment: desafio.environment,
    expiresAt: desafio.expira_el,
    deviceId: desafio.device_id,
    publicKeyHash,
  });
}

export async function logout(): Promise<void> {
  await fetch('/api/auth/logout', { method: 'POST' });
}