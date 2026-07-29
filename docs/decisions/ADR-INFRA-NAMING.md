# ADR-INFRA-NAMING — Migración de nombres de infraestructura

**Estado:** Propuesta
**Fecha:** 2026-07-28
**Decisión pendiente:** Momento de ejecución

---

## Contexto

El proyecto se llamó originalmente "Cobro Colombia" durante el desarrollo inicial (M0). El nombre oficial del producto cambió a **Daily System** y el repositorio a `daily-system`.

El código fuente (FastAPI, tests, documentación) ya fue renombrado. La infraestructura Docker mantiene nombres heredados que deben migrarse sin pérdida de datos.

## Estado actual

| Recurso | Nombre actual | Nombre propuesto |
|---|---|---|
| Contenedor PostgreSQL | `cobro-postgres` | `daily-postgres` |
| Volumen de datos | `cobro-pgdata` | `daily-pgdata` |
| Proyecto Compose | `daily-system` | `daily-system` (ya corregido) |
| Usuario PostgreSQL | `cobro` | `daily` |
| Base de datos | `cobro` | `daily` |
| Puerto | `7103` | `7103` (sin cambio) |

## Riesgos de la migración

1. **Pérdida de datos:** Cambiar el nombre del contenedor sin preservar el volumen elimina la base de datos migrada.
2. **Conexiones activas:** La API en desarrollo podría estar conectada al cambiar usuario/base.
3. **Credenciales hardcodeadas:** Actualmente `POSTGRES_PASSWORD: cobro_secret` está en texto plano público en el repositorio.

## Plan de migración (cuando se ejecute)

### Paso 1: Backup del volumen

```bash
docker run --rm -v cobro-pgdata:/data -v $(pwd):/backup alpine tar czf /backup/cobro-pgdata-backup.tar.gz -C /data .
```

### Paso 2: Renombrar usuario y base

```sql
-- Conectar al contenedor existente
ALTER USER cobro RENAME TO daily;
ALTER DATABASE cobro RENAME TO daily;
```

### Paso 3: Recrear el contenedor con nuevos nombres

```bash
cd infra
docker compose down
docker compose up -d postgres
```

### Paso 4: Verificar migraciones

```bash
cd apps/api
DATABASE_URL=postgresql://daily:daily_dev@localhost:7103/daily alembic upgrade head
```

### Paso 5: Verificar aplicación

```bash
curl http://localhost:7100/api/health
# {"status":"ok","service":"daily-system-api"}
```

### Rollback

```bash
docker compose down
docker volume rm daily-pgdata
docker run --rm -v cobro-pgdata:/data -v $(pwd):/backup alpine tar xzf /backup/cobro-pgdata-backup.tar.gz -C /data
# Revertir docker-compose.yml al estado anterior
docker compose up -d postgres
```

---

## Decisión

**Se ejecuta cuando el desarrollo lo requiera (antes de M1 o antes de producción), no durante esta tarea de normalización.** El contenedor actual sigue funcionando sin cambios.

## Referencias

- Commit `65c90f8` — normalización de nombres en código
- `infra/docker-compose.yml` — configuración actual
- `infra/.env.example` — variables de entorno
