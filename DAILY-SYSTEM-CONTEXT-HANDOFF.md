# DAILY-SYSTEM-CONTEXT-HANDOFF

**Handoff operativo vigente — Daily System**

**Ruta de checkout canónica:** `/home/jesus/proyectos/daily-system`

| Campo | Valor |
|---|---|
| **Rama de trabajo** | `hardening/b1-b7-audit` |
| **HEAD (repositorio)** | Dinámico: `git rev-parse HEAD` (Git es autoridad; SHA no se hardcodea) |
| **HEAD (código S0-S2 baseline)** | `c0a3a9c1646358fea4badc45bc9cdf5d6e2a1216` |
| **master** | `486d08b` (no contiene el hardening B1-B7) |
| **Alembic head** | `m7_desafio_auth` |
| **Tests backend (SQLite)** | 255 passed, 7 skipped (257 funciones) |
| **Tests mobile** | 147 passing |
| **flutter analyze** | No issues found |

> `master` (486d08b) es una línea histórica que precede al hardening. Todo el trabajo de auth/sync productivo está en `hardening/b1-b7-audit`. No usar master como base.

---

## 1. Estado del producto (verificado 2026-08-11)

| Estado | Bloque |
|---|---|
| ✅ PASS | M0-M3 (backend financiero, hoja viva, suscripciones) |
| ✅ PASS | B1-B7 hardening (auth, device, activation, bootstrap) |
| ✅ PASS | S0 — session maintenance (renovación antes de expirar) |
| ✅ PASS | S1 — route isolation (scope server-side, cliente no elige ruta) |
| ✅ PASS | S2 — pull servidor→móvil + persistencia SQLite (UPSERT por PK) |
| ⏳ PENDIENTE | S3 — outbox móvil→servidor (push / ACK / retry / conflictos) |
| ⏳ PENDIENTE | Web productiva (`apps/web/` vacío; solo prototipo MOCK) |
| ⏳ PENDIENTE | Verificado en dispositivo físico (solo emulador API 35) |
| ⛔ NO EXISTE | PowerSync (no es la arquitectura; usa SQLite + sync_queue + capa propia) |
| ⛔ NO EXISTE | Auth por sesión (es JWT ES256 + AndroidKeyStore) |
| ⛔ NO EXISTE | Bot Telegram, panel inversionista productivo |
| ⛔ PROHIBIDO | Bot en móvil |

---

## 2. Arquitectura productiva de auth

```
1. Device genera EC P-256 en AndroidKeyStore (privada no exportable)
2. POST /api/activaciones/desafio → nonce + intento_id (daily-v1, single-use)
3. Device firma nonce con JCS (RFC 8785) → SHA256withECDSA
4. POST /api/activaciones/canjear → credencial_bootstrap TEMPORAL (no JWT; un solo uso, nunca reutilizado como access token)
5. POST /api/auth/device/desafio (Bearer: credencial_bootstrap) → challenge (daily-auth-v1)
6. Device firma challenge → POST /api/auth/device/canjear → access token JWT ES256 (claims congeladas)
7. GET /api/mobile/bootstrap (Bearer: access JWT) → identity (negocio, cobrador, ruta única)
8. AuthHttpClient (mobile) usa Bearer JWT; renovación S0 antes de expirar
```

**Componentes:**
- `MethodChannel daily_system/device_identity` → `MainActivity.kt` → AndroidKeyStore (EC P-256)
- JWT claims congeladas: iss/aud/sub/negocio_id/device_id/public_key_hash/version_asignacion/protocol_version/typ/jti/iat/exp
- Fail-closed: rechaza none/HS256/RS256
- `get_request_context` (deps.py): fail-closed; 0 o >1 rutas activas → 401

Ver `docs/SECURITY.md`.

## 3. Arquitectura productiva de sync

```
S0  Session maintenance (mobile)     — ✅ PASS
S1  Route isolation (backend)        — ✅ PASS
S2  Pull + local persistence (S2)    — ✅ PASS
S3  Outbox push/ACK/retry (PENDIENTE)
```

**Implementado (S0-S2):**
- `lib/sync/sync_client.dart` — GET /api/mobile/sync, session renewal
- `lib/sync/sync_repository.dart` — UPSERT por PK (ON CONFLICT), protección de pendientes
- `lib/sync/sync_models.dart` — SyncDataset/DTOs (snake_case ←→ camelCase)
- `lib/auth/` — AuthHttpClient, DeviceAuthClient, DeviceIdentity, JCS, TokenStore

**Pendiente (S3):**
- Outbox local → push al server → ACK/NACK → retry reintentable → resolución de conflictos
- Los endpoints individuales de push YA EXISTEN (POST /api/pagos, POST /api/pagos/{id}/reversar, POST /api/movimientos, POST /api/jornadas/{id}/cerrar, POST /api/jornadas/{id}/sincronizar). Lo que falta: el envelope de outbox móvil, ACK/NACK, persistencia de idempotency keys, resolución de conflictos. Definir en `docs/OFFLINE-SYNC.md` (sección S3).

## 4. Hoja Viva y modelo offline existente

- SQLite local con migraciones v2/v3/v4 (`lib/database/`)
- `lib/domain/` — tipos financieros, excepciones, `JornadaGuard`
- `lib/services/` — caja, pago, hoja_viva, jornada, movimiento, sync_queue, pdf
- `lib/models/` — JornadaSnapshot, CajaResultado
- Jornada state machine: OPEN → CLOSING → CLOSED_LOCAL_PENDING_SYNC → CLOSED_SYNCED
- Pagos/movimientos: append-only, trazables, idempotentes (clave_idempotencia, full-payload, 409)
- Snapshot con hash SHA-256 reproducible (canonical JSON)

## 5. Restricciones para el agente siguiente

1. **Master/merge/tag/deploy sin autorización: PROHIBIDO.** Ver SECURITY.md §7 ("Prohibido tocar").
2. **No tocar** sin instrucción explícita: migraciones de activación, `CodigoActivacion`, `IntentoActivacion`, `public_key`, challenge-response, JWT/OAuth/PKCE, Keystore, bootstrap, dependencias Flutter de auth, módulo web.
   - **S3 es el bloque actual autorizado.** El outbox (mobile→server push, ACK, retry, conflictos) puede evolucionarse conforme a `docs/OFFLINE-SYNC.md`, reutilizando servicios y endpoints financieros existentes (`POST /api/pagos`, `POST /api/pagos/{id}/reversar`, `POST /api/movimientos`, `POST /api/jornadas/{id}/cerrar`, `POST /api/jornadas/{id}/sincronizar`). No reconstruir auth, Hoja Viva ni el modelo financiero.
3. **No renombrar S3 a S4.** S3 es el bloque actual.
4. **Ruta canónica:** `/home/jesus/proyectos/daily-system`
5. **Documentación obligatoria como gate de cierre de bloque.** Ver AGENTS.md §Workflow (pasos `/plan` → `/review` → `/test` → `/handoff`). Cada bloque requiere su cierre documental antes de avanzar.

## 6. Tests / gates

```bash
# Mobile
cd apps/mobile && flutter analyze        # No issues found
cd apps/mobile && flutter test          # 147 passing
dart run tool/generate_design_tokens.dart --check  # tokens determinísticos

# Backend (SQLite — default)
cd apps/api/src && python3 -m pytest tests/ -q    # 255 passed, 7 skipped
cd apps/api && python3 -m alembic check          # No new upgrade operations

# Backend (PG concurrency — requiere scratch DB)
export API_DATABASE_URL="postgresql://cobro:cobro_secret@localhost:7103/cobro_scratch_b6_pg"
export DAILY_ENV=test
export ALLOW_PG_TRUNCATE=1
python3 -m pytest src/tests/ -q
# Nota: cobro-postgres necesita `ALTER ROLE cobro WITH PASSWORD 'cobro_secret'` al reiniciar

# UI Gate
scripts/ci/ui_gate.sh                     # PASS (GitHub Actions)
```

> **Backend CI no existe** en GitHub Actions (solo `ui-gate.yml` para mobile).
> **ruff:** 97 errores en `apps/api/src/` (deuda conocida, no resuelta en hardening).

## 7. Próximos pasos (siguiente bloque)

**S3 — outbox móvil→servidor (push/ACK/retry/conflictos).**
- Diseñar contrato de push (POST individual con idempotency keys, o endpoint batch)
- ACK/NACK, retry reintentable, resolución de conflictos (snapshot de jornada)
- Documentar en `docs/OFFLINE-SYNC.md`

**Pendientes adicionales:**
- M4: Importación OCR (`ocr_service.py` no existe)
- M5: Score, chatbot, inteligencia
- M6: Producción y despliegue
- Verificado en dispositivo físico (solo emulador API 35)
- CI backend (GitHub Actions)

## 8. Documentación actual

| Documento | Tipo | Propósito |
|---|---|---|
| [README.md](README.md) | Raíz | Índice + inicio rápido |
| [docs/STATUS.md](docs/STATUS.md) | Estado vivo | Estado productivo verificado |
| [docs/README.md](docs/README.md) | Índice | Navegador documental |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Normativo | Arquitectura vigente |
| [docs/SECURITY.md](docs/SECURITY.md) | Normativo | Auth, device, tenant, ruta, idempotencia |
| [docs/OFFLINE-SYNC.md](docs/OFFLINE-SYNC.md) | Normativo | S0-S3 contract |
| [docs/TESTING.md](docs/TESTING.md) | Estado vivo | Suites, gates, CI, scratch DB |
| [docs/IMPLEMENTATION-PLAN.md](docs/IMPLEMENTATION-PLAN.md) | Estado vivo | Roadmap |
| [AGENTS.md](AGENTS.md) | Protocolo | Instrucciones para agentes OpenCode |
| [DAILY-SYSTEM-ARCHIVO-MAESTRO-CONTINUIDAD-OPENCODE.md](DAILY-SYSTEM-ARCHIVO-MAESTRO-CONTINUIDAD-OPENCODE.md) | Archivo maestro | Continuidad entre sesiones |

---

> **Histórico:** esta sección preserva la auditoría UX/UI del 5 de agosto. El contenido original de esta auditoría se mueve a `docs/historical/` al finalizar la reconciliación. El handoff operativo vigente está arriba.

---

## 9. Historial de auditoría UX/UI (2026-08-05)

**Fecha de auditoría:** 2026-08-05
**Auditor:** opencode (big-pickle) — reconstrucción desde copia local

### Cadena de cierre de la auditoría

```
BASE_SHA        3a1a566  (punto de comparación "antes")
CODE_SHA        8cfe225  (código auditado — UI, tests, goldens)
EVIDENCE_SHA    95b2488  (68 capturas + script autovalidado + manifest)
GATE_SHA        fec6fa5 + 30b2984  (corrección y dedupe del paso generador)
AUDIT_CONTENT   10ea745  (contenido sustantivo del audit)
FINAL_HEAD      72f6ac2  (último commit auditado)
486d08b         (commits posteriores documentales, no alteran el contenido auditado)
```

### Estado de verificación (según README/audit — 2026-08-05)

| Verificación | Estado |
|---|---|
| APK debug construido | ✅ PASS |
| Verificado en emulador API 35 | ✅ PASS |
| Verificado en dispositivo físico | ⏳ PENDING |
| Tests móviles | 68/68 — **declarado, no re-ejecutado por este auditor** |
| Analyzer | "No issues found!" — **no re-ejecutado** |
| Backend pytest | 138/138 (STATUS.md, stale) — **no re-ejecutado** |

### Veredicto UX/UI

- APK debug construido ✅ PASS
- Emulador API 35 ✅ PASS
- Dispositivo físico ⏳ PENDING
- 68 capturas reales (phone/tablet × light/dark + web) con manifest SHA-256

Ver `docs/ui-audit/` para la auditoría completa.