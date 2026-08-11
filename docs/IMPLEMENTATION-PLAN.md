# Plan de Implementación — Daily System

**Proyecto:** daily-system
**Versión:** 1.3
**Fecha:** 2026-07-31
**Estado:** M0-M3 completos, B1-B7 hardening completado, S3 pendiente · M3.6.6-F

> ## ⚠️ NOTA DE RECONCILIACIÓN (2026-08-06) — estados históricos desactualizados
>
> Este documento se conserva como **historia**. Las siguientes afirmaciones están **DESACTUALIZADAS** y NO se presentan como evidencia de implementación real:
>
> - **`apps/web` productiva: NO EXISTE.** El árbol real del repositorio (`apps/`) contiene únicamente `api` y `mobile`. `apps/web` es una carpeta vacía.
> - **Panel inversionista productivo: NO EXISTE.** El material web actual es un prototipo estático HTML/CSS en `design/prototypes/web/` (datos hardcodeados, sin JS/API/auth/build), declarado en `docs/web/WEB-UI-BLUEPRINT.md` como "Prototipo visual (no aplicación productiva)".
> - **Bot Telegram productivo: NO EXISTE.** No hay `apps/telegram-bot/` en el árbol real.
> - **La aplicación móvil del cobrador NO contiene bot.** Un bot, si se desarrolla, pertenece exclusivamente al entorno administrativo posterior. Bot en móvil: PROHIBIDO.
>
> **La evidencia real del repositorio y las pruebas prevalece sobre estados históricos incorrectos.**
> Ver estado oficial en `docs/STATUS.md`, `DAILY-SYSTEM-CONTEXT-HANDOFF.md` y `DAILY-SYSTEM-ARCHIVO-MAESTRO-CONTINUIDAD-OPENCODE.md`.

---

## Hito M0 — Fundación ejecutable ✅

**Estado:** COMPLETADO
**Archivos:** apps/api/src/, apps/api/migrations/, infra/
**Pruebas:** 28/28 (M0 tests)
**Dependencias:** Ninguna
**Commit de cierre:** 724a644

### Requisitos

| # | Requisito | Estado | Archivos | Pruebas | Commit |
|---|---|---|---|---|---|
| M0.1 | Repo público creado | ✅ | `.gitignore`, `opencode.json` | — | 61c2b9a |
| M0.2 | AGENTS.md configurado | ✅ | `AGENTS.md` | — | 90493db |
| M0.3 | Protocolo Engram | ✅ | `docs/ENGRAM-PROTOCOL.md` | — | 90493db |
| M0.4 | Protocolo Graphify | ✅ | `docs/GRAPHIFY-PROTOCOL.md` | — | 61c2b9a |
| M0.5 | Infraestructura Docker | ✅ | `infra/docker-compose.yml` | — | e5af682 |
| M0.6 | Backend FastAPI skeleton | ✅ | `apps/api/src/main.py` | — | e5af682 |
| M0.7 | Database layer | ✅ | `apps/api/src/database.py` | — | e5af682 |
| M0.8 | Modelos SQLAlchemy (9 tablas) | ✅ | `apps/api/src/models/` | — | e5af682 |
| M0.9 | Schemas Pydantic | ✅ | `apps/api/src/schemas/` | — | e5af682 |
| M0.10 | Migration Alembic init | ✅ | `apps/api/alembic.ini` | — | e5af682 |
| M0.11 | Routes: negocio | ✅ | `apps/api/src/routes/negocio.py` | — | e5af682 |
| M0.12 | Routes: ruta | ✅ | `apps/api/src/routes/ruta.py` | — | e5af682 |
| M0.13 | Routes: cliente | ✅ | `apps/api/src/routes/cliente.py` | — | e5af682 |
| M0.14 | Routes: credito | ✅ | `apps/api/src/routes/credito.py` | — | e5af682 |
| M0.15 | Routes: pago | ✅ | `apps/api/src/routes/pago.py` | — | e5af682 |
| M0.16 | Routes: hoja_viva | ✅ | `apps/api/src/routes/hoja_viva.py` | — | e5af682 |
| M0.17 | Services: calculation_service | ✅ | `apps/api/src/services/calculation_service.py` | — | e5af682 |
| M0.18 | Tests: calculaciones financieras | ✅ | `apps/api/src/tests/test_calculations.py` | 15 tests | e5af682 |
| M0.19 | Tests: API integration | ✅ | `apps/api/src/tests/test_api.py` | 13 tests | 65c90f8 |
| M0.20 | Health endpoint | ✅ | `apps/api/src/main.py` | 1 test | 65c90f8 |

---

## Hito M1 — Hoja viva y pagos ✅

**Estado:** COMPLETADO
**Dependencias:** M0 completo
**Archivos:** `apps/api/src/routes/hoja_viva.py`, `apps/api/src/services/hoja_viva_service.py`, `payment_service.py`
**Pruebas:** 38/38 (M1 tests)
**Commit de cierre:** e2d8e37

### Requisitos

| # | Requisito | Estado | Archivos | Pruebas | Commit |
|---|---|---|---|---|---|
| M1.1 | Calcular crédito (cuota × días) | ✅ | `calculation_service.py` | 5 tests | e2d8e37 |
| M1.2 | Calcular caja (asignar pagos) | ✅ | `calculation_service.py` | 5 tests | e2d8e37 |
| M1.3 | Hoja viva del día | ✅ | `hoja_viva_service.py` | 4 tests | e2d8e37 |
| M1.4 | Registrar pago parcial | ✅ | `pago.py` route | 3 tests | e2d8e37 |
| M1.5 | Reversar pago | ✅ | `pago.py` route | 2 tests | e2d8e37 |
| M1.6 | Historial de pagos | ✅ | `pago.py` route | 2 tests | e2d8e37 |
| M1.7 | Cálculo de pico y residuo | ✅ | `calculation_service.py` | 3 tests | 965e0da |
| M1.8 | Renegociación básica | ✅ | `credito.py` route | 2 tests | 965e0da |

### Notas M1
- `calcular_credito()` produce resultados idénticos al documento maestro
- `calcular_caja()` maneja múltiples abonos parciales
- Hoja viva genera PDF o JSON imprimible
- Idempotencia con 409 Conflict en pagos duplicados

---

## Hito M2 — Jornada, caja y TERMINAR JORNADA ✅ (GATE FINAL)

**Estado:** COMPLETADO
**Dependencias:** M1 completo
**Archivos:** `apps/api/src/routes/jornada.py`, `apps/api/src/services/jornada_service.py`, `movimiento_service.py`
**Pruebas:** 47/47 (M2 tests)
**Commit de cierre:** 485671e (implementación), b6d48bb (linting)

### Requisitos

| # | Requisito | Estado | Archivos | Pruebas | Commit |
|---|---|---|---|---|---|
| M2.1 | Iniciar jornada | ✅ | `jornada.py` route | 2 tests | 485671e |
| M2.2 | Cerrar jornada | ✅ | `jornada.py` route | 3 tests | 485671e |
| M2.3 | Total recaudado por jornada | ✅ | `jornada.py` route | 2 tests | 3f59bd3 |
| M2.4 | Movimientos de caja | ✅ | `movimiento_service.py` | 3 tests | 3f59bd3 |
| M2.5 | Reporte de jornada | ✅ | `jornada_service.py` | 2 tests | 86779e8 |
| M2.6 | Anular jornada | ✅ | `jornada.py` route | 2 tests | 2826590 |

### Notas M2
- Una jornada solo puede cerrar si todas las cuotas del día están cubiertas o marcadas como impagas
- El pico (abono % cuota) se registra como abono a la siguiente cuota
- **M2 Gate Final:** 138 tests passing, alembic head = m3_dispositivo, PostgreSQL migrations applied
- Idempotencia obligatoria en apertura de jornada
- Hash reproducible SHA-256 de snapshot de jornada
- PDF recuperable desde snapshot

---

## Hito M3 — Suscripción, Telegram e inversionista ✅

> **NOTA DE RECONCILIACIÓN (2026-08-06):** las filas M3.2 (Bot cobrador), M3.3 (Bot inversionista), M3.4 (Panel web) y M3.5 (reporte automático) **NO corresponden a artefactos existentes en el repositorio actual** (`apps/telegram-bot/` y `apps/web/` no existen; `telegram_bot.py` no existe). Se conservan como registro histórico pero **no** como evidencia de implementación. Los únicos requisitos M3 verificables en el árbol real son los relacionados con suscripciones/planes (`suscripcion.py`, `negocio.py`). La corrección prevalece: véase la nota de reconciliación al inicio del documento.

**Estado:** COMPLETADO (suscripciones) · **DESACTUALIZADO** (telegram/panel web — ver nota)
**Dependencias:** M2 completo
**Archivos:** `apps/api/src/routes/suscripcion.py`, `apps/telegram-bot/`, `apps/web/`
**Pruebas:** 27/27 (M3 tests)
**Commit de cierre:** 871d1de (implementación), b6d48bb (linting)

### Requisitos

| # | Requisito | Estado | Archivos | Pruebas | Commit |
|---|---|---|---|---|---|
| M3.1 | Planes y suscripciones | ✅ | `suscripcion.py` | 4 tests | 871d1de |
| M3.2 | Bot Telegram (cobrador) | ⚠️ DESACTUALIZADO — no existe | `apps/telegram-bot/` no existe en árbol | — | 871d1de |
| M3.3 | Bot Telegram (inversionista) | ⚠️ DESACTUALIZADO — no existe | `apps/telegram-bot/` no existe en árbol | — | 871d1de |
| M3.4 | Panel inversionista (web) | ⚠️ DESACTUALIZADO — no existe | `apps/web/` está vacío | — | 871d1de |
| M3.5 | Reporte diario automático | ⚠️ DESACTUALIZADO — no existe | `telegram_bot.py` no está en árbol | — | 871d1de |
| M3.6 | Límite de rutas por plan | ✅ | `negocio.py` route | 2 tests | e44b09e |

### Notas M3
- Plan free: 1 ruta, 100 clientes
- Plan básico: 5 rutas, 500 clientes
- Plan pro: rutas ilimitadas, clientes ilimitados
- M3.6.x: Flutter Offline Alpha + Visual Alpha Premium (Material 3 Expressive)
- M3.6.6: Domain model unification — JornadaGuard, atomic payments, typed exceptions
- M3.6.6-F: Migration V4, JornadaSnapshot único, idempotencia obligatoria

> ⚠️ M3.2-M3.5: los ítems de Bot Telegram y Panel inversionista están **DESACTUALIZADOS**. `apps/telegram-bot/` no existe en el árbol real; `apps/web/` está vacío. Estos elementos NO son parte del producto actual. Cualquier bot futuro es exclusivamente administrativo; bot en móvil: **PROHIBIDO**.

---

## Hito M4 — Importación OCR

**Estado:** PENDIENTE
**Dependencias:** M3 completo
**Archivos:** `apps/api/src/services/ocr_service.py`
**Pruebas:** Pendientes
**Commit de cierre:** —

### Requisitos

| # | Requisito | Estado | Archivos | Pruebas | Commit |
|---|---|---|---|---|---|
| M4.1 | OCR de comprobantes | ⬜ PENDIENTE | `ocr_service.py` | 3 tests | — |
| M4.2 | Validación automática | ⬜ PENDIENTE | `ocr_service.py` | 2 tests | — |
| M4.3 | Upload de imagen | ⬜ PENDIENTE | `pago.py` route | 2 tests | — |

---

## Hito M5 — Score, chatbot e inteligencia

**Estado:** PENDIENTE
**Dependencias:** M4 completo
**Archivos:** `apps/api/src/services/score_service.py`, `apps/api/src/services/chatbot_service.py`
**Pruebas:** Pendientes
**Commit de cierre:** —

### Requisitos

| # | Requisito | Estado | Archivos | Pruebas | Commit |
|---|---|---|---|---|---|
| M5.1 | Score de cobro por cliente | ⬜ PENDIENTE | `score_service.py` | 3 tests | — |
| M5.2 | Chatbot asistente | ⬜ PENDIENTE | `chatbot_service.py` | 2 tests | — |
| M5.3 | Predicción de pagos | ⬜ PENDIENTE | `score_service.py` | 2 tests | — |
| M5.4 | Alertas de mora | ⬜ PENDIENTE | `score_service.py` | 2 tests | — |

---

## Hito B1-B7 — Harden Auth + Bootstrap + Sync S0-S2

> **Estado:** ✅ COMPLETADO (c0a3a9c, rama `hardening/b1-b7-audit`)
> **Commit de cierre:** c0a3a9c
> **Ver:** [Security](SECURITY.md), [Offline Sync](OFFLINE-SYNC.md), [Architecture](ARCHITECTURE.md)

Bloque de endurecimiento de autenticación y sincronización offline. No es M4-M6; vive en `hardening/b1-b7-audit`.

### Entregables

| # | Bloque | Estado | Auth | Descripción |
|---|---|---|---|---|
| B1 | JWT ES256 fail-closed | ✅ | backend | Rechaza none/HS256/RS256; claims congeladas |
| B1b | Device binding | ✅ | backend | public_key_hash en JWT + version_asignacion |
| B2 | Activation (daily-v1) | ✅ | backend | Challenge-response single-use, MAX_INTENTOS=5→EXPIRED |
| B2-H2 | Bootstrap | ✅ | backend | GET /api/mobile/bootstrap, ruta única |
| B3 | AndroidKeyStore | ✅ | mobile | EC P-256 no exportable, MethodChannel |
| B4 | Route isolation | ✅ | backend+mobile | Scope server-side, 0/>1 rutas → 401 |
| B7 | Mobile auth bridge | ✅ | mobile | lib/auth/: AuthHttpClient, DeviceAuthClient, JCS |
| S0 | Session maintenance | ✅ | mobile | Renovación antes de expirar (daily-auth-v1) |
| S2 | Pull + local persist | ✅ | mobile | GET /api/mobile/sync, SyncRepository UPSERT PK |

### Tests

| Gate | Resultado | Comando |
|---|---|---|
| Backend (SQLite) | 255 passed, 7 skipped | `pytest src/tests/ -q` |
| Mobile | 147 passing | `flutter test` |
| Alembic | m7_desafio_auth (head), clean | `alembic check` |
| Analyzer | No issues found | `flutter analyze` |

---

## Hito S3 — Offline sync outbox (mobile → server)

> **Estado:** ⏳ PENDIENTE
> **Dependencias:** B1-B7 + S0-S2 completos
> **Commit de cierre:** — (no iniciado)

Outbox push, ACK, retry con backoff, resolución de conflictos. Ver [OFFLINE-SYNC.md](OFFLINE-SYNC.md).

**NO** enviar `negocio_id`/`cobrador_id`/`ruta_id` como autoridad desde el móvil hasta que S3 esté implementado.

---

## Hito M6 — Producción y despliegue

**Estado:** PENDIENTE
**Dependencias:** M5 completo
**Archivos:** `infra/docker-compose.prod.yml`, `infra/nginx/`, `.github/workflows/`
**Pruebas:** Pendientes
**Commit de cierre:** —

### Requisitos

| # | Requisito | Estado | Archivos | Pruebas | Commit |
|---|---|---|---|---|---|
| M6.1 | Docker Compose producción | ⬜ PENDIENTE | `infra/docker-compose.prod.yml` | — | — |
| M6.2 | CI/CD pipeline | ⬜ PENDIENTE | `.github/workflows/ci.yml` | — | — |
| M6.3 | Nginx reverse proxy | ⬜ PENDIENTE | `infra/nginx/` | — | — |
| M6.4 | SSL/TLS | ⬜ PENDIENTE | `infra/nginx/` | — | — |
| M6.5 | Monitoreo | ⬜ PENDIENTE | `infra/prometheus/` | — | — |
| M6.6 | Backups automáticos | ⬜ PENDIENTE | `infra/scripts/` | — | — |
| M6.7 | Logs centralizados | ⬜ PENDIENTE | `infra/` | — | — |

---

## Resumen de Progreso

| Hito | Estado | Progreso | Tests |
|---|---|---|---|
| **M0** | ✅ COMPLETADO | 22/22 (100%) | 28/28 |
| **M1** | ✅ COMPLETADO | 8/8 (100%) | 38/38 |
| **M2** | ✅ COMPLETADO | 6/6 (100%) | 47/47 |
| **M3** | ✅ COMPLETADO | 6/6 (100%) | 27/27 |
| **M4** | ⬜ PENDIENTE | 0/3 (0%) | — |
| **M5** | ⬜ PENDIENTE | 0/4 (0%) | — |
| **M6** | ⬜ PENDIENTE | 0/7 (0%) | — |
| **B1-B7 hardening** | ✅ COMPLETADO | — | 255 passed + 7 skip (backend) / 147 (mobile) |
| **TOTAL** | M0-M3 + B1-B7 ✅ | **78% base + hardening** | **255+147** |

---

## Reglas de Avance

1. **M0 primero:** No avanzar a M1 sin M0 completo (modelos + migraciones + tests)
2. **Tests antes de merge:** Cada requisito debe tener tests pasando
3. **Commit por requisito:** Un commit por requisito completado
4. **Graphify después de M0:** Actualizar grafo al cerrar M0
5. **Engram en cada hito:** Guardar `mem_session_summary` al cerrar cada hito
