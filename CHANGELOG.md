# Changelog

## [Unreleased] — Hardening B1–B7 + Mobile Auth/Sync (HEAD: c0a3a9c)

Rama de trabajo: `hardening/b1-b7-audit`. `master` (`486d08b`) no contiene estos cambios.

### Security
- Tenant isolation y route isolation endurecidos (server-side scope, `0 y >1 rutas → 401`)
- Activación productiva de dispositivo (challenge-response daily-v1, single-use)
- AndroidKeyStore EC P-256 no exportable (SHA256withECDSA)
- Challenge-response daily-auth-v1 (renovación de sesión)
- JWT ES256 con device/user/negocio/version_asignacion binding; fail-closed (rechaza none/HS256/RS256)
- Bootstrap productivo con exactamente una ruta activa
- JCS (RFC 8785) canonicalización byte-exacta
- Idempotencia financiera en pagos, movimientos y cierre de jornada
- Hash reproducible SHA-256 de snapshot de jornada (canonical JSON)
- Revocación y reemplazo de dispositivo (admin-only)

### Mobile / Offline
- Bridge Dart ↔ AndroidKeyStore ↔ backend (`MethodChannel daily_system/device_identity`)
- AuthHttpClient centralizado (bearer JWT, 401 → borrarToken)
- DeviceAuthClient (desafío/canje, renovación antes de expirar)
- AuthTokenStore (persistencia segura)
- JCS Dart (RFC 8785) con vector de prueba byte-exacto contra backend
- GET /api/mobile/sync — pull dataset ruta activa única
- DTOs y persistencia sobre SQLite existente (reutiliza tablas lib/database/tables.dart)
- UPSERT por PK con ON CONFLICT(id) DO UPDATE (nunca INSERT OR REPLACE)
- Protección de trabajo local pendiente durante pull (sync_queue + CLOSED_LOCAL_PENDING_SYNC)
- Preservación de reversal_of_payment_id en pull (S2-H2)
- S0: atomic session envelope (daily_session)
- S1: route isolation (scope derivado del servidor)
- S2: pull + local persistence

### Backend
- 409 idempotent en pago/movimiento/jornada; comparación full-payload
- Estado de jornada: OPEN → CLOSING → CLOSED_LOCAL_PENDING_SYNC → CLOSED_SYNCED (guards)
- `JornadaSyncException` (409) con validación de snapshot hash
- Revalidación de efectivo_esperado / efectivo_contado / diferencia en sincronizar_cierre
- `mobile_sync_service.py` con fail-closed (fail-closed: 0 y >1 rutas activas → 401 en deps.py)
- `activacion.py` con bootstrap + auth + sync routes
- `m7_desafio_auth` alembic (head)

### Current
- S0 session maintenance: PASS
- S1 route isolation: PASS
- S2 server→mobile pull/persistence: PASS
- S3 outbox (mobile→server push/ACK/retry/conflictos): PENDIENTE
- Backend pytest: 255 passed, 7 skipped (257 funciones)
- Mobile flutter test: 147 passing
- alembic: m7_desafio_auth (head), clean
- ruff: 97 errors en src/ (deuda conocida — no fue limpiado en hardening)

### Repository
- `hardening/b1-b7-audit` contiene todos los cambios B1–B7
- `master` (`486d08b`) no fusionado; 0/7 detrás de hardening HEAD

### Historias no implementadas (arqueología del CHANGELOG)
- [M3.5] Bot Telegram (cobrador/inversionista): **NO EXISTE** en el árbol (`apps/telegram-bot/` no existe)
- [M3.4] Panel inversionista (web): **NO EXISTE** (`apps/web/` vacío; solo prototipo MOCK `design/prototypes/web/`)
- [M3.3] Reporte diario automático: pendiente

---

## [HARDENING-B1-B7] - Auth productivo + sync offline (c0a3a9c)

### Security
- Tenant isolation y route isolation endurecidos.
- Activación productiva de dispositivo.
- AndroidKeyStore EC P-256 no exportable.
- Challenge-response daily-v1 / daily-auth-v1.
- JWT ES256 con device/user/business/version binding.
- Bootstrap productivo con exactamente una ruta activa.
- Renovación de sesión mediante challenge-response.
- Sesión móvil en envelope atómico daily_session.

### Mobile / Offline
- Bridge Dart ↔ AndroidKeyStore ↔ backend.
- GET /api/mobile/sync.
- DTOs y persistencia sobre SQLite existente.
- Pull de clientes, créditos, cuotas, jornadas, pagos y movimientos.
- UPSERT por PK con ON CONFLICT(id), sin INSERT OR REPLACE.
- Protección de trabajo local pendiente durante pull.
- Preservación de reversal_of_payment_id.

### Current
- S0 session maintenance: PASS.
- S1 aislamiento ruta: PASS.
- S2 pull servidor→móvil: PASS.
- S3 outbox móvil→servidor: PENDIENTE.

### Repository
- `hardening/b1-b7-audit` contiene estos cambios.
- `master` todavía no contiene este hardening.

## [M3.6.6-F] - Migration V4
- JornadaSnapshot único, idempotencia obligatoria
- Hash reproducible SHA-256
- PDF recuperable desde snapshot

## [M3.6.6] - Domain model unification
- JornadaGuard, atomic payments, typed exceptions

## [M3.6.5] - Atomic post-close block
- JornadaCerradaException + PDF evidence

## [M3.6.4] - Integration test validation
- Transactional and offline emulator validation

## [M3.6.3] - Navigation enums fix
- Real SQLite data, ThemeExtension

## [M3.6.2] - IndexedStack navigation
- Real SQLite data + design tokens

## [M3.6.1] - Visual Alpha Premium
- Material 3 Expressive redesign

## [M3.6] - Flutter Offline Alpha
- APK construida con 10 pantallas

## [M3] - Suscripcion, Telegram, inversionista
- Planes y suscripciones
- Bot Telegram (cobrador/inversionista) — ⚠️ DESACTUALIZADO: `apps/telegram-bot/` no existe en el árbol real. No es parte del producto. Cualquier bot futuro es exclusivamente administrativo; bot en móvil: PROHIBIDO.
- Panel inversionista — ⚠️ DESACTUALIZADO: `apps/web/` está vacío. Solo prototipo estático `design/prototypes/web/` (MOCK).
- Reporte diario automático — pendiente (no implementado)
- Límite de rutas por plan

## [M2] - Jornada, caja y Terminar Jornada
- Iniciar/cerrar/anular jornada
- Movimientos de caja
- Reporte de jornada

## [M1] - Hoja viva y pagos
- Calcular crédito, caja, pico y residuo
- Hoja viva del día
- Registrar/reversar pago
- Historial de pagos
- Renegociación básica

## [M0] - Fundación ejecutable
- Repo, AGENTS.md, Engram, Graphify
- Infraestructura Docker
- Backend FastAPI
- Database layer, modelos, schemas
- Routes, services, tests
