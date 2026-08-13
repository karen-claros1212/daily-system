// Identidad criptografica del navegador — replica del motor del dispositivo.
//
// Equivalente Web del canal nativo Android Keystore (apps/mobile/android/.../
// DeviceIdentityService.kt) usando la Web Crypto API:
//   - Par EC P-256 (secp256r1) con la privada NO extractable.
//   - La clave se persiste en IndexedDB (la privada se guarda como CryptoKey
//     no extraible; structuredClone la sobrevive como ImpossibleKey).
//   - La publica se exporta como SPKI (X.509, DER) en base64, byte por byte
//     como exige el contrato.
//   - Firma SHA256withECDSA. WebCrypto genera la firma en formato raw
//     (IEEE P1363, r||s 64 bytes); el backend productivo verifica DER
//     (ASN.1) via `ec.ECDSA(hashes.SHA256())`, asi que convertimos raw->DER.
//     La conversion raw->DER NO altera el material del par y es verificada
//     por los tests del contrato (e2e y unit).
//
// public_key_hash = sha256 hex lowercase del SPKI DER exacto.

import { base64UrlDecode, base64UrlNoPad } from './jcs';

const DB_NAME = 'daily-web-identity';
const STORE = 'keys';
const KEY = 'device-identity';

export interface WebIdentity {
  spkiBase64: string;
  publicKeyHash: string;
}

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, 1);
    req.onupgradeneeded = () => {
      if (!req.result.objectStoreNames.contains(STORE)) {
        req.result.createObjectStore(STORE);
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

async function idbGet(key: string): Promise<unknown> {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, 'readonly');
    const g = tx.objectStore(STORE).get(key);
    g.onsuccess = () => resolve(g.result);
    g.onerror = () => reject(g.error);
  });
}

async function idbPut(key: string, value: unknown): Promise<void> {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, 'readwrite');
    tx.objectStore(STORE).put(value, key);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

async function idbDelete(key: string): Promise<void> {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, 'readwrite');
    tx.objectStore(STORE).delete(key);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

export function isWebCryptoAvailable(): boolean {
  return typeof crypto !== 'undefined' && !!crypto.subtle;
}

/** SHA-256 hex lowercase de bytes (public_key_hash del contrato). */
export async function sha256Hex(bytes: Uint8Array): Promise<string> {
  const digest = await crypto.subtle.digest('SHA-256', BufferSourceOf(bytes));
  return Array.from(new Uint8Array(digest))
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('');
}

function BufferSourceOf(bytes: Uint8Array): ArrayBuffer {
  return bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength) as ArrayBuffer;
}

async function exportSpki(publicKey: CryptoKey): Promise<ArrayBuffer> {
  const spki = await crypto.subtle.exportKey('spki', publicKey);
  return spki;
}

function base64FromBytes(bytes: ArrayBuffer): string {
  const u8 = new Uint8Array(bytes);
  let bin = '';
  for (const b of u8) bin += String.fromCharCode(b);
  return btoa(bin);
}

function bytesFromBase64(b64: string): Uint8Array {
  const bin = atob(b64);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

function concatBytes(a: Uint8Array, b: Uint8Array): Uint8Array {
  const out = new Uint8Array(a.length + b.length);
  out.set(a, 0);
  out.set(b, a.length);
  return out;
}

function derInt(x: Uint8Array): Uint8Array {
  let v = x;
  while (v.length > 1 && v[0] === 0) v = v.subarray(1);
  if ((v[0] & 0x80) !== 0) v = concatBytes(new Uint8Array([0]), v);
  return concatBytes(new Uint8Array([0x02, v.length]), v);
}

/**
 * Convierte una firma ECDSA raw (IEEE P1363, r||s 64 bytes) a la
 * representacion ASN.1 DER (SEQUENCE { INTEGER r, INTEGER s }) que exige el
 * backend productivo (cryptography ec.ECDSA) y Android SHA256withECDSA.
 */
export function rawToDerSignature(raw: Uint8Array): Uint8Array {
  if (raw.length !== 64) {
    throw new Error(`firma raw debe ser 64 bytes (r||s), recibidos ${raw.length}`);
  }
  const r = derInt(raw.subarray(0, 32));
  const s = derInt(raw.subarray(32, 64));
  const body = concatBytes(r, s);
  return concatBytes(new Uint8Array([0x30, body.length]), body);
}

/** Genera (o recupera) el par EC P-256. Privada no extractable. */
export async function getOrCreateIdentity(): Promise<WebIdentity> {
  if (!isWebCryptoAvailable()) {
    throw new Error('Web Crypto API no disponible');
  }
  const existing = (await idbGet(KEY)) as CryptoKeyPair | undefined;
  if (existing) {
    const spki = await exportSpki(existing.publicKey);
    const spkiBase64 = base64FromBytes(spki);
    const publicKeyHash = await sha256Hex(new Uint8Array(spki));
    return { spkiBase64, publicKeyHash };
  }

  const pair = await crypto.subtle.generateKey(
    { name: 'ECDSA', namedCurve: 'P-256' },
    false,
    ['sign', 'verify'],
  );
  await idbPut(KEY, pair);
  const spki = await exportSpki(pair.publicKey);
  const spkiBase64 = base64FromBytes(spki);
  const publicKeyHash = await sha256Hex(new Uint8Array(spki));
  return { spkiBase64, publicKeyHash };
}

/** Firma los bytes exactos del payload (SHA256withECDSA; DER), base64url. */
export async function signPayload(payload: Uint8Array): Promise<string> {
  const pair = (await idbGet(KEY)) as CryptoKeyPair | undefined;
  if (!pair) {
    throw new Error('No hay identidad del dispositivo: ejecute getOrCreateIdentity()');
  }
  const raw = new Uint8Array(
    await crypto.subtle.sign({ name: 'ECDSA', hash: 'SHA-256' }, pair.privateKey, BufferSourceOf(payload)),
  );
  const der = rawToDerSignature(raw);
  return base64UrlNoPad(der);
}

export async function hasIdentity(): Promise<boolean> {
  const existing = (await idbGet(KEY)) as CryptoKeyPair | undefined;
  return !!existing;
}

export async function deleteIdentity(): Promise<void> {
  await idbDelete(KEY);
}

export { bytesFromBase64, base64UrlDecode, base64UrlNoPad }; // re-export helpers