# Seguridad — Daily System

**Documento:** Normativo
**Última actualización:** 2026-08-11
**Base verificada:** `c0a3a9c` (baseline código S0-S2)
**HEAD repositorio (documental):** `35adf24`
**Ver también:** [ARCHITECTURE.md](ARCHITECTURE.md), [OFFLINE-SYNC.md](OFFLINE-SYNC.md)

---

## Resumen de la pila de seguridad

| Capa | Mecanismo | Estado |
|---|---|---|
| Device identity | AndroidKeyStore EC P-256 (SHA256withECDSA), clave privada no exportable | ✅ Implementado |
| Serialization | JCS (RFC 8785), byte-exacto backend↔mobile | ✅ Implementado |
| Activation | Challenge-response single-use (daily-v1), MAX_INTENTOS_FALLIDOS=5 → EXPIRED | ✅ Implementado |
| Session | JWT ES256 con binding, fail-closed (rechaza none/HS256/RS256) | ✅ Implementado |
| Bootstrap | GET /api/mobile/bootstrap (Bearer JWT), ruta activa única | ✅ Implementado |
| Renewal | Challenge-response (daily-auth-v1) antes de expiración | ✅ Implementado |
| Scope | Server-derived (negocio + cobrador + dispositivo + ruta) | ✅ Implementado |
| Idempotency | clave_idempotencia + full-payload comparison; 409 on mismatch | ✅ Implementado |
| Revocation | Dispositivo revocado bloqueado; version_asignacion bump | ✅ Implementado |

---

## 1. Identidad del dispositivo

- **Backend:** `apps/api/src/auth/deps.py`, `models/dispositivo.py`
- **Mobile:** `apps/mobile/lib/auth/device_identity.dart` → `MethodChannel daily_system/device_identity` → `MainActivity.kt`
- **Motor nativo:** AndroidKeyStore, par de claves EC P-256 (curva `secp256r1`)
- **Clave privada:** generada e interceptada dentro de AndroidKeyStore; **nunca exportada**. Solo se expone el SPKI (X.509, base64) de la clave pública.
- **Signing:** `SHA256withECDSA` sobre el payload JCS canónico exactamente como lo serializa el backend.

### Prohibido (como autenticador principal)
- IMEI, Android ID, huella calculada por el cliente
- SharedPreferences como token de autenticación
- QR reutilizable
- Parámetros de query como auth en producción (solo dev/test)

---

## 2. Protocolo de activación (daily-v1)

```
POST /api/activaciones/codigos          (admin-only) → codigo_activacion (hash)
POST /api/activaciones/desafio          (público) → intento_id, nonce, expira_el
POST /api/activaciones/canjear          (público) → firma JCS + intento_id → credencial_bootstrap TEMPORAL (no JWT; un solo uso)
POST /api/auth/device/desafio           (Bearer: credencial_bootstrap) → challenge_id, nonce (daily-auth-v1)
POST /api/auth/device/canjear           → access token JWT ES256
GET  /api/mobile/bootstrap              (Bearer: access JWT) → identity + ruta_activa_unica
```

- Código de activación: un solo uso, vence con `MAX_INTENTOS_FALLIDOS=5` → estado `EXPIRED`
- `canjear`: SELECT FOR UPDATE (idempotente); `bootstrappear` solo para dispositivo `ACTIVE`
- **Casos A–D de idempotencia verificados:** replay exacto idempotente; firma distinta sobre mismo intento → `FIRMA_INVALIDA` (401, no heredan); dos intentos distintos mismo código → el segundo no es idempotente; canje concurrente → 1 consumo real + 1 idempotente
- Vector JCS: 285 bytes verificado byte a byte entre Dart y Python

---

## 3. JWT ES256 (daily-auth-v1)

**Claims congeladas:**

| Claim | Valor |
|---|---|
| `iss` | `daily-system-api` |
| `aud` | `daily-system-mobile` |
| `sub` | `usuario_id` (cobrador) |
| `negocio_id` | UUID |
| `device_id` | UUID del dispositivo activo |
| `public_key_hash` | SHA-256 del SPKI |
| `version_asignacion` | int (forzado por servidor en canje) |
| `protocol_version` | `"daily-auth-v1"` |
| `typ` | `"access"` |
| `jti` | UUID único |
| `iat` / `exp` | timestamps Bogotá |

### Fail-closed
En `apps/api/src/auth/token.py`:
- Algoritmo **obligatorio** ES256 (P-256)
- Rechaza: `none`, `HS256`, `RS256`, cualquier otra clave o claim faltante
- Claims congelados verificados server-side en cada request

### Renewal (daily-auth-v1)
```
POST /api/auth/device/desafio    (Bearer access JWT vigente o credencial_bootstrap) → challenge_id, nonce
Device firma nonce →
POST /api/auth/device/canjear     → nuevo access JWT (version_asignacion ACTUAL de la base)
```
- Single-use (consumido en transaction con SELECT FOR UPDATE)
- `version_asignacion` verificado en cada canje → bump de versión revoca tokens anteriores

---

## 4. Tenant y route isolation

- Tenant (`negocio_id`) derivado del JWT, **nunca** del request body
- Route (`ruta_id`) = única ruta activa del cobrador, derivada server-side
- `get_request_context` en `deps.py`: fail-closed — 0 o >1 rutas activas → 401
- `mobile_sync_service.py` revalida: solo `COBRADOR` con ruta activa vigente
- Listados de rutas/clientes/cobradores siempre scoped por `negocio_id` + (si cobrador) `route_id`

### Mobile client-side gaps (documentados, no resueltos)
- `pago_screen.dart:37-45` — créditos sin filtro de ruta (backend rechaza 403)
- `caja_main_screen.dart:34-36`, `inicio_screen.dart:59-66` — jornada abierta sin filtro de ruta
- `cobros_shell.dart:207-211` — rutas activas sin `cobrador_id`
- Estos son client-side; el backend los rechaza. No son una brecha financiera.

---

## 5. Idempotencia financiera

| Entidad | Clave | Payload comparison | On match | On mismatch |
|---|---|---|---|---|
| Pago | `clave_idempotencia` | full payload | Return existing | 409 (PaymentIdempotencyError) |
| Movimiento | `clave_idempotencia` | full payload | Return existing | 409 |
| Jornada cierre | `idempotencia_cierre` | canonical JSON (sort_keys) | Re-sync accepted | 409 (JornadaSyncException) |
| Device canje | `intento_id` | JCS signature | Idempotent return | 401 FIRMA_INVALIDA |

- `clave_idempotencia` min_length=1, stripped (`@field_validator`)
- Snapshot de cierre: hash SHA-256 reproducible, `json.dumps(sort_keys=True, separators=(",",":"))`

---

## 6. HTTP status codes

| Code | Uso |
|---|---|
| 401 | Sin autorización, JWT inválido/vencido/revocado, dispositivo inactivo, 0/>1 rutas activas, firma inválida |
| 403 | Rol insuficiente (admin-only endpoints) |
| 404 | Recurso no existe o no pertenece a scope (no revela existencia cross-ruta) |
| 409 | Idempotencia: clave repetida con payload diferente, o jornada CLOSED_SYNCED con snapshot distinto |
| 422 | Validación de request body (Pydantic) |

---

## 7. Prohibido tocar

Ver `DAILY-SYSTEM-ARCHIVO-MAESTRO-CONTINUIDAD-OPENCODE.md` §invariantes. Hasta nuevo aviso (requiere instrucción explícita):

- Migraciones de activación, `CodigoActivacion`, `IntentoActivacion`, `public_key`
- Challenge-response, JWT, OAuth/PKCE, Keystore
- Bootstrap, dependencias Flutter de auth, módulo productivo de activación web
- S3 outbox (push/ACK/retry)
- Renombrar S3 → S4

---

## 8. Secretos y configuración

- `infra/.env.example` — solamente plantilla
- `.env*` — gitignored
- La clave ES256 pública se sirve vía JWKS o env en dev
- `ALLOW_PG_TRUNCATE=1` — solo en tests con DB nombre `test`/`scratch` y `DAILY_ENV=test`
