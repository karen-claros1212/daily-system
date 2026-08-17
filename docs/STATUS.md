# STATUS — Daily System

**Proyecto:** daily-system
**Última actualización:** 2026-08-16
**Ruta de trabajo verificada (local):** `/home/jesus/proyectos/daily-system`
**Rama de trabajo:** `product/web-premium-v1`
**HEAD operativo:** dinámico — `git rev-parse HEAD` (Git es autoridad)
**Baseline funcional certificado:** `bbb3e1024cd0380cf48288c486565a4411c602c3`
**Commit fuente de evidencia visual responsive:** `33b13428d5b9364ae6d8ed39d2875ee99b33d2f7`
**Repo:** https://github.com/karen-claros1212/daily-system

> ## ⚠️ NOTA DE RECONCILIACIÓN (2026-08-15)
>
> Reconciliación documental: el repositorio refleja ahora el estado real del producto.
> - **Panel web administrativo: production-grade** — `apps/web/` es una aplicación Next.js 16
>   (onboarding, dispositivos, suscripción, dashboard, rutas, caja, reportes). El prototipo
>   estático MOCK vive en `design/prototypes/web/` como **histórico**.
> - **Backend CI: EXISTE** (`backend-ci.yml`) — alembic upgrade/current + pytest + gate de
>   concurrencia NIT sobre PostgreSQL.
> - **Web CI: EXISTE** (`web-ci.yml`) — 3 jobs: static (api:check/lint/typecheck/build),
>   E2E mock (Playwright + axe), E2E real (FastAPI + PostgreSQL).
> - **UI Gate: EXISTE** (`ui-gate.yml`) — flutter analyze + flutter test estrictos.
> - **S0-S5: PASS** — session, ruta, pull, outbox, reasignación R1→R2, conflictos.
> - **Bot en móvil: PROHIBIDO.** Cualquier bot futuro es exclusivamente administrativo.
> - **PowerSync: NO EXISTE** — la sincronización offline usa SQLite + sync_queue + capa propia.
> - `master` (`486d08b`) es una rama legacy sin hardening; todo el trabajo vive en `product/web-premium-v1`.

---

## Resumen ejecutivo

| Campo | Valor |
|---|---|
| **Estado general** | Etapa 1 ✅ · Etapa 2 ✅ · Etapa 3 EN PROGRESO · Etapa 4 ⏳ · Etapa 5 ⏳ |
| **Hito actual** | Web Premium W0-W4 ✅ (W5 pendiente) — ver `WEB-PREMIUM-EXECUTION-LEDGER.md` |
| **Tests backend (SQLite)** | 472 passed, 9 skipped |
| **Tests mobile** | 177/177 passing (frozen — no ejecutar por rutina W) |
| **Web E2E (local, Next 16)** | mock 175 passing (incl. a11y axe) + real 34 passing |
| **flutter analyze** | 14 infos preexistentes (migraciones congeladas v5/v7) / 0 nuevos |
| **ruff (deuda conocida)** | 127 errores en `src/` — no limpiado en hardening |
| **Alembic** | `m10_audit_documento` (head) · upgrade + current verificados en Backend CI (PG) |
| **npm audit (web)** | 0 vulnerabilidades |
| **Backend CI** | ✅ PASS |
| **Web CI** | ✅ PASS (3/3 jobs) |
| **UI Gate CI** | ✅ PASS |
| **PostgreSQL** | Docker (`postgres` servicio CI; local `cobro-postgres`, puerto 7103) |

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
| ✅ PASS | S4 — reasignación de ruta R1→R2 (ruta_id_origen inmutable) + orquestación sync |
| ✅ PASS | S5 — `conflict_service.py` (verificadores server-authoritative de conflicto) |
| ✅ PASS | Web Premium — panel administrativo production-grade (Next.js 16, preparada para producción, NO desplegada) |
| ✅ PASS | Migración Next.js 16 security baseline (CI 3/3) |
| ⏳ PENDING | Verificado en dispositivo físico |
| ⏳ PENDIENTE | Etapa 4: Importación OCR (`ocr_service.py` no existe) |
| ⏳ PENDIENTE | Etapa 5: Score, chatbot, inteligencia |
| ⏳ PENDIENTE | Producción / deploy (implementación production-grade existe; NO desplegada todavía) |
| ⏳ FUTURO | Bot administrativo (exclusivamente administrativo) |
| ⛔ NO EXISTE | Bot Telegram (histórico, no implementado como bloque original) |
| ⛔ PROHIBIDO | Bot en móvil |
| ⛔ NO EXISTE | PowerSync (no es la arquitectura de sync) |

---

## Estado canónico del producto

### Aplicación cobrador — Android/Flutter (offline-first) — 🧊 FROZEN

> **Mobile Contract Freeze (W0-W14):** `apps/mobile/**` = READ-ONLY.
> Android ya está terminado y operativo. El frente activo es Web Premium.
> Gate por cada W: `git diff --name-only <baseline>..HEAD -- apps/mobile/` → VACÍO.

| Área | Estado |
|---|---|
| Aplicación cobrador offline-first | ✅ Implementada (SQLite local, operaciones offline) |
| Auth AndroidKeyStore P-256 + JWT ES256 | ✅ Implementado (clave no exportable, SHA256withECDSA) |
| Flujo challenge / canje / bootstrap | ✅ Implementado (daily-v1 / daily-auth-v1, JCS RFC 8785) |
| Una única ruta activa derivada por servidor | ✅ Implementada (el cliente no elige ruta) |
| Hoja Viva | ✅ Implementada y preservada |
| Pagos y reversiones | ✅ Implementados (idempotencia + 409 on mismatch) |
| Jornada y caja | ✅ Implementadas (apertura, movimientos, cierre, hash reproducible) |
| Movimientos e historial | ✅ Implementados |
| PDF de cierre de jornada | ✅ Implementado |
| SQLite (migraciones versionadas v2..v7) | ✅ Implementado (v5/v7 congeladas — fuente de las 14 infos de analyzer) |
| Sync S0-S5 | ✅ PASS |
| Suite de tests | ✅ 177/177 (último baseline aceptado) |
| Analyzer | ✅ 14 infos históricos en migraciones congeladas / 0 nuevos |
| Bot en móvil | ⛔ PROHIBIDO — no forma parte del producto |

### Panel web administrativo — Web Premium (Next.js 16, production-grade / preparada para producción)

| Área | Estado |
|---|---|
| Login (sesión httpOnly `daily_admin_token`) | ✅ Implementado (identidad solo vía `/api/auth/me`) |
| Onboarding (registro de negocio) | ✅ Implementado (`/registro`) |
| Dashboard financiero | ✅ Implementado (`/dashboard`, despacha superficie por rol) |
| Rutas | ✅ Implementado (`/routes`, `/routes/[id]` — W4: CRUD + reasignación S4) |
| Caja | ✅ Implementado (`/caja`) |
| Reportes | ✅ Implementado (`/reportes`) |
| Dispositivos | ✅ Implementado (`/dispositivos`) |
| Suscripción | ✅ Implementado (`/suscripcion`) |
| RBAC por capacidades (COBRADOR / INVERSIONISTA / ADMINISTRADOR) | ✅ Implementado (server-side) |
| E2E Playwright (mock + real) + a11y axe | ✅ PASS (mock 175 / real 34) |
| `openapi-typescript` cliente generado | ✅ Implementado (`src/lib/api/generated/`, `npm run api:check`) |

### Backend — FastAPI

| Área | Estado |
|---|---|
| Modelos, schemas, rutas, servicios | ✅ Implementado |
| Alembic | ✅ head `m8_negocio_nit` (init → m2..m8) |
| Invariante NIT por negocio | ✅ En BD (`m8_negocio_nit`, 2026-08-14) + gate concurrencia 201/409 en CI |
| `conflict_service.py` (S5) | ✅ 6 verificadores server-authoritative |
| Tests | ✅ 367 passed, 8 skipped (SQLite) |
| ruff | ⚠️ 127 errores deuda conocida (no limpiado en hardening) |

### CI/CD (GitHub Actions)

| Workflow | Jobs | Estado |
|---|---|---|
| `backend-ci.yml` | API tests + Alembic check (PG) + NIT concurrency gate | ✅ PASS |
| `web-ci.yml` | `web-static` · `web-e2e-mock` · `web-real-integration` | ✅ PASS 3/3 |
| `ui-gate.yml` | flutter analyze + flutter test (estricto) | ✅ PASS (trigger: master; mobile baseline aceptado: 177/177, 14 infos históricos / 0 errores) |

---

## Hitos M0-M3 (históricos — completados)

Las secciones siguientes se conservan como historia de ejecución. El estado vigente está en
"Estado canónico del producto" arriba.

### Hito M0 — Fundación ejecutable ✅ (22/22)

| # | Requisito | Commit |
|---|---|---|
| M0.1-M0.22 | Repo, AGENTS.md, protocolos, infraestructura, backend FastAPI, modelos, migraciones, routes, services, tests, health, naming, documento maestro | `90493db` … `724a644` |

### Hito M1 — Hoja viva y pagos ✅ (8/8)

| # | Requisito | Commit |
|---|---|---|
| M1.1-M1.8 | Crédito, caja, hoja viva, pago parcial, reversión, historial, pico/residuo, renegociación | `e2d8e37` / `965e0da` |

### Hito M2 — Jornada, caja y TERMINAR JORNADA ✅ (6/6, GATE FINAL)

| # | Requisito | Commit |
|---|---|---|
| M2.1-M2.6 | Iniciar/cerrar jornada, total recaudado, movimientos, reporte, anular | `485671e` / `3f59bd3` / `86779e8` / `2826590` |

- Jornada solo cierra si todas las cuotas del día están cubiertas o marcadas impagas
- Pico (abono % cuota) se registra como abono a la siguiente cuota
- Idempotencia obligatoria en apertura; hash reproducible de snapshot
- **M2 Gate Final:** 138 tests passing, alembic head = m3_dispositivo, PostgreSQL applied

### Hito M3 — Suscripción / límites por plan ✅ · M3.2-M3.5 históricos

| # | Requisito | Estado |
|---|---|---|
| M3.1 | Planes y suscripciones | ✅ (`871d1de`) |
| M3.2-M3.3 | Bot Telegram (cobrador/inversionista) | ⚠️ no implementado como bloque original |
| M3.4 | Panel inversionista (web) | ✅ **reimplementado como Web Premium production-grade** |
| M3.5 | Reporte diario automático | ⚠️ no implementado |
| M3.6 | Límite de rutas por plan | ✅ (`e44b09e`) |

- Plan free: 1 ruta / 100 clientes · básico: 5 / 500 · pro: ilimitado

---

## Historial de Sesiones

### Sesiones 2026-07-28 — Configuración inicial (1-6)
- Init repo, AGENTS.md, protocolos Engram/Graphify, plan, import M0 backend, corrección de tests (28/28), documento maestro cerrado
- Commits: `90493db`, `61c2b9a`, `ff889a8`, `e5af682`, `65c90f8`, `724a644`

### Sesión 2026-07-31 — M2 gate final + ruff linting
- 138 tests passing (M0-M3), migraciones aplicadas (head m3_dispositivo), ruff --fix 130 UP045
- Commit: `b6d48bb`

### Bloques B1-B7 / S0-S5 — hardening y sync (2026-08-06 → 2026-08-14)
- B1-B7: JWT ES256, AndroidKeyStore, challenge-response, bootstrap productivo
- S0-S2: session, route isolation, pull+persist (baseline `c0a3a9c`)
- S3: outbox push/ACK/retry/conflictos
- S4: reasignación R1→R2 (`b75f2c4` … `327c7fd`)
- S5: `conflict_service.py` + 48 tests (`877f24d`)
- HARDENING FINAL ONBOARDING: invariante NIT `m8_negocio_nit` (2026-08-14)

### Bloques Web Premium + Migración Next.js 16 (2026-08-14 → 2026-08-15)
- Web Premium: panel administrativo production-grade (Next.js 16, RBAC, onboarding, dispositivos, suscripción, dashboard, rutas, caja, reportes)
- Migración Next.js 16 security baseline: `5d1205b` + `bbb3e102` (fix devIndicators) — CI 3/3 PASS
- Reconciliación documental 2026-08-15: este documento + archivo de históricos en `docs/historical/`

---

## Desviaciones

| # | Desviación | Impacto | Estado |
|---|---|---|---|
| 1 | Nombres heredados en infraestructura (cobro-postgres) | Bajo | ADR creado, migración pendiente |
| 2 | Rama master (no main) | Bajo | Mantener (legacy) |
| 3 | ruff: 127 errores en `src/` | Bajo (deuda) | No limpiado en hardening |
| 4 | flutter analyze: 14 infos en migraciones congeladas | Nulo | Preexistentes, no tocar |

---

## Próximos pasos

1. **Etapa 3 — completar pendientes:** Mini App inversionista, política de exposición del onboarding, recuperación del admin principal
2. **Etapa 4** — Importación OCR (`ocr_service.py` no existe aún; pendiente)
3. **Etapa 5** — Score, chatbot, inteligencia (pendiente)
4. **Producción / deploy** — pendiente (implementación production-grade ya existe, NO desplegada todavía)
5. **Verificado en dispositivo físico** — PENDING (solo emulador API 35)
6. **Bot administrativo futuro** — exclusivamente administrativo; NO bot en móvil
7. **ruff** — limpiar 127 errores en `src/` (deuda conocida)
