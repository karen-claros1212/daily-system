# AGENTS.md — Daily System

## Identidad
Eres un ingeniero senior trabajando en **Daily System**, plataforma de cobro diario para Colombia.

## Directorio de trabajo
```
/home/jesus/proyectos/daily-system
```
Siempre confirmar con `pwd` y `git rev-parse --show-toplevel`.

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
database/schema
security/route-isolation
finance/daily-close
finance/renewal
milestone/M0
milestone/M1
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

## Stack

- Backend: Python, FastAPI, SQLAlchemy, Alembic
- Frontend: Next.js, TypeScript, Tailwind CSS
- DB: PostgreSQL
- Sync: PowerSync (offline-first)
- Tests: pytest

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
