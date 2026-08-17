# WEB PREMIUM — Execution Ledger

**Proyecto:** daily-system
**Rama:** `product/web-premium-v1`
**Última actualización:** 2026-08-17
**Código certificado último vertical:** `180db73`

---

## Estado global

| Fase | Estado | Commit | Endpoints | Pruebas | CI | Decisiones | Blockers |
|---|---|---|---|---|---|---|---|
| **W0** | ✅ COMPLETADO | dac558d | BFF usuarios/audit | — | ✅ | Ledger creado | Ninguno |
| **W1** | ✅ FINAL PASS | 355cdb3 | Todos | 399 backend + 136 E2E mock + 41 a11y | ✅ PASS (ambos) | Git repair, BFF PATCH, m10, UI completa, PG migration gate real en CI | Ninguno |
| **W2** | ✅ FINAL PASS | d89f736 | Todos | 426 backend + 157 E2E mock + 22 a11y + 26 real | ✅ PASS (ambos) | Listado scoped COBRADOR, 360 DTO, real E2E en PG :5432 | Ninguno |
| **W3** | ✅ FINAL PASS | 875d506 | Todos | 452 backend + 172 E2E mock + 24 a11y + 34 real | ✅ PASS (ambos) | Autoridad financiera backend, PII por rol, sort allowlist | Ninguno |
| **W4** | ✅ FINAL PASS | 22a710c | Todos | 472 backend + 175 E2E mock + 43 E2E real | ✅ PASS (ambos) | S4 vía BFF, JWT stale 401, negativos 403/404, cross-tenant | Ninguno |
| **W5** | ✅ FINAL PASS | 48ead5e | /api/movimientos/web + /resumen | 483 backend + 182 E2E mock + 54 E2E real | ✅ PASS (ambos) | RBAC movimientos:ver 3 roles, BFF cookie auth, DTO minimizado, PII INVERSIONISTA | Ninguno |
| **W6** | ✅ FINAL PASS | 180db73 | /api/cobranza/web + /resumen + /promesas + /{credito_id} | 498 backend + 194 E2E mock + 65 E2E real | ✅ PASS (ambos) | Aging server-side, worklist priorizada, Promise to Pay state machine, drill-down, RBAC cobranza:ver 3 roles, PII cobrador_nombre | Ninguno |
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

**Protección:** `apps/mobile/**` = READ-ONLY durante W0-W14.

**Gate obligatorio por cada vertical W:**

```bash
git diff --name-only <baseline-vertical>..HEAD -- apps/mobile/
```

Resultado exigido: **VACÍO** (0 archivos).

Si alguna vez NO es vacío: **STOP.** No justificar automáticamente.
Requiere regresión crítica demostrada + autorización explícita del owner.

**Compatibilidad backend compartido obligatoria al tocar `apps/api/`:**
- auth ES256 / AndroidKeyStore
- device binding
- bootstrap / challenge/canje
- JWT / version_asignacion
- route scope
- sync
- jornadas
- pagos/reversos
- movimientos
- Hoja Viva
- cierres
- idempotencia
- S4/S5 conflict/provenance

**Cierre final (W14):** certificación de compatibilidad móvil completa sin cambios Flutter.

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

**Estado:** ✅ FINAL PASS — CI remoto verde sobre `875d506`
**Depende de:** W2
**Backend:** GET `/api/creditos` (envelope `{items,total,limit,offset}`, filtros `q` (PII solo roles con `creditos:ver`), `estado`, `ruta_id` (COBRADOR forzado a su ruta → ruta ajena 404), `limit<=100`, `offset`, sort allowlist `fecha_inicio|monto|total|cuota|periodicidad|estado|saldo` + order `asc|desc` → inválido 422), GET `/api/creditos/resumen` (agregados financieros vía `hoja_viva_service.resumen_creditos`, COBRADOR scoped), GET `/api/creditos/{id}` (detalle con saldo/mora/ruta/cobrador/cliente; COBRADOR fuera de ruta o inexistente → 404 sin revelar; INVERSIONISTA PII minimizada `cliente_nombre`/`cliente_id` → null), POST `/api/creditos` (SOLO `creditos:gestionar` → COBRADOR/INVERSIONISTA 403; body allowlist → 422; ruta/cliente inexistente → 404; invariante `total = cuota × n_cuotas` + `generate_schedule` + auditoría append-only `CREDITO_CREADO`); capabilities `creditos:ver` (ADMINISTRADOR + COBRADOR + INVERSIONISTA) y `creditos:gestionar` (SOLO ADMINISTRADOR); `credito_service.py`, `test_w3.py` (26 tests); OpenAPI regenerado (44 paths)
**BFF:** GET+POST `/api/creditos`, GET `/api/creditos/resumen`, GET `/api/creditos/[id]` (proxies al backend, session httpOnly)
**UI:** `/creditos` (CreditosPage: tabla con saldo/mora/formato es-CO, búsqueda, filtro estado, paginación, crear crédito con cálculo de total mostrado por backend), `/creditos/[id]` (CreditoDetailPage: financiero completo + link Cliente360 con `underline` para contraste a11y), gate `creditos:ver`, nav por capability
**E2E mock:** 13 tests en `w3-creditos.spec.ts` (serial + reset por test; ADMIN lista/resumen/busca/ordena por saldo/crea (total backend)/detalle; COBRADOR scoped a su ruta sin crear ni filtrar ruta ajena (404), detalle ajeno 404; INVERSIONISTA PII minimizada sin Cliente360 ni crear; RBAC 403/404/422) + 2 scans a11y (`creditos`, `credito detalle`) — fix WCAG `link-in-text-block` con `underline hover:no-underline`
**E2E real:** 34/34 contra FastAPI real (:8001) + Postgres — incluye `real-creditos.spec.ts` (8 tests: create ADMIN 201 + total + audit `CREDITO_CREADO`, POST 403 COBRADOR (JWT real del flujo de dispositivo)/INVERSIONISTA, ruta inexistente 404, lista/resumen/detalle ADMIN, PII minimizada INVERSIONISTA, COBRADOR scoped ruta ajena 404)
**Gates locales:** backend 452 passed / 9 skipped ✅, alembic head m10_audit_documento ✅, api:check ✅, lint 0 errores (4 warnings baseline) ✅, typecheck ✅, build ✅, npm audit 0 ✅, E2E mock 172/172 ✅, a11y 24 ✅, E2E real 34/34 ✅
**CI remoto (sobre 875d506):**
- Backend CI `31964572610` **PASS** — Alembic check + pytest 452/9 + migration gates PG ✅
- Web CI `31964572612` **PASS** — OpenAPI drift + lint + typecheck + build + E2E mock + E2E real (real-creditos incluido) ✅

### Decisiones W3
- **Autoridad financiera SOLO backend**: saldo/mora/resumen se calculan en `hoja_viva_service` (mora = días transcurridos − 1 − cuotas pagadas, mín 0); la UI nunca recalcula en TS.
- **PII minimizada por rol**: INVERSIONISTA lee cartera pero recibe `cliente_nombre`/`cliente_id` → null y sin link Cliente360; COBRADOR ve solo su ruta con 404 (no 403) fuera de ella.
- **Sort allowlist compartido**: backend y mock replican el mismo conjunto (`fecha_inicio|monto|total|cuota|periodicidad|estado|saldo`); sort inválido → 422 en ambos.
- **Mock sincronizado con contrato real**: `mock-api.mjs` deriva créditos de `CLIENTES_MOCK` (consistencia con counts de clientes), `POST /api/_test/reset-creditos` para determinismo, y replica 422/404/403 por rol.
- **E2E real con JWT real de COBRADOR**: el spec usa el flujo de dispositivo completo (activación daily-v1 → canje → desafío → JWT) — el rol no viaja en el JWT, se deriva de la DB por request.

---

## W4 — Rutas y Cobradores

**Estado:** ✅ FINAL PASS
**Depende de:** W3
**Código certificado:** `22a710c` (real-rutas completo con negativos)
**Backend CI (código):** `31989064613` PASS
**Web CI (código):** `31989064602` PASS (43/43 E2E real incluyendo negativos)

> **Estado documental:** actualizado. El HEAD vigente de `product/web-premium-v1`
> y sus GitHub Actions son la autoridad para la revisión del cierre; este Ledger
> no se autoreferencia.
>
> Validación documental posterior: `a505fcf` — Backend `31989503359` PASS,
> Web `31989503357` PASS.

**Backend:** GET `/api/rutas` (envelope `{items,total,limit,offset}`, filtros `q`/`activa`/`cobrador_id`, sort `nombre|creado_el|version` + order `asc|desc` → inválido 422, paginación `limit<=100`/`offset`), GET `/api/rutas/{id}` (detalle; inexistente → 404), POST `/api/rutas` (SOLO `rutas:crear` → 403; body allowlist → 422; nombre duplicado activo → 409; cobrador inexistente → 404; auditoría `RUTA_CREADA`), PATCH `/api/rutas/{id}/reasignar` (S4: crea ruta nueva para mismo cobrador, ruta anterior → inactiva, bump version, invalidate sesión móvil; nombre duplicado activo → 409; auditoría `RUTA_REASIGNADA`), GET `/api/rutas/resumen` (agregados: total/activas/inactivas/con_cobrador; COBRADOR scoped); capabilities `rutas:ver` (ADMIN+COBRADOR), `rutas:crear` (ADMIN), `rutas:reasignar` (ADMIN); `ruta_service.py`, `test_w4.py` (20 tests); OpenAPI regenerado

**BFF:** GET+POST `/api/rutas`, GET `/api/rutas/[id]`, PATCH `/api/rutas/[id]/reasignar`, GET `/api/rutas/resumen` (proxies al backend, session httpOnly)

**UI:** `/routes` (Routes.tsx: tabla con búsqueda, filtros activa/cobrador, sort, paginación, form crear con confirmación), `/routes/[id]` (RouteDetailPage.tsx: detalle + form reasignación explícita con confirmación + resultado S4), gate `rutas:ver`, nav por capability

**E2E mock:** 9 tests en `w4-rutas.spec.ts` (serial + reset-rutas; ADMIN lista/detalle/crea/409 dup/reasigna S4/cobrador scoped/creación 403/filtros/sort) + a11y scan

**E2E real:** 9 tests en `real-rutas.spec.ts` contra FastAPI :8001 + Postgres + BFF :3000 — (1) COBRADOR JWT real /me 200 route_id=R1, (2) ADMIN reasigna R1→R2 **vía BFF** (no service directo), (3) PG: R1 inactiva, R2 activa, mismo cobrador, version bump, (4) AuditLog RUTA_REASIGNADA, (5) JWT ANTERIOR → **401** (version_asignacion stale), (6) JWT NUEVO (re-autenticación) → 200 route_id=R2, (7) COBRADOR POST/PATCH → **403**, (8) INVERSIONISTA GET 200 / POST+PATCH **403**, (9) CROSS-TENANT ruta ajena → **404** sin revelar. Suite real completa: 43/43 ✅

**ANDROID / MOBILE CONTRACT FREEZE:** `git diff --name-only e6e564b23bcfbf780a616a16b82ba19b7c06cc20..22a710c -- apps/mobile/` = **VACÍO** ✅

**Gates locales:** backend 472 passed / 9 skipped ✅, E2E mock 175/175 ✅, E2E real 43/43 ✅, api:check ✅, lint ✅, typecheck ✅, build ✅

### Decisiones W4
- **Reasignación S4 crea ruta nueva (no muta la existente):** `ruta_id_origen` inmutable, bump version, invalidate sesión móvil. Preserva el contrato Android (el cobrador recibe su ruta activa por bootstrap, no por mutación).
- **COBRADOR scoped a su ruta activa:** igual que el backend real — el mock replica el aislamiento (solo ve su ruta; detalle ajeno → 404).
- **Mock `test-cobrador-code` en `SESIONES`:** necesario para `sesionDe()` en E2E (antes solo existía en `ACTIVATION_TOKENS`, causando null en lookup).
- **Read-model Web enriquecido:** `cobrador_nombre` en vez de UUID, paginación/filtros para panel — sin alterar el read-model que consume Android.

---

## W5 — Centro Financiero

**Estado:** ✅ FINAL PASS
**Depende de:** W4
**Código certificado:** `aad2221` (implementación) + `48ead5e` (corrección CI)
**Backend CI:** `31994576690` PASS
**Web CI:** `31994576694` PASS

### Scope (matriz W0.2)

| Dominio | Backend | BFF | UI | Mutaciones | E2E |
|---|---:|---:|---:|---:|---:|
| Movimientos/Gastos | sí | auditar | no | sí | auditar |

### Entregables

- **Backend:** `GET /api/movimientos/web` (envelope, filtros q/tipo/naturaleza/ruta_id, sort creado_el/monto/tipo, order asc/desc, paginación limit≤100, role scoping) + `GET /api/movimientos/resumen` (total_movimientos, total_monto, gastos_por_tipo)
- **RBAC:** `movimientos:ver` → ADMINISTRADOR + INVERSIONISTA + COBRADOR (scoped a ruta activa). `movimientos:registrar` → COBRADOR (invariante)
- **BFF:** `/api/movimientos` (GET) + `/api/movimientos/resumen` (GET) → proxy a backend. Sort/order pass-through 422
- **UI:** `/movimientos` — Centro Financiero: resumen cards, tabla paginada, filtros (naturaleza, ruta, búsqueda), sort, paginación. Navegación AppShell gated por `movimientos:ver`
- **DTO minimizado:** id, tipo, naturaleza, monto, nota, creado_por_nombre, creado_el, jornada_fecha, ruta_id, ruta_nombre. INVERSIONISTA: nota=null, creado_por_nombre=null
- **E2E mock:** 7 tests (ADMIN envelope/filtros/sort/búsqueda, INVERSIONISTA PII, COBRADOR scoped)
- **E2E real:** 11 tests (ADMIN: envelope, resumen, filtros, búsqueda, sort, paginación, 422 sort/order; COBRADOR: JWT dispositivo, scoped, /me capabilities; INVERSIONISTA: PII/minimización)

### Decisiones

1. `movimientos:ver` es capability separada de `movimientos:registrar` — un COBRADOR puede ver sin registrar
2. BFF no convierte silenciosamente sort inválido → 422 (contrato explícito)
3. Backend valida `order` explícito (asc|desc) → 422 si no match
4. Read-model web NO expone: negocio_id, clave_idempotencia, creado_por UUID, jornada_id
5. INVERSIONISTA: nota=null (free-text puede contener PII)
6. Route ordering: `/web` y `/resumen` antes de `/{movimiento_id}` en FastAPI
7. Mobile contract: `GET /api/movimientos?jornada_id=` invariante (mobile siempre envía jornada_id)

### Evidencia estable

| Gate | Resultado |
|---|---|
| Backend pytest | 483 passed, 9 skipped |
| E2E mock | 182 passed |
| E2E real | 54 passed (incluye W5: 11 tests) |
| Typecheck | PASS |
| Lint | 0 errors, 10 warnings (preexistentes) |
| Build | PASS |
| api:check | PASS (OpenAPI reexportado con /web + /resumen) |
| npm audit | 0 vulnerabilities |
| Mobile freeze | VACÍO (0 archivos en apps/mobile/) |

---

## W6 — Cobranza y Mora

**Estado:** ✅ FINAL PASS
**Depende de:** W5
**Código certificado:** `f56969c` (implementación) + `18a4a85` (RBAC E2E) + `5425d2f` (drill-down + Promise UI) + `7e42cd0` (E2E mock+real) + `180db73` (PII fix)
**Backend CI:** `32055132322` PASS
**Web CI:** `32055132251` PASS
**Gates:** 498/498 backend, 194/194 E2E mock, 65/65 E2E real, typecheck/lint/build PASS
**Alembic head:** `m11_promesa_pago`

### Scope (matriz W0.2)

| Dominio | Backend | BFF | UI | Mutaciones | E2E |
|---|---:|---:|---:|---:|---:|
| Cobranza/Mora/Aging | sí | auditar | no | sí | auditar |

### Entregables

- **Backend:** `cobranza_service.py` (aging buckets, days_past_due, overdue_installments, overdue_amount, priority scoring) + `GET /api/cobranza/web` (worklist paginada, filtros, sort, role scoping) + `GET /api/cobranza/resumen` (KPIs + aging distribution) + `GET /api/cobranza/{credito_id}` (drill-down: obligaciones vencidas, pagos recientes, promesas, aging, PII por rol) + `POST /api/cobranza/promesas` (409 si ya existe ACTIVE) + state machine (cumplir/incumplir/cancelar)
- **Modelo:** `PromesaPago` (estado ACTIVE/FULFILLED/BROKEN/CANCELLED, idempotencia, tenant isolation) + migration `m11_promesa_pago`
- **RBAC:** `cobranza:ver` (3 roles), `cobranza:gestionar` (ADMIN), `promesas:ver/crear/actualizar` (ADMIN+COBRADOR)
- **BFF:** `/api/cobranza` (GET) + `/api/cobranza/resumen` (GET) + `/api/cobranza/[credito_id]` (GET drill-down) + `/api/cobranza/promesas` (POST) + `/api/cobranza/promesas/[id]/cumplir|incumplir|cancelar` (POST) → proxy a backend
- **UI:** `/cobranza` — Centro de Cobranza: KPIs, aging distribution, worklist priorizada, filtros (bucket, prioridad, búsqueda), sort. `/cobranza/[credito_id]` — Drill-down: KPIs, obligaciones vencidas (tabla), pagos recientes, promesas (historial), formulario Promise to Pay (fecha, monto, nota), manejo 409/422/403, refresh posterior. AppShell nav gated por `cobranza:ver`
- **E2E mock:** 12 tests en `w6-cobranza.spec.ts` (ADMIN: worklist, KPIs, aging, drill-down, crear promesa, 409, 422, filtro bucket; INVERSIONISTA: PII minimizada worklist + drill-down; COBRADOR: scoped, 404 fuera de ruta, crear promesa)
- **E2E real:** 11 tests en `real-cobranza.spec.ts` (ADMIN: worklist, resumen, drill-down, crear promesa 201, 409, 422; COBRADOR: scoped worklist, drill-down, capabilities; INVERSIONISTA: PII minimizada worklist + drill-down)

### Decisiones

1. Aging buckets: CURRENT, 1-7, 8-15, 16-30, 31-60, 61-90, 90+ (fuente única en `AGING_BUCKETS`)
2. `days_past_due` = (report_date - oldest_unpaid_due_date).days — no hardcode en frontend
3. `overdue_amount` ≠ `total_outstanding` — vencido vs. saldo total vivo
4. Priority scoring: heurístico determinista (no ML), explicable con `priority_factors`
5. Promise to Pay: state machine estricta (ACTIVE → FULFILLED/BROKEN/CANCELLED, sin re-apertura)
6. `CuotaProgramada.estado` nunca se actualiza — la verdad financiera está en `Pago` rows
7. INVERSIONISTA: PII minimizada (cliente_id=null, cliente_nombre=null, cobrador_nombre=null)

### Evidencia estable

| Gate | Resultado |
|---|---|
| Backend pytest | 498 passed, 9 skipped |
| E2E mock | 194 passed (incluye 12 W6 cobranza) |
| E2E real | 65 passed TOTAL (incluye 11 W6 real-cobranza.spec.ts) |
| Typecheck | PASS |
| Lint | 0 errors, 14 warnings (preexistentes) |
| Build | PASS |
| api:check | PASS (OpenAPI 53 paths, +6 cobranza) |
| npm audit | 0 vulnerabilities |
| Mobile freeze | VACÍO (0 archivos en apps/mobile/) |

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
4. **Mobile Contract Freeze.** `apps/mobile/**` = READ-ONLY. Gate obligatorio: `git diff --name-only <baseline>..HEAD -- apps/mobile/` → VACÍO.
5. **Backend authority.** Web captura y presenta; backend calcula.
6. **OpenAPI drift gate.** `npm run api:check` siempre PASS.
7. **E2E por rol.** ADMIN, INVERSIONISTA, COBRADOR.
8. **Anti-deuda.** No parches para verde, no `|| true`, no cálculos TS financieros.
9. **Cierre documental.** Cada W se registra en este ledger con: SHA, CI IDs, tests, mobile freeze, decisiones.

## Decisones

| # | Decisión | Fecha | Justificación |
|---|---|---|---|
| 1 | Ledger como único documento de estado | 2026-08-15 | Evita duplicación con PLAN MAESTRO V2 |
| 2 | Fecha de negocio = America/Bogota | 2026-08-15 | Colombia; no cambiar Hoja Viva existente |
| 3 | Mobile Contract Freeze | 2026-08-15 | Proteger app en uso real |
| 4 | W10 antes de W11 | 2026-08-15 | Provider gateway necesario para asistente |
| 5 | E2E real de W2 sobre PG :5432 | 2026-08-16 | PG heredado en :5433 quedó desalineado; :5432 es la instancia canónica |
| 6 | Sin real-clientes.spec.ts | 2026-08-16 | Cobertura W2 real vía mock E2E + real-rbac CAPS + test_w2 |
| 7 | Mobile Contract Freeze = gate obligatorio por W | 2026-08-16 | `git diff -- apps/mobile/` debe ser VACÍO; si no, STOP + autorización explícita |
| 8 | S4 reasignación crea ruta nueva (no muta) | 2026-08-16 | Preserva contrato Android: cobrador recibe ruta por bootstrap, no por mutación in-place |

## Blockers

Ninguno.
