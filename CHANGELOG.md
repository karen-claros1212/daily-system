# Changelog

## [Unreleased] — Reconciliación documental (2026-08-15)

Rama: `product/web-premium-v1` @ `bbb3e102`. Reconciliación del repositorio con el estado
canónico verificado (sin cambios funcionales; actualización de docs + evidencia).

### Docs
- Inventario documental clasificado A–E; 8 documentos históricos archivados en `docs/historical/` con banner.
- README.md, docs/STATUS.md, docs/README.md, docs/TESTING.md, docs/ARCHITECTURE.md reescritos al estado canónico 2026-08-15.
- docs/SECURITY.md, docs/OFFLINE-SYNC.md, docs/IMPLEMENTATION-PLAN.md actualizados (Web Premium, S4/S5, capa web security).
- docs/web/WEB-UI-BLUEPRINT.md marcado histórico (prototipo MOCK); el panel productivo vive en `apps/web/`.

### Current (canónico 2026-08-15)
- Backend pytest: **367 passed, 8 skipped** (SQLite)
- alembic head: `m8_negocio_nit` (invariante NIT por BD)
- Mobile flutter test: **177/177 passing** · flutter analyze: 14 infos preexistentes / 0 nuevos
- Web E2E Playwright: mock **107** + real **26** · `npm audit` = 0
- ruff: 127 errores en src/ (deuda conocida)
- CI: 3 workflows PASS (backend-ci · web-ci · ui-gate)

---

## [WEB-PREMIUM] — Panel web administrativo productivo (rama `product/web-premium-v1`, HEAD `bbb3e102`)

### Web (apps/web — Next.js 16 · React 19 · TypeScript · Tailwind)
- Login + sesión httpOnly `daily_admin_token`; identidad única vía `GET /api/auth/me`
- RBAC por capacidades server-side (`src/lib/rbac.ts`): COBRADOR / INVERSIONISTA / ADMINISTRADOR
- Superficies: dashboard, rutas, caja, reportes, dispositivos, suscripción, onboarding (`/registro`)
- BFF con route handlers (`src/app/api/*`) + cliente TS generado (`openapi-typescript`)
- E2E Playwright: mock 107 (incl. a11y axe) + real 26 (FastAPI + PostgreSQL)
- `next` 16.3.1 · `eslint-config-next` 16.3.1 · React 19.2.8 · TS 5.9.3 · `npm audit` = 0
- Fix `devIndicators: { position: 'top-right' }` en `next.config.mjs`
- CI: `web-ci.yml` (web-static · web-e2e-mock · web-real-integration) + `ui-gate.yml`

### Backend (apps/api)
- Routers `onboarding` (/api/onboarding), `auth/me`, `inversionista` (resumen, suscripción)
- Gate PG: `test_onboarding.py::TestNitConcurrentePostgres::test_13_dos_transacciones_concurrentes_mismo_nit_201_y_409`
- `backend-ci.yml` certifica alembic upgrade head + current + pytest en PostgreSQL 16

---

## [Unreleased] — Hardening B1–B7 + S0–S5 (histórico: rama `hardening/b1-b7-audit`)

> Nota: este bloque fue superado por los bloques S4/S5 y Web Premium. Se conserva como historia.

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
- UPSERT por PK con ON CONFLICT(id) DO UPDATE (nunca INSERT OR REPLACE)
- Protección de trabajo local pendiente durante pull (sync_queue + CLOSED_LOCAL_PENDING_SYNC)
- Preservación de reversal_of_payment_id en pull (S2-H2)
- S0: atomic session envelope (daily_session)
- S1: route isolation (scope derivado del servidor)
- S2: pull + local persistence
- **S3: outbox móvil→servidor — IMPLEMENTADO**
  - `migration_v5.dart` — sync_queue evolucionada: `datos` JSON, `idempotency_key`, provenance, `intento`, `ultimo_error`, `ultima_transicion`
  - `push_orchestrator.dart` — PushOrchestrator: lee sync_queue pendiente, envía por tipo al endpoint correcto
  - Payloads: PAYMENT → POST /api/pagos, REVERSAL → POST /api/pagos/{id}/reversar, MOVIMIENTO → POST /api/movimientos, JORNADA_CIERRE → POST /cerrar + POST /sincronizar
  - Estados: PENDIENTE_DE_SINCRONIZAR, ENVIANDO, SINCRONIZADO, ERROR_REINTENTABLE, CONFLICTO
  - Idempotent retry: misma key/payload/provenance en retry; lost response converge idempotentemente
  - server_entity_id durable: se guarda en sync_queue al recibir ACK
  - Local↔server ID mapping: REVERSAL usa server_payment_id (no local ID)
  - Route provenance R1→R2: fila de R1 no se transmite bajo R2 → CONFLICTO, 0 requests HTTP
  - 401 preserva outbox (ERROR_REINTENTABLE)
  - 409 mismatch → CONFLICTO (no reintentable); 409 match → 200 idempotente
  - ENVIANDO abandonado → recupera misma fila, no INSERT nueva
  - Dependencia: JORNADA_CIERRE espera PAYMENT/REVERSAL ACK de misma jornada
  - CLOSED_LOCAL_PENDING_SYNC → CLOSED_SYNCED solo tras ACK válido de /sincronizar
  - Push→pull reconciliation: pagos/movimientos/reversales empujados aparecen en GET /sync
  - reversal_of_payment_id reconciliado en pull

### Backend
- 409 idempotent en pago/movimiento/jornada; comparación full-payload
- Estado de jornada: OPEN → CLOSING → CLOSED_LOCAL_PENDING_SYNC → CLOSED_SYNCED (guards)
- `JornadaSyncException` (409) con validación de snapshot hash
- Revalidación de efectivo_esperado / efectivo_contado / diferencia en sincronizar_cierre
- `mobile_sync_service.py` con fail-closed (0 y >1 rutas activas → 401 en deps.py)
- `activacion.py` con bootstrap + auth + sync routes
- `m7_desafio_auth` alembic

---

## [S4-S5] — Reasignación de ruta + conflictos server-authoritative

### S4 — Reasignación R1→R2 (commits `b4da7ca`, `327c7fd`, `b75f2c4`)
- `ruta_id_origen` inmutable en `sync_queue`; fila de R1 no se transmite bajo R2 → CONFLICTO, 0 requests HTTP
- Ciclo completo de reasignación + endurecimiento estricto + orquestación de sync

### S5 — Conflict detection (`877f24d`)
- `apps/api/src/services/conflict_service.py` — PRE-CHECK layer server-authoritative
- 6 verificadores: pago, movimiento, jornada, apertura de jornada, reversal, ruta
- No reemplaza las validaciones inline (payment/movimiento/jornada service)
- Tests: `test_s5_conflict_service.py` (48 tests)

---

## [HARDENING-B1-B7] — Auth productivo + sync offline (c0a3a9c)

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

### Current (histórico)
- S0 session maintenance: PASS.
- S1 aislamiento ruta: PASS.
- S2 pull servidor→móvil: PASS.
- S3 outbox móvil→servidor: ✅ IMPLEMENTADO.

---

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
- Bot Telegram (cobrador/inversionista) — ⚠️ HISTÓRICO: no existe en el árbol. Cualquier bot futuro es exclusivamente administrativo; bot en móvil: PROHIBIDO.
- Panel inversionista — ⚠️ HISTÓRICO: hoy está cubierto por la Web Premium productiva (`apps/web/`); el prototipo MOCK `design/prototypes/web/` es referencia de diseño.
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
