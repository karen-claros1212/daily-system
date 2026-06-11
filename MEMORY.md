# MEMORY.md

## CobroPro (nexuscorp)

### Stack
- FastAPI + PostgreSQL 16 (PostGIS) + Redis + MinIO + Docker
- Multi-tenant: tenants con SUPER_ADMIN, TENANT_ROOT, COLLECTOR roles
- WebSocket: pub/sub en Redis canal `dashboard:{tenant_id}`, auth via JWT como primer frame

### Arquitectura
- **Auth**: Depends(get_current_user) via deps.py — NO middleware auth (para evitar doble resolución)
- **Interceptor chain**: Timing + RateLimit como middleware, AuthInterceptor existe como clase pero sin registrar
- **EventGate**: Whitelist de 9 eventos WS validados antes de publish a Redis
- **InsightEngine**: IInsightRule abstracta con reglas registrables (compliance, recovery_30d, geo_fencing, risk_drop)

### Módulos completados
- **M1**: Core CRUD + JWT + Docker
- **M2**: Offline-first sync con Protobuf
- **M3**: Automation + Sync v2 batch + Redis caching
- **M4**: Command Center — WS, Assistant Engine, UX premium
- **M5**: MinIO uploads, PendingTransfer cuarentena, Habeas Data (Ley 1581/2012)

### P0-3 Préstamos y Cartera
- **Phase 1** (commit `4428357`, tag `m4.3.0-rc1`): loans pagination/search/filter + PATCH/DELETE/stats + 19 tests
- **Phase 2** (commit `de57d7e`, tag `m4.3.0-rc2`): delinquency job (`update_delinquency.py`, UTC-0 cutoff, idempotent) + 5 tests + 15 payment tests (waterfall cascade, cash, create)
- **LoanStatus.CANCELLED**: enum faltante, agregado en Phase 2
- **Total tests**: 97/97 pasando (excluye `test_reconciliation_sync.py` con error pre-existente de `connect_timeout`)
- **Payment waterfall**: `_cascade_waterfall` en `routers/payments.py` — distribuye pago entre schedules ordenados por `n`, marca PAID/PARTIAL, y actualiza loan.status si todos PAID
- **Delinquency job**: cargo CLI (`python -m app.jobs.update_delinquency`), marca PENDING→LATE por cutoff UTC-0, configurable CUTOFF_MODE/CUTOFF_OFFSET_DAYS
- **Schedule**: NO tiene `days_late` (se computa dinámicamente) ni `tenant_id` (join via `Loan.tenant_id`)

### Bugs conocidos y fixes
- `minio.put_object()` requiere `io.BytesIO()` wrapper alrededor de bytes
- `presigned_get_object()` expires debe ser `timedelta`, no int
- CustomerOut necesita campos `id_document_url` y `habeas_data_accepted` explícitos
- `test_reconciliation_sync.py`: `TypeError: 'connect_timeout'` — error pre-existente, excluir con `--ignore`

### Dola (referencia)
- manual-dola clonado en `/home/jesus/.openclaw/workspace/manual-dola/`
- Patrones útiles: ServiceManager/IAccountService, event whitelist, interceptor chain, FRIDA SSL bypass

### Próximo
- Estabilizar con tests antes de M6
- Posible M6: Flutter app (ver FLUTTER_BLUEPRINT.md)
- Migrar secrets a .env cifrado
