# Offline Sync — Daily System

**Documento:** Normativo
**Última actualización:** 2026-08-11
**Base verificada:** `c0a3a9c` (baseline código S0-S2)
**HEAD (repositorio):** dinámico — `git rev-parse HEAD`
**Ver también:** [Security](SECURITY.md), [Architecture](ARCHITECTURE.md)

---

## Separación de bloques (NO ambiguo)

> **S3 no es "S2.5". S3 no es "S4". S3 es el bloque actual.**

| Bloque | Alcance | Dirección | Estado |
|---|---|---|---|
| **S0** | Session maintenance | Móvil → Backend | ✅ Implementado |
| **S1** | Route isolation (server-derived scope) | Backend | ✅ Implementado |
| **S2** | Pull dataset + local persistence | Backend → Móvil | ✅ Implementado |
| **S3** | Outbox: push → ACK → retry → conflictos | Móvil → Backend | ⏳ PENDIENTE |

---

## S0 — Session maintenance ✅

**Objetivo:** renovar el JWT antes de que expire, sin esperar a un 401.

**Implementación:**
- `apps/mobile/lib/auth/device_auth_client.dart` — `requiereRenovacion()` evalúa expiración
- Renueva ~5 minutos antes de `expira_el`
- Usa challenge-response single-use (daily-auth-v1)
- `AuthHttpClient` (único cliente HTTP): 401 → `tokenStore.borrarToken()` + rethrow

**Código:**
```dart
// sync_client.dart:41-62
if (await auth.requiereRenovacion()) {
  await auth.renovarSesion();
}
final token = await tokenStore.leerToken();
final json = await http.getJson('/api/mobile/sync', token: token);
```

---

## S1 — Route isolation ✅

**Objetivo:** el móvil nunca elige ni descarga rutas ajenas.

**Implementación:**
- Backend: `get_request_context` (`deps.py`) — fail-closed; 0 o >1 rutas activas → 401
- `mobile_sync_service.py` — revalida que el contexto sea `COBRADOR` con ruta activa vigente
- Mobile: `SyncDataset` incluye `rutaId`/`negocioId`/`cobradorId` derivados del server

---

## S2 — Pull + local persistence ✅

**Objetivo:** reflejar el dataset de la ruta activa en SQLite local, sin destruir estado offline.

### Flujo implementado

```
   Backend
      │  GET /api/mobile/sync (Bearer JWT ES256)
      ↓
   SyncClient.sincronizar()
      ↓  (session renewal S0 si vencíbase)
   SyncDataset (clientes, creditos, cuotas, jornadas, pagos, movimientos)
      ↓
   SyncRepository.importar()
      ↓
   SQLite (ON CONFLICT(id) DO UPDATE SET)
```

### Reglas de persistencia (`sync_repository.dart`)

1. **UPSERT por PK** — `INSERT ... ON CONFLICT(id) DO UPDATE SET <cols>`. Nunca `INSERT OR REPLACE` (que borra y re-inserta).
2. **Protección de pendientes** — si una entidad tiene trabajo en `sync_queue` (estado `PENDIENTE_DE_SINCRONIZAR`), el pull no la sobrescribe.
3. **Protección de jornada CLOSED_LOCAL_PENDING_SYNC** — si el estado local es `CLOSED_LOCAL_PENDING_SYNC` y el servidor devuelve un estado anterior, no regresa (conflicto para S3).
4. **Triggers DROP/CREATE en transacción** — `trg_pago_require_open_jornada` y `trg_movimiento_require_open_jornada` se drop/recreate dentro de la transacción de pagos/movimientos (el server envía jornadas cerradas que la guarda rechazaría). DDL transaccional en SQLite → rollback preserva triggers si falla.
5. **Orden de importación:** identidad → clientes → créditos → cuotas → jornadas → pagos → movimientos.
6. **Cuotas protegidas** — créditos con pagos pendientes no ven revertidas sus cuotas.
7. **Cada dataset en su propia transacción.**

### S2-H2 — Reversal preservation ✅

El pull preserva `reversal_of_payment_id` en `Pago` y bloquea un doble reverso local. Verificado por:
- `test/sync/sync_repository_test.dart` — "preservation of reversal link and blocks double reversal"
- `test_m6_sync.py::test_sync_pagos_expone_reversal_of_payment_id`

---

## S3 — Outbox móvil→servidor ⏳ PENDIENTE

**Objetivo:** cuando el móvil está offline, los eventos financieros (pagos, movimientos, cierres) se encolan localmente y se empujan al servidor al recuperar conectividad. El servidor responde con ACK/NACK; el móvil hace retry reintentable y resuelve conflictos.

### Estado actual
- **`sync_queue_service.dart`** existe (push local de la cola de eventos pendientes). Los endpoints individuales de push **YA EXISTEN** en el backend: POST /api/pagos, POST /api/pagos/{id}/reversar, POST /api/movimientos, POST /api/jornadas/{id}/cerrar, POST /api/jornadas/{id}/sincronizar.
- **Lo que falta (S3):** el envelope de outbox móvil (envelope atómico de push, ACK/NACK, idempotency key persistence, retry reintentable, resolución de conflictos, reasignación segura). Si se demuestra necesaria una fachada batch/mobile para S3, será una decisión de S3 — **no** una ausencia general de endpoints.
- **No documentar como implementado.** No asumir.

### Flujo objetivo (no implementado)

```
Hoja Viva → PagoService/MovimientoService/JornadaService (local, append-only)
      ↓  (offline: encola en sync_queue)
sync_queue (outbox local)
      ↓  (online: S3 push loop)
POST /api/pagos / /api/movimientos / /api/jornadas/{id}/cerrar / sincronizar
      ↓
Server responde 201 (ACK) / 409 (conflict) / 401 (reauth) / 5xx (retry)
      ↓
S3: ACK → marcar done; 409 → resolver conflicto; 401 → reauth; 5xx → retry
```

---

## Jornada state machine

```
OPEN → CLOSING → CLOSED_LOCAL_PENDING_SYNC → CLOSED_SYNCED
```

- **OPEN:** jornada activa, acepta pagos/movimientos
- **CLOSING:** en transición de cierre (local)
- **CLOSED_LOCAL_PENDING_SYNC:** cerrada localmente; pendiente de sincronizar al servidor
- **CLOSED_SYNCED:** cerrada y validada por el servidor (snapshot hash verified)

- No hay transición hacia atrás (CLOSED_SYNCED → OPEN está prohibido)
- AJUSTE de movimiento está permitido en estados cerrados (solo admin)
- `sincronizar_cierre` valida: efectivo_esperado, efectivo_contado = esperado + diferencia, y los 4 IDs de evento (pagos/reversales/movimientos/renovaciones) coinciden

---

## Idempotency

| Endpoint | Key | Server-side comparison |
|---|---|---|
| POST /api/pagos | `clave_idempotencia` | full payload fields |
| POST /api/movimientos | `clave_idempotencia` | full payload fields |
| POST /api/jornadas/{id}/cerrar | (cierre local) | — |
| POST /api/jornadas/{id}/sincronizar | `idempotencia_cierre` | canonical JSON (sort_keys=True) |

- On mismatch: **409** (JornadaSyncException / MovimientoIdempotencyError / PaymentIdempotencyError)
- On match: return existing (idempotent)
- En S3, el push reutilizará estas idempotency keys existentes.