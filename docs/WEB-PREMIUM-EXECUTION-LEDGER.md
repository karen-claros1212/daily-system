# WEB PREMIUM — Execution Ledger

**Proyecto:** daily-system
**Rama:** `product/web-premium-v1`
**Última actualización:** 2026-08-15
**HEAD:** `869dfc1`

---

## Estado global

| Fase | Estado | Commit | Endpoints | Pruebas | CI | Decisiones | Blockers |
|---|---|---|---|---|---|---|---|
| **W0** | ✅ COMPLETADO | dac558d | BFF usuarios/audit | — | ✅ | Ledger creado | Ninguno |
| **W1** | ✅ COMPLETADO | 869dfc1 | Todos | 32/32 backend + E2E + A11Y | en espera | Git repair, BFF PATCH, m10, UI completa | Ninguno |
| **W2** | PENDIENTE | — | — | — | — | — | Depende de W1 |
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

### Estado: EN PROGRESO

#### W0.1 — Ledger (este archivo)
- [x] Ledger creado con fases W0-W14
- [x] Matriz de contratos inicial
- [x] Mobile Contract Freeze definido
- [x] Reglas anti-deuda listadas

#### W0.2 — Matriz de contratos

| Dominio | Backend | BFF | UI | Mutaciones | E2E | Estado |
|---|---:|---:|---:|---:|---:|---|
| Usuarios | auditar | auditar | no/parcial | auditar | auditar | W1 |
| Clientes | sí | no/parcial | no | sí | no | W2 |
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

**Estado:** ✅ COMPLETADO
**Depende de:** W0.2 (matriz) + W0.3 (regla fecha)
**Backend:** tabla audit_log, actor_nombre en read model (LEFT JOIN), m10 migration (DROP CHECK → UPDATE → CREATE INDEX)
**BFF:** GET /api/usuarios, POST /api/usuarios, PATCH /api/usuarios/[id], PATCH /api/usuarios/[id]/estado?activo=0|1, GET /api/audit, POST /api/activaciones/codigos
**UI:** /usuarios (ADMIN, con filtros/activación/confirmación), /auditoria (ADMIN, con actor nombre/metadata expandible)
**E2E:** ADMIN crea/edita/desactiva/reactiva usuario, genera activación, filtra auditoría; COBRADOR/INVERSIONISTA sin navegación Usuarios/Auditoría, 403 en mutaciones
**A11Y:** axe en /usuarios, /auditoria, formularios, confirmaciones, keyboard nav
**Gates:** backend 32/32 ✅, api:check ✅, lint ✅, typecheck ✅, build ✅

### Incidente Git (resuelto)
- master accidental apuntaba a 913fe6f (contaminado)
- Branquicota quarantine: `quarantine/master-contamination-2026-08-15` → 913fe6f
- master restaurado a baseline canónico `486d08b`
- product/web-premium-v1 limpio, push exitoso

### m10 — Migration hardening
- Orden crítico: DROP CHECK constraint → UPDATE typo (USUARIO_DESATIVADO → USUARIO_DESACTIVADO) → CREATE INDEX
- Test PostgreSQL real con fila legacy: pasa 32/32

---

## W2 — Clientes 360

**Estado:** PENDIENTE
**Depende de:** W1

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

## Blockers

Ninguno.
