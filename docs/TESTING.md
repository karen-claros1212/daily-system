# Testing — Daily System

**Documento:** Estado vivo  
**Última actualización:** 2026-08-11  
**Base verificada:** `hardening/b1-b7-audit` @ `c0a3a9c`

---

## Último baseline verificado

Ejecución local en `/home/jesus/proyectos/daily-system` (checkout operativo canónico). Fecha: 2026-08-11.

| Gate | Resultado | Comando |
|---|---|---|
| Flutter analyze | No issues found | `cd apps/mobile && flutter analyze` |
| Flutter test (mobile) | **147 passing** | `cd apps/mobile && flutter test` |
| Backend pytest (SQLite) | **255 passed, 7 skipped** (257 funciones) | `cd apps/api/src && python3 -m pytest tests/ -q` |
| Ruff (backend) | **97 errors** (deuda conocida) | `cd apps/api && ruff check src/` |
| Alembic | head = m7_desafio_auth, clean | `python3 -m alembic check` |
| UI Gate CI | PASS (GitHub Actions) | `scripts/ci/ui_gate.sh` |
| Backend CI | ⛔ NO EXISTE | — |

> **Aclaración:** los tests PG concurrency (7 skips en pytest) requieren una DB scratch con nombre `test`/`scratch` + `DAILY_ENV=test` + `ALLOW_PG_TRUNCATE=1`. No se ejecutaron en este baseline. Ver §3.

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
│   ├── sync/                          # SyncRepository (upsert, pendientes, S2-H2)
│   ├── goldens/
│   └── helpers/
├── integration_test/
│   └── jornada_cierre_test.dart       # Integration: cierre de jornada
└── test/  (total 18 archivos .dart)
```

### Categorías

| Categoría | Archivos | Qué valida |
|---|---|---|
| Golden | `screen_golden_test.dart`, `logo_golden_test.dart` | Render visual (31 goldens) |
| Semantics | `semantics_test.dart`, `login_semantics_test.dart` | Accesibilidad (37 widgets) |
| Widget | `cobros_nav_test.dart`, `widget_test.dart` | Widget tests |
| Paridad | `paridad_b5_test.dart` | Backend==Mobile resultados (14 casos) |
| Auth | `test/auth/` | Vector JCS byte-exacto vs backend Python |
| Sync | `test/sync/` | SyncRepository: upsert, pendientes, CLOSED_LOCAL_PENDING_SYNC, S2-H2 |
| Integration | `integration_test/jornada_cierre_test.dart` | Cierre de jornada end-to-end (SQLite) |
| Generator | `generator_test.dart` | Tokens determinísticos (incluido en flutter test) |

### UI Gate (`scripts/ci/ui_gate.sh`)
1. `dart run tool/generate_design_tokens.dart --check` — tokens determinísticos
2. `flutter analyze` — estricto, sin flags
3. `flutter test` — todos los tests

**CI en GitHub Actions:** único workflow `ui-gate.yml` (solo mobile). Backend CI: **no existe.**

---

## 2. Backend test suites

```
apps/api/src/tests/
├── conftest.py                     # Fixtures: test DB (SQLite default / PG con scratch)
├── test_api.py                     # Health, modelos base (16 tests)
├── test_calculations.py          # Calculation service (12 tests)
├── test_m1.py / test_m1_advanced / test_m1_gate  # Hoja viva + pagos
├── test_m2.py                      # Jornada, caja, cierre
├── test_m3.py                      # Dispositivo
├── test_m4.py                      # Multirruta (9 tests)
├── test_m5_activacion.py          # Activación (19 tests + 1 skip PG)
├── test_m6_auth.py                # JWT ES256 (alg confusion, binding, renewal)
├── test_m6_pg_concurrency.py    # Concurrency PG (skip en SQLite)
├── test_m6_sync.py               # Sync dataset + route isolation + reversal
└── test_g3_truncate_guard.py     # G3 TRUNCATE protection
```

### Categorías

| Categoría | Archivo | Qué valida |
|---|---|---|
| API base | `test_api.py` | Health, modelos, esquema |
| Cálculos | `test_calculations.py` | Cuota, caja, pico, residuo |
| Paridad | `test_m1_gate.py` | Backend–mobile parity |
| Multirruta | `test_m4.py` | 9 tests: jornadas simultáneas, crosstalk, carry |
| Activación | `test_m5_activacion.py` | Challenge-response, JCS, casos A-D idempotencia |
| Auth | `test_m6_auth.py` | JWT ES256 fail-closed, claims, renewal |
| Sync | `test_m6_sync.py` | Dataset scope, reversal_of_payment_id, route isolation |
| Concurrency | `test_m6_pg_concurrency.py` | PG-specific (skip en SQLite) |

### Base de datos

| Tipo | Uso | Cómo |
|---|---|---|
| SQLite (in-memory) | Default tests backend + mobile | `sqlite:///:memory:` (conftest) |
| PostgreSQL | Prod + tests PG concurrency | `cobro-postgres`, puerto 7103, DB `cobro`, user `cobro` |
| PG scratch | Tests concurrency + migración reversible | `cobro_scratch_b6_pg` (nombre debe contener `scratch` o `test`) |

### TRUNCATE guard (G3)

`test_g3_truncate_guard.py` verifica que los tests **nunca** hagan TRUNCATE sobre la base productiva `cobro`. El conftest exige:
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
| `m5_dispositivo_activacion` | Activación: codigo, intento, challenge-response |
| `m7_desafio_auth` | daily-auth-v1: challenge/auth device (head) |

`alembic check`: No new upgrade operations detected ✅

Alembic reversible: upgrade → downgrade → re-upgrade verificado en scratch DB ✅

---

## 4. Deuda conocida

| Item | Estado |
|---|---|
| ruff | 97 errores en `src/` (deuda no limpiada en hardening — principalmente imports no usados) |
| Backend CI | No hay workflow de pytest/alembic en GitHub Actions (solo `ui-gate.yml` para mobile) |
| S3 outbox | No implementado (push/ACK/retry/conflictos) |
| Dispositivo físico | No verificado (solo emulador API 35) |
| Web productivo | `apps/web/` vacío — solo prototipo MOCK |
| ruff | No se ejecuta en CI (no está en el ui-gate ni en ningún workflow) |