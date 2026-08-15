# AGENTS.md — Daily System

## Identidad
Eres un ingeniero senior trabajando en **Daily System**, plataforma de cobro diario para Colombia.
## Directorio de trabajo

```
/home/jesus/proyectos/daily-system
```
Este es el checkout operativo canónico. Confirmar siempre con `pwd` y `git rev-parse --show-toplevel` antes de cualquier operación.

## Estado del repositorio (2026-08-15)

| Concepto | Valor |
|---|---|
| Rama de trabajo | `product/web-premium-v1` |
| HEAD operativo | dinámico — `git rev-parse HEAD` (Git es autoridad) |
| Baseline funcional certificado | `bbb3e102` |
| Commit fuente evidencia visual responsive | `33b1342` |
| HEAD (repositorio) | **Dinámico** — `git rev-parse HEAD` (Git es autoridad; SHA no se hardcodea en docs) |
| origin/master | `486d08b` (no contiene hardening ni Web Premium) |

> **Importante:** el trabajo activo vive en `product/web-premium-v1` (o descendiente).
> `master` no contiene hardening B1-B7, sync S0-S5 ni la Web Premium.
> Ver `docs/STATUS.md` para estado canónico en tiempo real.

---

## Jerarquía del proyecto

| Capa | Responsable | Propósito |
|---|---|---|
| **Código + tests** | Evidencia | Estado real verificable; prevalece sobre docs históricas |
| **Git** | Historial | Evidencia verificable, diffs, commits |
| **docs/** | Especificación | Estado canónico, arquitectura, decisiones, testing |
| **Engram** | Memoria | Decisiones, avances, continuidad entre sesiones |
| **Graphify** | Estructura | Relaciones entre archivos, grafo de conocimiento |
| **OpenCode** | Ejecución | Herramienta de trabajo principal |

---

## Engram — Memoria Persistente

**Project obligatorio:** `daily-system`

Toda llamada `mem_*` que acepte `project` debe incluir explícitamente:
```
project: "daily-system"
```

No confiar en la detección automática por nombre de carpeta.

### Cuándo guardar

Después de: decisión de arquitectura, migración, endpoint terminado, corrección financiera, cambio de seguridad, prueba relevante, error con causa/solución, bloqueo, cambio de orden, commit de hito.

### topic_key estables

```
architecture/backend
architecture/sync
architecture/mobile
architecture/web-mock
architecture/web-premium
database/schema
security/auth
security/device-binding
security/route-isolation
security/idempotencia
finance/daily-close
finance/renewal
milestone/M0
milestone/M1
milestone/B1-B7
milestone/S0-S5
milestone/web-premium
testing/current-status
blockers/current
next-step/current
```

### Cierre de sesión

1. Ejecutar pruebas.
2. `git status`.
3. `mem_session_summary` con `project: "daily-system"`.
4. Registrar: terminado, pendiente, pruebas, errores, archivos, commit, siguiente acción.

### Recuperación

Después de compactación: `mem_context` → `AGENTS.md` → `docs/ENGRAM-PROTOCOL.md` → `git log` → `next-step/current`.

### No guardar

tokens, API keys, contraseñas, secretos hardcodeados, datos sensibles.

---

## Graphify — Grafo de Conocimiento

**Ruta del grafo:** `graphify-out/`

Graphify indexa la estructura y relaciones del código. Solo puede indexar Daily System.

### Antes de ejecutar

Verificar la raíz Git:
```bash
cd /home/jesus/proyectos/daily-system
pwd
git rev-parse --show-toplevel
```

### Comandos

- `graphify .` → indexación completa
- `graphify . --update` → indexación incremental (después de cambios)
- `graphify cluster-only .` → re-clustering sin LLM
- `graphify query "pregunta"` → consultar el grafo

### Cuándo ejecutar

- Después de cerrar un hito
- Después de añadir o eliminar módulos
- Después de modificar el schema
- Después de cambiar contratos API
- Después de refactorización estructural
- Antes de auditoría de arquitectura

### Archivos regenerables

`graphify-out/` es regenerable y debe excluirse de Git:

```
graphify-out/
```

---

## Stack

- Backend: Python, FastAPI, SQLAlchemy, Alembic
- Mobile: Flutter (primary client — Android offline collector)
- Web: Next.js 16, React 19, TypeScript, Tailwind CSS (**production-grade / preparada para producción** — panel administrativo `apps/web/`, NO desplegada)
- DB: PostgreSQL (prod) + SQLite (mobile local / backend test default)
- Sync: SQLite + sync_queue + custom offline layer (NOT PowerSync)
- Auth: JWT ES256 + AndroidKeyStore + challenge-response (daily-auth-v1) + sesión web httpOnly (`/api/auth/me`)
- Tests: pytest (backend) + flutter test (mobile) + Playwright E2E (web) + CI 3 workflows

## Reglas de oro

1. Money = integers COP, rates = NUMERIC
2. UUIDs = `UUID(as_uuid=True)`, FastAPI recibe strings
3. Filtrar por `negocio_id` en toda query operativa
4. Decimal para montos, float prohibido en finanzas
5. Commit messages: Conventional Commits (feat:, fix:, chore:, refactor:, test:, docs:)
6. Bot en móvil: PROHIBIDO. Cualquier bot futuro es exclusivamente administrativo.
7. No tocar los componentes de `docs/SECURITY.md` §7 (auth, activación, sync, finanzas) sin instrucción explícita + pruebas de contrato.

## Gates de verificación (estado canónico 2026-08-15)

| Gate | Comando | Esperado |
|---|---|---|
| Backend | `cd apps/api && python3 -m pytest src/tests/ -q` | 367 passed, 8 skipped |
| Alembic head | `cd apps/api && python3 -m alembic heads` | `m8_negocio_nit` |
| Mobile | `cd apps/mobile && flutter test` | 177/177 passing |
| Analyzer | `cd apps/mobile && flutter analyze` | 14 infos preexistentes, 0 nuevos |
| Web API check | `cd apps/web && npm run api:check` | PASS (contrato OpenAPI) |
| Web lint | `cd apps/web && npm run lint` | PASS |
| Web typecheck | `cd apps/web && npm run typecheck` | PASS |
| Web build | `cd apps/web && npm run build` | PASS |
| Web E2E mock | `cd apps/web && npm run test` | 107 passing |
| Web E2E real | `cd apps/web && npm run test:real` | 26 passing |
| Audit | `cd apps/web && npm audit` | 0 vulnerabilities |
| CI | GitHub Actions | backend-ci · web-ci = PASS (ui-gate trigger: master; mobile baseline aceptado: 177/177, 14 infos) |

## Workflow

1. `/plan` antes de tocar código
2. `/review` antes de commitear
3. `/test` después de cambios
4. `/handoff` al cerrar sesión
