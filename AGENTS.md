# AGENTS.md — Daily System

## Identidad
Eres un ingeniero senior trabajando en **Daily System**, plataforma de cobro diario para Colombia.
## Directorio de trabajo

```
/home/jesus/proyectos/daily-system
```
Este es el checkout operativo canónico. Confirmar siempre con `pwd` y `git rev-parse --show-toplevel` antes de cualquier operación.

## Estado del repositorio (2026-08-11)

| Concepto | Valor |
|---|---|
| Rama de trabajo verificada | `hardening/b1-b7-audit` |
| HEAD (repositorio) | **Dinámico** — `git rev-parse HEAD` (Git es autoridad; SHA no se hardcodea en docs) |
| HEAD (código S0-S2 baseline) | `c0a3a9c1646358fea4badc45bc9cdf5d6e2a1216` |
| HEAD (checkpoint DOC-SYNC inicial) | `35adf24576a44c9843b73a4d047c0623f7f9d345` (histórico, no autoridad actual) |
| origin/master | `486d08b` (no contiene el hardening B1-B7) |

> **Importante:** el hardening B1-B7 vive en `hardening/b1-b7-audit`, NO en `master`.
> Cualquier trabajo debe basarse en esta rama o su descendiente.
> Ver `docs/STATUS.md` para estado productivo en tiempo real.

---

## Jerarquía del proyecto

| Capa | Responsable | Propósito |
|---|---|---|
| **Documento maestro** | Requisitos | Especificaciones, arquitectura, decisiones |
| **Git** | Historial | Evidencia verificable, diffs, commits |
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

tokens, API keys, contraseñas, secretos硬coded, datos sensibles.

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
- Web: Next.js, TypeScript, Tailwind CSS (PLANNED — apps/web/ is empty; design/prototypes/ is a static MOCK)
- DB: PostgreSQL (prod) + SQLite (mobile local / backend test default)
- Sync: SQLite + sync_queue + custom offline layer (NOT PowerSync)
- Auth: JWT ES256 + AndroidKeyStore + challenge-response (daily-auth-v1)
- Tests: pytest (backend) + flutter test (mobile) + UI Gate CI

## Reglas de oro

1. Money = integers COP, rates = NUMERIC
2. UUIDs = `UUID(as_uuid=True)`, FastAPI recibe strings
3. Filtrar por `negocio_id` en toda query operativa
4. Decimal para montos, float prohibido en finanzas
5. Commit messages: Conventional Commits (feat:, fix:, chore:, refactor:, test:, docs:)

## Workflow

1. `/plan` antes de tocar código
2. `/review` antes de commitear
3. `/test` después de cambios
4. `/handoff` al cerrar sesión
