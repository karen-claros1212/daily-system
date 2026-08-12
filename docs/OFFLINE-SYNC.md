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
| **S3** | Outbox: push → ACK → retry → conflictos | Móvil → Backend | ✅ Implementado |

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

## S3 — Outbox móvil→servidor ✅ PASS / IMPLEMENTADO

**Objetivo:** cuando el móvil está offline, los eventos financieros (pagos, movimientos, cierres) se encolan localmente y se empujan al servidor al recuperar conectividad. El servidor responde con ACK/NACK; el móvil hace retry reintentable y resuelve conflictos.

### Estado actual

- **`sync_queue`** — tabla evolucionada con migration v5. No es una segunda outbox; reutiliza la tabla existente con nuevos estados y columnas.
- **`migration_v5.dart`** — añade: `datos` (JSON payload completo), `idempotency_key`, `ruta_id_origen`, `cobrador_id_origen`, `jornada_id_origen`, `intento`, `ultimo_error`, `ultima_transicion`.
- **`push_orchestrator.dart`** — PushOrchestrator que lee sync_queue pendiente, envía por tipo al endpoint correcto, maneja ACK/NACK/conflicto/retry.
- **`sync_queue_service.dart`** — estados: `PENDIENTE_DE_SINCRONIZAR`, `ENVIANDO`, `SINCRONIZADO`, `ERROR_REINTENTABLE`, `CONFLICTO`.
- **`idempotency_key`** — persistida en sync_queue, enviada en headers de cada push.
- **Provenance** — `ruta_id_origen`, `cobrador_id_origen`, `jornada_id_origen` persistidos en la fila; R1→R2 protection (fila de R1 no se envía bajo R2).
- **`server_entity_id`** — durable: se guarda en sync_queue al recibir ACK del servidor (201/200), permite pull→reconciliación posterior.

### Tipos productivos

| Tipo | Endpoint | Método |
|---|---|---|
| PAYMENT | POST `/api/pagos` | `push_orchestrator.dart` |
| REVERSAL | POST `/api/pagos/{server_payment_id}/reversar` | `push_orchestrator.dart` |
| MOVIMIENTO | POST `/api/movimientos` | `push_orchestrator.dart` |
| JORNADA_CIERRE | POST `/api/jornadas/{id}/cerrar` → POST `/api/jornadas/{id}/sincronizar` | `push_orchestrator.dart` |

### Semántica de estados

| Estado | Significado |
|---|---|
| `PENDIENTE_DE_SINCRONIZAR` | Fila nueva, lista para push |
| `ENVIANDO` | Push en progreso (protege contra doble push) |
| `SINCRONIZADO` | ACK del servidor recibido (200/201), `server_entity_id` guardado |
| `ERROR_REINTENTABLE` | Error transitorio (401, 5xx), se reintentará |
| `CONFLICTO` | Error no reintentable (409 mismatch, 400, 403, 404, 422) |

### Comportamientos documentados

- **PAYMENT/REVERSAL** — usan mapping local↔server: REVERSAL requiere `server_payment_id` (no local ID) para construir URL del reverso.
- **Retry** — conserva misma `idempotency_key`, mismo payload, misma provenance.
- **Lost response** — si servidor commitó pero móvil no recibió ACK, retry idempotente devuelve 200 (idempotente) → converge a SINCRONIZADO.
- **401** — preserva fila en outbox (ERROR_REINTENTABLE), no borra.
- **409 mismatch** — idempotency key existe pero payload distinto → CONFLICTO (no reintentable).
- **409 "ya cerrada"** — jornada_cierre: re-intenta con `/sincronizar` directo.
- **ENVIANDO abandonado** — recupera LA MISMA fila (no INSERT nueva), retransmite.
- **R1→R2** — fila con `ruta_id_origen=R1` no se transmite bajo R2 → CONFLICTO. 0 requests HTTP.
- **Jornada dependencies** — JORNADA_CIERRE espera PAYMENT/REVERSAL de misma jornada ACKeados.
- **CLOSED_LOCAL_PENDING_SYNC → CLOSED_SYNCED** — solo tras ACK válido de `/sincronizar`.
- **Pull posterior** — reconcilia server_entity_id, evita duplicados.

### No afirmar

- Que todos los 409 son conflicto.
- Que todos los 409 son ACK.
- Que existe endpoint batch.
- Que existe PowerSync.
- Que PG pasó si no se ejecutó.

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
- En S3, el push reutiliza estas idempotency keys existentes. 409 mismatch → CONFLICTO (no reintentable). 409 match → 200 idempotente → SINCRONIZADO.