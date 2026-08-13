// JCS (RFC 8785) canonicalization — perfiles daily-v1 y daily-auth-v1.
//
// Replica byte a byte el motor del backend (apps/api/src/services/jcs.py y
// auth_jcs.py) y del mobile (apps/mobile/lib/auth/jcs.dart):
//   - daily-v1      : canje de activacion (payload firmado de 6 campos)
//   - daily-auth-v1 : desafio/canje del token productivo (payload de 8 campos)
//   - Canonizacion segun RFC 8785: claves ordenadas por code points (unidades
//     UTF-16), strings segun json.dumps(ensure_ascii=False), sin floats.
//
// El vector de prueba (e2e/jcs.spec.ts y src/lib/auth/jcs.test.ts) compara la
// salida byte a byte contra los vectores del contrato (apps/mobile/test/auth/
// jcs_vector_test.dart): este modulo debe producir exactamente esos bytes.

const PROTOCOL_VERSION_ACTIVACION = 'daily-v1';
const PROTOCOL_VERSION_AUTH = 'daily-auth-v1';
const PURPOSE_ISSUE_ACCESS_TOKEN = 'issue_access_token';

const VALID_ENVIRONMENTS = ['development', 'staging', 'production'];

const RE_UUID_LOWER =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const RE_NONCE_BASE64URL = /^[A-Za-z0-9_-]{43}$/;
const RE_HEX_64 = /^[0-9a-f]{64}$/;
const RE_RFC3339_SECONDS = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/;

export class JcsValidationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'JcsValidationError';
  }
}

function validateUuidLowercase(value: string, field: string): void {
  if (!RE_UUID_LOWER.test(value)) {
    throw new JcsValidationError(`${field} debe ser un UUID lowercase (8-4-4-4-12)`);
  }
}

function validateNonce(value: string): void {
  if (!RE_NONCE_BASE64URL.test(value)) {
    throw new JcsValidationError(
      'nonce debe ser base64url sin padding de 43 caracteres (32 bytes)',
    );
  }
}

function validatePublicKeyHash(value: string): void {
  if (!RE_HEX_64.test(value)) {
    throw new JcsValidationError(
      'public_key_hash debe ser hex lowercase de 64 caracteres (SHA-256)',
    );
  }
}

function validateRfc3339Seconds(value: string): void {
  if (!RE_RFC3339_SECONDS.test(value)) {
    throw new JcsValidationError(
      'expires_at debe ser RFC 3339 en segundos (YYYY-MM-DDTHH:MM:SSZ)',
    );
  }
}

/** JSON string literal per RFC 8785 (UTF-8 literal, sin ensure_ascii). */
function stringify(value: string): string {
  let out = '"';
  for (const ch of value) {
    const code = ch.codePointAt(0) as number;
    switch (code) {
      case 0x22:
        out += '\\"';
        break;
      case 0x5c:
        out += '\\\\';
        break;
      case 0x08:
        out += '\\b';
        break;
      case 0x09:
        out += '\\t';
        break;
      case 0x0a:
        out += '\\n';
        break;
      case 0x0c:
        out += '\\f';
        break;
      case 0x0d:
        out += '\\r';
        break;
      default:
        if (code <= 0x1f) {
          out += `\\u00${code.toString(16).padStart(2, '0')}`;
        } else {
          out += ch;
        }
    }
  }
  return out + '"';
}

/** Ordena claves por code points (unidades de codigo UTF-16). */
function compareUtf16CodeUnits(a: string, b: string): number {
  for (let i = 0; i < Math.min(a.length, b.length); i++) {
    const ca = a.charCodeAt(i);
    const cb = b.charCodeAt(i);
    if (ca !== cb) return ca < cb ? -1 : 1;
  }
  return a.length - b.length;
}

function canonicalizeToString(value: unknown): string {
  if (value === null) return 'null';
  const t = typeof value;
  if (t === 'string') return stringify(value as string);
  if (t === 'boolean') return value ? 'true' : 'false';
  if (t === 'number') {
    if (!Number.isInteger(value)) {
      throw new JcsValidationError(
        'Tipo no canonicalizable por el perfil del contrato: number',
      );
    }
    const n = value as number;
    return Object.is(n, -0) ? '0' : String(n);
  }
  if (t === 'object') {
    const obj = value as Record<string, unknown>;
    const keys = Object.keys(obj).sort(compareUtf16CodeUnits);
    if (keys.length === 0) return '{}';
    const parts: string[] = [];
    for (const key of keys) {
      parts.push(`${stringify(key)}:${canonicalizeToString(obj[key])}`);
    }
    return `{${parts.join(',')}}`;
  }
  throw new JcsValidationError(
    `Tipo no canonicalizable por el perfil del contrato: ${t}`,
  );
}

/** Canonicaliza un objeto al subconjunto permitido por el contrato. */
export function jcsCanonicalize(obj: Record<string, unknown>): Uint8Array {
  return new TextEncoder().encode(canonicalizeToString(obj));
}

/** Perfil de activacion (daily-v1) — canje de codigo de activacion. */
export function buildPayloadActivacion(opts: {
  protocolVersion: string;
  environment: string;
  attemptId: string;
  nonce: string;
  publicKeyHash: string;
  expiresAt: string;
}): Uint8Array {
  const {
    protocolVersion,
    environment,
    attemptId,
    nonce,
    publicKeyHash,
    expiresAt,
  } = opts;
  if (protocolVersion !== PROTOCOL_VERSION_ACTIVACION) {
    throw new JcsValidationError("protocol_version debe ser 'daily-v1'");
  }
  if (!VALID_ENVIRONMENTS.includes(environment)) {
    throw new JcsValidationError(`environment invalido: ${environment}`);
  }
  validateUuidLowercase(attemptId, 'attempt_id');
  validateNonce(nonce);
  validatePublicKeyHash(publicKeyHash);
  validateRfc3339Seconds(expiresAt);

  return jcsCanonicalize({
    protocol_version: protocolVersion,
    environment,
    attempt_id: attemptId,
    nonce,
    public_key_hash: publicKeyHash,
    expires_at: expiresAt,
  });
}

/** Perfil de auth (daily-auth-v1) — desafio/canje del token productivo. */
export function buildPayloadAuth(opts: {
  purpose: string;
  environment: string;
  challengeId: string;
  deviceId: string;
  nonce: string;
  publicKeyHash: string;
  expiresAt: string;
}): Uint8Array {
  const {
    purpose,
    environment,
    challengeId,
    deviceId,
    nonce,
    publicKeyHash,
    expiresAt,
  } = opts;
  if (purpose !== PURPOSE_ISSUE_ACCESS_TOKEN) {
    throw new JcsValidationError('purpose invalido: ' + purpose);
  }
  if (!VALID_ENVIRONMENTS.includes(environment)) {
    throw new JcsValidationError(`environment invalido: ${environment}`);
  }
  validateUuidLowercase(challengeId, 'challenge_id');
  validateUuidLowercase(deviceId, 'device_id');
  validateNonce(nonce);
  validatePublicKeyHash(publicKeyHash);
  validateRfc3339Seconds(expiresAt);

  return jcsCanonicalize({
    protocol_version: PROTOCOL_VERSION_AUTH,
    purpose,
    environment,
    challenge_id: challengeId,
    device_id: deviceId,
    nonce,
    public_key_hash: publicKeyHash,
    expires_at: expiresAt,
  });
}

/** Codifica bytes a base64url sin padding. */
export function base64UrlNoPad(bytes: Uint8Array): string {
  let bin = '';
  for (const b of bytes) bin += String.fromCharCode(b);
  return btoa(bin).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

/** Decodifica base64url sin padding a bytes. */
export function base64UrlDecode(value: string): Uint8Array {
  let b64 = value.replace(/-/g, '+').replace(/_/g, '/');
  while (b64.length % 4 !== 0) b64 += '=';
  const bin = atob(b64);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}