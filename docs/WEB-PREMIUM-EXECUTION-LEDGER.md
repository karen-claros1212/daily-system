# WEB PREMIUM — Execution Ledger

**Proyecto:** daily-system
**Rama:** `product/web-premium-v1`
**Última actualización:** 2026-08-16
**HEAD:** `d89f736` (W2 FINAL PASS — código certificado)

---

## Estado global

| Fase | Estado | Commit | Endpoints | Pruebas | CI | Decisiones | Blockers |
|---|---|---|---|---|---|---|---|
| **W0** | ✅ COMPLETADO | dac558d | BFF usuarios/audit | — | ✅ | Ledger creado | Ninguno |
| **W1** | ✅ FINAL PASS | 355cdb3 | Todos | 399 backend + 136 E2E mock + 41 a11y | ✅ PASS (ambos) | Git repair, BFF PATCH, m10, UI completa, PG migration gate real en CI | Ninguno |
| **W2** | ✅ FINAL PASS | d89f736 | Todos | 426 backend + 157 E2E mock + 22 a11y + 26 real | ✅ PASS (ambos) | Listado scoped COBRADOR, 360 DTO, real E2E en PG :5432 | Ninguno |
| **W3** | PENDIENTE | — | — | — | — | — | Depende de W2 |
| **W4** | PENDIENTE | — | — | — | — | — | Depende de W3 |
| **W5** | PENDIENTE | — | — | — | — | — | Depende de W4 |
| **W6** | PENDIENTE | — | — | — | — | — | Depende de W5 |
| **W7** | PENDIENTE | — | — | — | — | — | Depende de W6 |
| **W8** | PENDIENTE | — | — | — | — | — | Depende de W7 |
| **W9** | PENDIENTE | — | — | — | — | — | Depende de W8 |
| **W10** | PENDIENTE | — | — | — | — | — | Depende de W9 |
| **W11** | PENDIENTE | — | — | — | — | — | Depende de W10 |
| **W12** | PENDIENTE | — | — | — | — | — | Depende de W11 |
| **W13** | PENDIENTE | — | — | — | — | — | Depende de W12 |
| **W14** | PENDIENTE | — | — | — | — | — | Depende de W13 |

---

## W0 — Execution Ledger + Contratos + Fecha de Negocio

### Estado: ✅ COMPLETADO

#### W0.1 — Ledger (este archivo)
- [x] Ledger creado con fases W0-W14
- [x] Matriz de contratos inicial
- [x] Mobile Contract Freeze definido
- [x] Reglas anti-deuda listadas

#### W0.2 — Matriz de contratos

| Dominio | Backend | BFF | UI | Mutaciones | E2E | Estado |
|---|---:|---:|---:|---:|---:|---|
| Usuarios | auditar | auditar | no/parcial | auditar | auditar | W1 |
| Clientes | sí | sí | sí | sí | sí | W2 |
| Créditos | sí | no/parcial | no | sí | no | W3 |
| Rutas | sí | GET/parcial | parcial | backend sí | parcial | W4 |
| Jornadas | sí | sí | parcial | móvil/domain | parcial | verificado |
| Movimientos/Gastos | sí | auditar | no | sí | auditar | W5 |
| Reportes | básico | sí | básico | N/A | parcial | W7 |
| Inversionista | sí | sí | parcial | read-only | parcial | W9 |
| Auditoría | auditar | auditar | no | auditar | no | W1 |
| IA Providers | no | no | no | configuración | no | W10 |
| Assistant | no | no | no | read/prepare | no | W11 |
| Dispositivos | sí | sí | sí | sí | sí | CERRADO |
| Suscripción cliente | sí | sí | sí | read-only | sí | CERRADO |

#### W0.3 — Gate de fecha/zona horaria

**Regla:** La fecha de negocio la determina el backend. Para Colombia → `America/Bogota`.

**Búsqueda de autoridad de fecha:**

| Archivo | Patrón | Uso | Riesgo |
|---|---|---|---|
| `apps/api/src/` | `datetime.now()` / `date.today()` | backend | medio |
| `apps/api/src/services/` | `datetime` imports | servicios | bajo |
| `apps/api/src/routes/` | `datetime` imports | routes | bajo |
| `apps/api/src/models/` | `DateTime` columnas | modelos | bajo |
| `apps/web/src/` | `new Date()` | frontend | medio |
| `apps/mobile/lib/` | `DateTime` | mobile | bajo (ya tiene autoridad) |

**Reglas:**
- `apps/api/src/models/` usa `DateTime(timezone=True)` → SQLAlchemy maneza UTC.
- Backend: usar `datetime.now(timezone.utc)` o `datetime.now(pytz.timezone("America/Bogota"))`.
- Web: usar fecha del backend para agregados financieros; `new Date()` solo para UX.
- Mobile: autoridad de `jornada.fecha` ya certificada (S0-S5).
- No usar `date.today()` ni `new Date().toISOString().slice(0,10)` como autoridad financiera.

**Pruebas de borde pendientes (W7/W8):**
- 18:59 Colombia → qué día cuenta?
- 19:00 Colombia → cambio de día
- 23:59 → próximo día
- 00:00 → inicio de día
- Timestamps UTC de ambos días Colombia

**Estado:** Pendiente de implementación en W7/W8. W0 registra la regla.

#### W0.4 — Mobile Contract Freeze

**Protección:** `apps/mobile/**` READ-ONLY durante W0-W14.

**Compatibilidad requerida al tocar backend compartido:**
- auth ES256
- device binding
- bootstrap
- challenge/canje
- route scope
- Hoja Viva
- pagos/reversos
- jornadas
- movimientos
- sync
- cierres
- idempotencia
- S4/S5 conflict/provenance

**Cierre final:** certificación de compatibilidad móvil completa sin cambios Flutter.

---

## W1 — Audit Trail + Usuarios/Roles

**Estado:** ✅ FINAL PASS — CI remoto verde sobre `355cdb3`
**Depende de:** W0.2 (matriz) + W0.3 (regla fecha)
**Backend:** tabla audit_log, actor_nombre en read model (LEFT JOIN), m10 migration (DROP CHECK → UPDATE → CREATE INDEX)
**BFF:** GET /api/usuarios, POST /api/usuarios, PATCH /api/usuarios/[id], PATCH /api/usuarios/[id]/estado?activo=0|1, GET /api/audit, POST /api/activaciones/codigos
**UI:** /usuarios (ADMIN, con filtros/activación/confirmación), /auditoria (ADMIN, con actor nombre/metadata expandible)
**E2E:** ADMIN crea/edita/desactiva/reactiva usuario, genera activación, filtra auditoría; COBRADOR/INVERSIONISTA sin navegación Usuarios/Auditoría, 403 en mutaciones
**A11Y:** axe en /usuarios, /auditoria, formularios, confirmaciones, keyboard nav
**Gates locales:** backend 399 passed / 9 skipped ✅, alembic head m10_audit_documento ✅, api:check ✅, lint 0 errores ✅, typecheck ✅, build ✅, E2E mock 136/136 ✅, W1+a11y 41 passed ✅
**CI remoto (sobre 355cdb3):**
- Backend CI `31957450735` **PASS** — Alembic check ✅, pytest 399/9 ✅, PostgreSQL m9→m10 migration gate ✅, PostgreSQL NIT concurrency gate ✅
- Web CI `31957450733` **PASS** — OpenAPI drift + lint + typecheck + build ✅, E2E mock (RBAC + contrato) ✅, E2E real (FastAPI + Postgres) ✅

### Incidente Git (resuelto)
- master accidental apuntaba a 913fe6f (contaminado)
- Branquicota quarantine: `quarantine/master-contamination-2026-08-15` → 913fe6f
- master restaurado a baseline canónico `486d08b`
- product/web-premium-v1 limpio, push exitoso

### m10 — Migration hardening
- Orden crítico: DROP CHECK constraint → UPDATE typo (USUARIO_DESATIVADO → USUARIO_DESACTIVADO) → CREATE INDEX
- Test unitario portable (SQLite) con actor `activo=1` (NOT NULL)
- Gate de migración real PostgreSQL (`TestM9toM10UpgradePG`) **ejecutado en CI** (paso propio):
  DB scratch temporal, alembic upgrade m9, fila legacy con typo, alembic upgrade m10,
  verifica rename + sin typo + índice uq_usuario_negocio_documento + head m10.
- Fix final: `render_as_string(hide_password=False)` para no enmascarar credenciales de conexión (CI lo confirmó PASS).

---

## W2 — Clientes 360

**Estado:** ✅ FINAL PASS — CI remoto verde sobre `d89f736`
**Depende de:** W1
**Backend:** GET/POST `/api/clientes` (lista paginada + filtros `q`, `tipo_documento`, `identity_status`; scoped a la ruta del COBRADOR), GET/PATCH `/api/clientes/{id}` (detalle 360 con créditos, saldo/mora/ruta/cobrador y `pagos_recientes`; PATCH solo campos editables — identidad NO editable → 422), capabilities `clientes:ver` (ADMINISTRADOR + COBRADOR) y `clientes:gestionar` (SOLO ADMINISTRADOR); `cliente_service.py`, DTOs `clienteListDTO`/`clienteResponseDTO`/`cliente360DTO`; OpenAPI regenerado
**BFF:** GET+POST `/api/clientes`, GET+PATCH `/api/clientes/[id]` (proxies al backend, session httpOnly)
**UI:** `/clientes` (ClientesPage: tabla, search, filtros estado/tipo, paginación, crear/editar con confirmación), `/clientes/[id]` (Cliente360Page: créditos con saldo/mora/ruta/cobrador + pagos recientes), gate `clientes:ver` → Forbidden para INVERSIONISTA, nav por capability
**E2E mock:** 18 tests en `w2-clientes.spec.ts` (ADMIN lista/busca/filtra/pagina/crea/edita/detalle 360; COBRADOR lista scoped, detalle 404 fuera de ruta, POST 403; INVERSIONISTA sin nav + 403) + 3 scans a11y
**E2E real:** 26/26 contra FastAPI real (:8001) + Postgres (incluye `real-rbac` con CAPS W2)
**Gates locales:** backend 426 passed / 9 skipped ✅, alembic head m10_audit_documento ✅, api:check ✅, lint 0 errores ✅, typecheck ✅, build ✅, E2E mock 157/157 ✅, a11y 22 ✅, E2E real 26/26 ✅
**CI remoto (sobre d89f736):**
- Backend CI `31961405789` **PASS** — Alembic check + pytest 426/9 + migration gates PG ✅
- Web CI `31961405790` **PASS** — OpenAPI drift + lint + typecheck + build + E2E mock ✅

### Decisiones W2
- **Listado COBRADOR scoped por ruta**: el mock replica el contrato real (COBRADOR ve solo clientes de su ruta; detalle fuera de ruta → 404, nunca 403).
- **Identidad NO editable por PATCH**: el contrato real responde 422 si el payload intenta mutar documento/tipo/estado.
- **No se creó `real-clientes.spec.ts`**: cobertura W2 real suficiente mediante (1) E2E mock completo del contrato, (2) `real-rbac.spec.ts` con las CAPS `clientes:*` contra FastAPI real, (3) contract tests del backend (`test_w2.py`).
- **E2E real local se ejecuta sobre PG `:5432`** (`REAL_DB_URL=postgresql://postgres:postgres@127.0.0.1:5432/daily_web_e2e_test`) con el backend en `:8001`; el default de `real-seed.ts` (`:5433`) quedó para el entorno heredado.

---

## W3 — Cartera y Créditos

**Estado:** PENDIENTE
**Depende de:** W2

---

## W4 — Rutas y Cobradores

**Estado:** PENDIENTE
**Depende de:** W3

---

## W5 — Centro Financiero

**Estado:** PENDIENTE
**Depende de:** W4

---

## W6 — Cobranza y Mora

**Estado:** PENDIENTE
**Depende de:** W5

---

## W7 — Reportes Premium

**Estado:** PENDIENTE
**Depende de:** W6

---

## W8 — Dashboard Ejecutivo

**Estado:** PENDIENTE
**Depende de:** W7

---

## W9 — Inversionista Final

**Estado:** PENDIENTE
**Depende de:** W8

---

## W10 — Capa Multi-LLM / BYOK

**Estado:** PENDIENTE
**Depende de:** W9

---

## W11 — Daily Assistant Web

**Estado:** PENDIENTE
**Depende de:** W10

---

## W12 — Evals Multi-Provider

**Estado:** PENDIENTE
**Depende de:** W11

---

## W13 — UX / Performance / Accessibility

**Estado:** PENDIENTE
**Depende de:** W12

---

## W14 — Cierre Final

**Estado:** PENDIENTE
**Depende de:** W13

---

## Reglas de ejecución

1. **Un vertical a la vez.** No saltar fases.
2. **Commit por requisito.** Un commit por feature.
3. **CI verde antes de avanzar.** Backend CI + Web CI PASS.
4. **Mobile Contract Freeze.** No tocar `apps/mobile/**`.
5. **Backend authority.** Web captura y presenta; backend calcula.
6. **OpenAPI drift gate.** `npm run api:check` siempre PASS.
7. **E2E por rol.** ADMIN, INVERSIONISTA, COBRADOR.
8. **Anti-deuda.** No parches para verde, no `|| true`, no cálculos TS financieros.

## Decisones

| # | Decisión | Fecha | Justificación |
|---|---|---|---|
| 1 | Ledger como único documento de estado | 2026-08-15 | Evita duplicación con PLAN MAESTRO V2 |
| 2 | Fecha de negocio = America/Bogota | 2026-08-15 | Colombia; no cambiar Hoja Viva existente |
| 3 | Mobile Contract Freeze | 2026-08-15 | Proteger app en uso real |
| 4 | W10 antes de W11 | 2026-08-15 | Provider gateway necesario para asistente |
| 5 | E2E real de W2 sobre PG :5432 | 2026-08-16 | PG heredado en :5433 quedó desalineado; :5432 es la instancia canónica |
| 6 | Sin real-clientes.spec.ts | 2026-08-16 | Cobertura W2 real vía mock E2E + real-rbac CAPS + test_w2 |

## Blockers

Ninguno.
