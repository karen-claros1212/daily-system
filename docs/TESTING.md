# Testing — Daily System

**Documento:** Estado vivo  
**Última actualización:** 2026-08-15  
**Base verificada:** `product/web-premium-v1` @ `bbb3e102`

---

## Último baseline verificado

Ejecución local en `/home/jesus/proyectos/daily-system` (checkout operativo canónico). Fecha: 2026-08-15.

| Gate | Resultado | Comando |
|---|---|---|
| Flutter analyze | 14 infos preexistentes (migraciones congeladas v5/v7) / 0 nuevos | `cd apps/mobile && flutter analyze` |
| Flutter test (mobile) | **177/177 passing** | `cd apps/mobile && flutter test` |
| Backend pytest (SQLite) | **367 passed, 8 skipped** | `cd apps/api && python3 -m pytest src/tests/ -q` |
| Ruff (backend) | **127 errors** (deuda conocida) | `cd apps/api && ruff check src/` |
| Alembic | head = `m8_negocio_nit` · upgrade + current en Backend CI (PG) | `cd apps/api && python3 -m alembic heads` |
| Web — api:check / lint / typecheck / build | PASS | `cd apps/web && npm run api:check && npm run lint && npm run typecheck && npm run build` |
| Web E2E mock (Playwright + axe) | **107 passing** | `cd apps/web && npm test` (mock config) |
| Web E2E real (FastAPI + PostgreSQL) | **26 passing** | `cd apps/web && npm test` (real config) |
| npm audit (web) | 0 vulnerabilidades | `cd apps/web && npm audit` |
| Backend CI | ✅ PASS (GitHub Actions) | `.github/workflows/backend-ci.yml` |
| Web CI | ✅ PASS 3/3 (GitHub Actions) | `.github/workflows/web-ci.yml` |
| UI Gate CI | ✅ PASS (GitHub Actions) | `scripts/ci/ui_gate.sh` |

> **Aclaración:** los tests PG concurrency (skips en pytest) requieren una DB scratch con nombre `test`/`scratch` + `DAILY_ENV=test` + `ALLOW_PG_TRUNCATE=1`. El gate de concurrencia NIT se ejecuta en Backend CI sobre PostgreSQL (`test_onboarding.py::TestNitConcurrentePostgres`).

---

## 1. Mobile test suites

```
apps/mobile/
├── test/
│   ├── logo_golden_test.dart          # Golden: logo
│   ├── login_semantics_test.dart      # Semantics: login
│   ├── cobros_nav_test.dart           # Widget: navegación cobros
│   ├── paridad_b5_test.dart           # Paridad backend-mobile (14 casos)
│   ├── screen_golden_test.dart        # Goldens: 31 generados (phone/tablet × light/dark)
│   ├── semantics_test.dart            # Semantics: 37 widget tests
│   ├── widget_test.dart               # Widget básico
│   ├── generator_test.dart            # Generador de tokens (incluido en flutter test)
│   ├── fixture_test.dart              # Fixtures y helpers
│   ├── auth/                          # JCS vector (byte-exacto vs backend)
│   ├── sync/                          # SyncRepository + push_orchestrator (S3-S5)
│   ├── goldens/
│   └── helpers/
├── integration_test/
│   └── jornada_cierre_test.dart       # Integration: cierre de jornada
└── test/  (total 18+ archivos .dart)
```

### Categorías

| Categoría | Archivos | Qué valida |
|---|---|---|
| Golden | `screen_golden_test.dart`, `logo_golden_test.dart` | Render visual (31 goldens) |
| Semantics | `semantics_test.dart`, `login_semantics_test.dart` | Accesibilidad (37 widgets) |
| Widget | `cobros_nav_test.dart`, `widget_test.dart` | Widget tests |
| Paridad | `paridad_b5_test.dart` | Backend==Mobile resultados (14 casos) |
| Auth | `test/auth/` | Vector JCS byte-exacto vs backend Python |
| Sync S0-S2 | `test/sync/` | SyncRepository: upsert, pendientes, CLOSED_LOCAL_PENDING_SYNC |
| Sync S3-S5 | `test/sync/` (`push_orchestrator_test.dart`) | Outbox push/ACK/retry/conflictos, R1→R2, dependencias |
| Integration | `integration_test/jornada_cierre_test.dart` | Cierre de jornada end-to-end (SQLite) |
| Generator | `generator_test.dart` | Tokens determinísticos (incluido en flutter test) |

### UI Gate (`scripts/ci/ui_gate.sh`) + `ui-gate.yml`
1. `dart run tool/generate_design_tokens.dart --check` — tokens determinísticos
2. `flutter analyze` — estricto, sin flags (14 infos preexistentes tolerados, 0 nuevos)
3. `flutter test` — todos los tests (177)

**CI en GitHub Actions:** `ui-gate.yml` (mobile estricto). Backend y Web tienen sus propios workflows (ver §5).

---

## 2. Backend test suites

```
apps/api/src/tests/
├── conftest.py                     # Fixtures: test DB (SQLite default / PG con scratch)
├── test_api.py                     # Health, modelos base
├── test_calculations.py            # Calculation service (12 tests)
├── test_m1.py / test_m1_advanced / test_m1_gate  # Hoja viva + pagos
├── test_m2.py                      # Jornada, caja, cierre
├── test_m3.py                      # Suscripción / límites por plan
├── test_m4.py                      # Multirruta (9 tests)
├── test_m5_activacion.py           # Activación (challenge-response, JCS, casos A-D)
├── test_m6_auth.py                 # JWT ES256 (alg confusion, binding, renewal)
├── test_m6_pg_concurrency.py       # Concurrency PG (skip en SQLite)
├── test_m6_sync.py                 # Sync dataset + route isolation + reversal
├── test_b5_paridad.py              # Paridad financiera backend (14 casos)
├── test_s5_conflict_service.py     # S5: 6 verificadores server-authoritative (48 tests)
├── test_onboarding.py              # Onboarding + NIT concurrencia PG
└── test_g3_truncate_guard.py       # G3 TRUNCATE protection
```

### Categorías

| Categoría | Archivo | Qué valida |
|---|---|---|
| API base | `test_api.py` | Health, modelos, esquema |
| Cálculos | `test_calculations.py` | Cuota, caja, pico, residuo |
| Paridad | `test_m1_gate.py`, `test_b5_paridad.py` | Paridad financiera backend–mobile |
| Multirruta | `test_m4.py` | 9 tests: jornadas simultáneas, crosstalk, carry |
| Activación | `test_m5_activacion.py` | Challenge-response, JCS, casos A-D idempotencia |
| Auth | `test_m6_auth.py` | JWT ES256 fail-closed, claims, renewal |
| Sync | `test_m6_sync.py` | Dataset scope, reversal_of_payment_id, route isolation |
| Conflictos (S5) | `test_s5_conflict_service.py` | 6 verificadores: pago, movimiento, jornada, apertura, reversal, ruta (48 tests) |
| Onboarding | `test_onboarding.py` | Registro de negocio + NIT 201/409 concurrente (PG) |
| Concurrency | `test_m6_pg_concurrency.py` | PG-specific (skip en SQLite) |

### Base de datos

| Tipo | Uso | Cómo |
|---|---|---|
| SQLite (in-memory) | Default tests backend + mobile | `sqlite:///:memory:` (conftest) |
| PostgreSQL | Prod + tests PG concurrency | `cobro-postgres`, puerto 7103, DB `cobro`, user `cobro` |
| PG CI (Backend CI) | Alembic + pytest + NIT gate | service `postgres:16-alpine`, DB `daily_backend_ci_test` |
| PG CI (Web CI) | E2E real + fixtures deterministas | service `postgres:16-alpine`, DB `daily_web_e2e_test` |
| PG scratch | Tests concurrency + migración reversible | `cobro_scratch_b6_pg` (nombre debe contener `scratch` o `test`) |

### TRUNCATE guard (G3)

`test_g3_truncate_guard.py` verifica que los tests **nunca** hagan TRUNCATE sobre la base productiva. El conftest exige:
- `DAILY_ENV=test`
- DB name contiene `test` o `scratch`
- `ALLOW_PG_TRUNCATE=1`

---

## 3. Migrations

| Migration | Propósito |
|---|---|
| `init` | Tablas base, CheckConstraint jornada_estado |
| `m2_apertura_idempotency` | Idempotencia apertura jornada |
| `m2_jornada_caja` | Caja, snapshot, hash |
| `m3_dispositivo` | Dispositivo con estado/public_key (legacy) |
| `m4_ruta_cobrador_fk` | FK ruta→cobrador (S4) |
| `m5_dispositivo_activacion` | Activación: codigo, intento, challenge-response |
| `m6_dispositivo_version` | Versión de asignación de dispositivo |
| `m7_desafio_auth` | daily-auth-v1: challenge/auth device |
| `m8_negocio_nit` | **head** — invariante NIT única por negocio (2026-08-14) |

Head: `m8_negocio_nit`. `alembic upgrade head` + `alembic current` corren en Backend CI sobre PostgreSQL. Reversible: upgrade → downgrade → re-upgrade verificado en scratch DB.

---

## 4. Web test suites (Playwright)

```
apps/web/e2e/
├── onboarding.spec.ts        # Registro de negocio (onboarding)
├── auth.spec.ts              # Login / logout
├── auth-contract.spec.ts     # Contrato de auth (mock)
├── login-surfaces.spec.ts    # Superficies de login por rol
├── rbac-roles.spec.ts        # RBAC por rol (mock)
├── multi-role-device-flow.spec.ts
├── dashboard.spec.ts         # Dashboard financiero
├── routes.spec.ts            # Rutas
├── caja.spec.ts              # Caja / jornada
├── reportes.spec.ts          # Reportes
├── dispositivos.spec.ts      # Dispositivos
├── suscripcion.spec.ts       # Suscripción
├── session-renewal.spec.ts   # Renovación de sesión
├── pages.a11y.spec.ts        # a11y axe por página (mock)
├── real-contract.spec.ts     # Contrato real (FastAPI+PG)
├── real-onboarding.spec.ts   # Onboarding real
├── real-rbac.spec.ts         # RBAC real
├── real-dispositivos.spec.ts # Dispositivos real
└── real-integration.spec.ts  # Integración real
```

| Config | Base | Qué cubre |
|---|---|---|
| mock | `playwright.config.ts` (web mock en :8100) | 107 tests: surfaces, RBAC, rutas, caja, reportes, dispositivos, suscripción, session, a11y axe |
| real | `playwright.config.real.ts` (FastAPI + PostgreSQL en :8001) | 26 tests: contrato, onboarding, RBAC, dispositivos, integración real |

Clientes TS tipados generados desde `openapi.json` (`src/lib/api/generated/`) — `npm run api:check` detecta drift de contrato.

---

## 5. CI — GitHub Actions

| Workflow | Jobs | Qué corre |
|---|---|---|
| `backend-ci.yml` | `backend-test` | alembic upgrade/current + `pytest src/tests/ -q` + gate concurrencia NIT (PG `daily_backend_ci_test`) |
| `web-ci.yml` | `web-static` · `web-e2e-mock` · `web-real-integration` | api:check + lint + typecheck + build · Playwright mock + axe · Playwright real contra FastAPI+Postgres |
| `ui-gate.yml` | — | `scripts/ci/ui_gate.sh` (tokens + flutter analyze + flutter test) |

Triggers: push a `master` / `hardening/**` / `product/**` y PR a `master`.

---

## 6. Deuda conocida

| Item | Estado |
|---|---|
| ruff | 127 errores en `src/` (deuda no limpiada en hardening — principalmente imports no usados) |
| flutter analyze | 14 infos preexistentes en migraciones congeladas `migration_v5.dart` / `migration_v7.dart` — no tocar |
| Dispositivo físico | No verificado (solo emulador API 35) |
| npm audit | ✅ 0 vulnerabilidades (Next 16.3.1, sharp, postcss) — local; no es step de CI |
| PostgreSQL S3 (local) | NOT RUN — scratch PostgreSQL no disponible localmente (cubierto por CI PG) |
