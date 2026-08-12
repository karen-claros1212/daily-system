# STATUS — Daily System

**Proyecto:** daily-system
**Última actualización:** 2026-08-12
**Ruta de trabajo verificada (local):** `/home/jesus/proyectos/daily-system`
**Rama de trabajo:** `hardening/b1-b7-audit`
**HEAD (repositorio):** dinámico — `git rev-parse HEAD` (Git es autoridad; SHA no se hardcodea en docs)
**HEAD (código S0-S2 baseline):** `c0a3a9c1646358fea4badc45bc9cdf5d6e2a1216`
**master:** `486d08b1584684a4328825142209776fce477670` (no contiene el hardening B1-B7)
**Repo:** https://github.com/karen-claros1212/daily-system

> ## ⚠️ NOTA DE RECONCILIACIÓN (2026-08-06 → 2026-08-11)
>
> Las secciones históricas de este archivo (abajo) se conservan como historia. Los estados que NO se corresponden con el árbol real del repositorio están **DESACTUALIZADOS** y NO son evidencia de implementación:
>
> - **`apps/web` productiva: NO EXISTE** (carpeta vacía; `apps/` solo tiene `api` y `mobile`). El material web es un prototipo estático HTML/CSS en `design/prototypes/web/` (MOCK visual, sin JS/API/auth/build).
> - **Panel inversionista productivo: NO EXISTE.** El material web actual es un prototipo estático HTML/CSS en `design/prototypes/web/`.
> - **Bot Telegram (cobrador/inversionista): NO EXISTE** (`apps/telegram-bot/` no está en el árbol).
> - **Bot en móvil: PROHIBIDO.** Cualquier bot futuro es exclusivamente administrativo.
> - **PowerSync: NO EXISTE.** La sincronización offline usa SQLite + sync_queue + capa propia. `flutter pub deps` confirma cero dependencia de PowerSync.
> - **Autenticación por sesión: NO EXISTEN** en el hardening. La auth productiva es JWT ES256 + AndroidKeyStore + challenge-response.
> - **master (486d08b) NO contiene el hardening B1-B7.** Todo el trabajo de auth/sync productivo vive en `hardening/b1-b7-audit`.
>
> **Estado oficial (2026-08-11 verificado sobre `c0a3a9c`):**
> - Backend financiero: **PASS / implementado**
> - Hoja Viva: **implementada y preservada**
> - B1-B7 hardening: **PASS**
> - Auth productivo (JWT ES256 + AndroidKeyStore + challenge-response): **PASS**
> - Bootstrap single-route: **PASS**
> - Mobile auth bridge: **PASS**
> - S0 session maintenance: **PASS**
> - S1 route isolation: **PASS**
> - S2 pull servidor→móvil: **PASS**
> - S3 outbox móvil→servidor: **✅ PASS / IMPLEMENTADO**
> - Web productiva: **PENDIENTE** (`apps/web/` vacío)
> - Prototipo web: **existente, NO productivo**
> - Bot administrativo: **FUTURO**
> - Bot en móvil: **NO FORMA PARTE DEL PRODUCTO**
>
> > **Ejecución local de esta reconciliación (2026-08-11):** no equivale a GitHub Actions salvo el workflow `ui-gate.yml` que existe explícitamente. Ver [TESTING.md](TESTING.md) para comandos reproducibles.

---

## Resumen ejecutivo

| Campo | Valor |
|---|---|
| **Estado general** | M0-M3 completos · M3.2-M3.5 históricas no implementadas · B1-B7 hardening PASS · S0-S3 sync completo |
| **Hito actual** | S3 outbox push/ACK/retry/conflictos (IMPLEMENTADO)
| **Progreso total** | M0: 22/22 ✅ · M1: 8/8 ✅ · M2: 6/6 ✅ · M3 base: 1/1 ✅ (M3.2-M3.5 históricas, no implementadas en árbol actual) · B1-B7: ✅ |
| **Tests pasando (backend, SQLite)** | 262 passed, 7 skipped (269 funciones) |
| **Tests pasando (mobile)** | 175 passing |
| **Tests PG concurrency** | Pendientes (requieren scratch DB: `cobro_scratch_b6_pg` + `ALLOW_PG_TRUNCATE=1`) |
| **PostgreSQL** | Corriendo (cobro-postgres, Docker, puerto 7103) |
| **Alembic** | `m7_desafio_auth` (head); `alembic check` limpio |
| **ruff** | 97 errores en `src/` (deuda conocida — no limpiado en hardening) |
| **flutter analyze** | 14 infos preexistentes (migration_v5/v7) / 0 nuevos |
| **UI Gate CI** | PASS (GitHub Actions `ui-gate.yml`) |
| **Backend CI** | ⛔ NO EXISTE |
| **Documento maestro** | `docs/DOCUMENTO-MAESTRO-Plataforma-Cobro-Colombia-v1.3-CERRADO.md` + `DAILY-SYSTEM-ARCHIVO-MAESTRO-CONTINUIDAD-OPENCODE.md` |

### Estado de bloques

| Estado | Bloque |
|---|---|
| ✅ PASS | Backend financiero (M0-M2) |
| ✅ PASS | Hoja Viva y pagos |
| ✅ PASS | B1-B7 hardening (auth, device, activation, bootstrap) |
| ✅ PASS | JWT ES256 (fail-closed, claims congeladas) |
| ✅ PASS | AndroidKeyStore EC P-256 no exportable |
| ✅ PASS | Bootstrap single-route (daily-v1 / daily-auth-v1) |
| ✅ PASS | Mobile auth bridge (`lib/auth/`) |
| ✅ PASS | S0 — session maintenance (renovación antes de expirar) |
| ✅ PASS | S1 — route isolation (scope server-side; cliente no elige ruta) |
| ✅ PASS | S2 — pull servidor→móvil + persistencia SQLite (UPSERT por PK) |
| ✅ PASS | S3 — outbox móvil→servidor (push / ACK / retry / conflictos) |
| ⏳ PENDING | Verificado en dispositivo físico |
| ⏳ PENDIENTE | M4: Importación OCR (`ocr_service.py` no existe) |
| ⏳ PENDIENTE | M5: Score, chatbot, inteligencia |
| ⏳ PENDIENTE | M6: Producción y despliegue |
| ⛔ NO EXISTE | Bot Telegram (histórico, no implementado) |
| ⛔ NO EXISTE | Panel inversionista productivo (solo MOCK web) |
| ⛔ PROHIBIDO | Bot en móvil |
| ⛔ NO EXISTE | PowerSync (no es la arquitectura de sync) |
| ⛔ NO EXISTE | Auth por sesión (es JWT ES256) |

---

## Hito M0 — Fundación ejecutable ✅

**Estado:** COMPLETADO
**Progreso:** 22/22 (100%)

### Entregables

| # | Requisito | Estado | Commit |
|---|---|---|---|
| M0.1 | Repo público creado | ✅ | 90493db |
| M0.2 | AGENTS.md configurado | ✅ | 90493db |
| M0.3 | Protocolo Engram | ✅ | 90493db |
| M0.4 | Protocolo Graphify | ✅ | 61c2b9a |
| M0.5 | Infraestructura Docker | ✅ | e5af682 |
| M0.6 | Backend FastAPI | ✅ | e5af682 |
| M0.7 | Database layer | ✅ | e5af682 |
| M0.8 | Modelos SQLAlchemy (9 tablas) | ✅ | e5af682 |
| M0.9 | Schemas Pydantic | ✅ | e5af682 |
| M0.10 | Migration Alembic init | ✅ | e5af682 |
| M0.11-16 | Routes (6 módulos) | ✅ | e5af682 |
| M0.17 | Services: calculation_service | ✅ | e5af682 |
| M0.18 | Tests: calculaciones (12/12) | ✅ | e5af682 |
| M0.19 | Tests: API (16/16) | ✅ | 65c90f8 |
| M0.20 | Health endpoint | ✅ | 65c90f8 |
| M0.21 | Nombre normalizado | ✅ | f1ece01 |
| M0.22 | Documento maestro cerrado | ✅ | 724a644 |

---

## Hito M1 — Hoja viva y pagos ✅

**Estado:** COMPLETADO
**Progreso:** 8/8 (100%)

### Entregables

| # | Requisito | Estado | Commit |
|---|---|---|---|
| M1.1 | Calcular crédito (cuota × días) | ✅ | e2d8e37 |
| M1.2 | Calcular caja (asignar pagos) | ✅ | e2d8e37 |
| M1.3 | Hoja viva del día | ✅ | e2d8e37 |
| M1.4 | Registrar pago parcial | ✅ | e2d8e37 |
| M1.5 | Reversar pago | ✅ | e2d8e37 |
| M1.6 | Historial de pagos | ✅ | e2d8e37 |
| M1.7 | Cálculo de pico y residuo | ✅ | 965e0da |
| M1.8 | Renegociación básica | ✅ | 965e0da |

---

## Hito M2 — Jornada, caja y TERMINAR JORNADA ✅ (GATE FINAL)

**Estado:** COMPLETADO
**Progreso:** 6/6 (100%)

### Entregables

| # | Requisito | Estado | Commit |
|---|---|---|---|
| M2.1 | Iniciar jornada | ✅ | 485671e |
| M2.2 | Cerrar jornada | ✅ | 485671e |
| M2.3 | Total recaudado por jornada | ✅ | 3f59bd3 |
| M2.4 | Movimientos de caja | ✅ | 3f59bd3 |
| M2.5 | Reporte de jornada | ✅ | 86779e8 |
| M2.6 | Anular jornada | ✅ | 2826590 |

### Notas M2
- Una jornada solo puede cerrar si todas las cuotas del día están cubiertas o marcadas como impagas
- El pico (abono % cuota) se registra como abono a la siguiente cuota
- Idempotencia obligatoria en apertura de jornada
- Hash reproducible de snapshot de jornada
- Migrations: init → m2_apertura_idempotency → m2_jornada_caja → head
- **M2 Gate Final:** 138 tests passing, alembic head = m3_dispositivo, PostgreSQL applied

---

## Hito M3 — Suscripción / límites por plan ✅ · M3.2-M3.5 históricos no implementados

**Estado:** COMPLETADO (suscripciones) · **DESACTUALIZADO** (telegram/panel web — ver nota de reconciliación arriba)

### Entregables

| # | Requisito | Estado | Commit |
|---|---|---|---|
| M3.1 | Planes y suscripciones | ✅ | 871d1de |
| M3.2 | Bot Telegram (cobrador) | ⚠️ DESACTUALIZADO — no existe en el árbol real | 871d1de |
| M3.3 | Bot Telegram (inversionista) | ⚠️ DESACTUALIZADO — no existe en el árbol real | 871d1de |
| M3.4 | Panel inversionista (web) | ⚠️ DESACTUALIZADO — `apps/web` vacía; solo prototipo estático | 871d1de |
| M3.5 | Reporte diario automático | ⚠️ DESACTUALIZADO — no existe en el árbol real | 871d1de |
| M3.6 | Límite de rutas por plan | ✅ | e44b09e |

### Notas M3
- Plan free: 1 ruta, 100 clientes
- Plan básico: 5 rutas, 500 clientes
- Plan pro: rutas ilimitadas, clientes ilimitados
- M3.6.x: Flutter Offline Alpha + Visual Alpha Premium
- M3.6.6: Domain model unification — JornadaGuard, atomic payments, typed exceptions

---

## Historial de Sesiones

### Sesión 2026-07-28 (1) — Configuración inicial
- Init repo, AGENTS.md, Engram protocol
- Commit: 90493db

### Sesión 2026-07-28 (2) — Graphify setup
- Graphify audit, protocol, opencode.json
- Commit: 61c2b9a

### Sesión 2026-07-28 (3) — Documentación de plan
- Master doc, IMPLEMENTATION-PLAN.md, STATUS.md
- Commit: ff889a8

### Sesión 2026-07-28 (4) — Recuperación de código
- Import M0 backend from cobro-colombia (30 files, 18/28 passing)
- Commit: e5af682

### Sesión 2026-07-28 (5) — Corrección de tests
- 10 API test fixes → 28/28 passing
- Commit: 65c90f8

### Sesión 2026-07-28 (6) — Documento maestro cerrado
- DOCUMENTO-MAESTRO-Plataforma-Cobro-Colombia-v1.3-CERRADO.md guardado
- Commit: 724a644

### Sesión 2026-07-31 — M2 gate final + ruff linting
- 138 tests passing (M0-M3 all complete)
- Alembic migrations applied to PostgreSQL (head = m3_dispositivo)
- ruff --fix: 130 UP045 auto-fixed, 0 errors
- STATUS.md updated with M2 gate final evidence
- Commit: b6d48bb

---

## Archivos por tipo

| Tipo | Cantidad | Estado |
|---|---|---|
| Código Python | 34 | Normalizado (ruff clean) |
| Tests | 269 funciones backend (262 passed + 7 skip SQLite) / 175 mobile | Normalizado |
| Migraciones | 4 | init → m2_apertura → m2_jornada → m3_dispositivo |
| Infraestructura | 3 | docker-compose + init.sql + .env.example |
| Documentación | 8 | AGENTS.md, README, docs/*.md, ADR |
| Configuración | 3 | .gitignore, opencode.json, requirements.txt |

---

## Desviaciones

| # | Desviación | Impacto | Estado |
|---|---|---|---|
| 1 | Nombres heredados en infraestructura (cobro-postgres) | Bajo | ADR creado, migración pendiente |
| 2 | CORS restrictivo listo para desarrollo | Bajo | Corregido |
| 3 | Password en docker-compose (ya removido) | Resuelto | Usa variables de entorno |
| 4 | Rama master (no main) | Bajo | Mantener |

---

## Próximos pasos

1. **M4** — Importación OCR: `ocr_service.py` no existe aún (pendiente).
2. **M5** — Score, chatbot, inteligencia: pendiente.
3. **M6** — Producción y despliegue: pendiente.
4. **Verificado en dispositivo físico**: PENDING (solo emulador API 35).
5. **CI backend**: crear workflow de GitHub Actions para pytest + alembic check.
6. **ruff**: limpiar 97 errores en `src/` (deuda conocida en hardening).
