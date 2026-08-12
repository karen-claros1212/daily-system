# Phase 0 — Answers to 18 Baseline Questions
## Read-only audit of actual code (no assumptions)

---

### Q1. Schema exacto actual de `sync_queue`

**Tabla:** `sync_queue` (creada por MigrationV2, v2 DB)
```sql
CREATE TABLE IF NOT EXISTS sync_queue (
  id TEXT PRIMARY KEY,
  tipo TEXT NOT NULL,
  entidad_id TEXT NOT NULL,
  datos TEXT NOT NULL,
  creado_el TEXT NOT NULL,
  estado TEXT DEFAULT 'PENDIENTE_DE_SINCRONIZAR'
)
```
- 6 columnas, sin índices adicionales, sin foreign keys
- `id` = UUID generado por `uid()` (Uuid.v4())
- `datos` = TEXT (JSON o Map.toString())
- `estado` = TEXT, valor por defecto `'PENDIENTE_DE_SINCRONIZAR'`
- No hay columnas: `idempotency_key`, `negocio_id`, `ruta_id`, `cobrador_id`, `jornada_id`, `intento`, `ultimo_error`, `ultima_transicion`, `server_entity_id`

---

### Q2. Estados existentes

Solo 2 estados en uso actual:
- `'PENDIENTE_DE_SINCRONIZAR'` (valor por defecto, filas nuevas)
- `'SINCRONIZADO'` (set por `marcarSincronizado()`)

Filas con estado `'SINCRONIZADO'` se limpian con `limpiarSincronizados()` (DELETE).

**NO existen:** `'ENVIANDO'`, `'ERROR_REINTENTABLE'`, `'CONFLICTO'`

---

### Q3. ¿Quién encola PAYMENT?

**`PagoService.registrarPago()`** — `apps/mobile/lib/services/pago_service.dart:85-89`

```dart
await _insertSyncQueue(txn, 'pago', pago.id, {
  'tipo': 'PAYMENT',
  'monto': monto,
  'credito_id': creditoId,
});
```
- Dentro de la misma transacción SQLite que INSERT en tabla `pago`
- Usa `_insertSyncQueue()` helper (no `SyncQueueService.enqueue()`)
- Payload: solo `tipo`, `monto`, `credito_id`

---

### Q4. ¿Quién encola REVERSAL?

**`PagoService.reversarPago()`** — `apps/mobile/lib/services/pago_service.dart:169-173`

```dart
await _insertSyncQueue(txn, 'pago', reversal.id, {
  'tipo': 'REVERSAL',
  'monto': pagoOriginal.monto,
  'reversal_of_payment_id': pagoId,
});
```
- idempotency key: `_uuid.v4()` (generada en línea 135, no persistida en sync_queue)
- Payload: solo `tipo`, `monto`, `reversal_of_payment_id`

---

### Q5. ¿Quién encola MOVIMIENTO?

**`MovimientoService.registrarMovimiento()`** — `apps/mobile/lib/services/movimiento_service.dart:55-62`

```dart
await txn.insert('sync_queue', {
  'id': uid(),
  'tipo': 'movimiento',
  'entidad_id': id,
  'datos': jsonEncode({'tipo': tipo, 'monto': monto, 'nota': nota}),
  'creado_el': now,
  'estado': 'PENDIENTE_DE_SINCRONIZAR',
});
```
- idempotency key: `id = _uuidMov.v4()` (UUID del movimiento)
- Payload: solo `tipo`, `monto`, `nota`
- **NO guarda:** `jornada_id`, `negocio_id`, `cobrador_id`, `clave_idempotencia`

---

### Q6. ¿Quién encola JORNADA_CIERRE?

**`JornadaService.cerrarJornada()`** — `apps/mobile/lib/services/jornada_service.dart:104-111`

```dart
await txn.insert('sync_queue', {
  'id': uid(),
  'tipo': 'jornada_cierre',
  'entidad_id': jornadaId,
  'datos': jsonEncode({'contado': contado, 'esperado': caja.efectivoEsperado, 'diferencia': diferencia}),
  'creado_el': now,
  'estado': 'PENDIENTE_DE_SINCRONIZAR',
});
```
- Payload: solo `contado`, `esperado`, `diferencia`
- **NO guarda:** `idempotencia_cierre`, `jornada_id` (solo entidad_id), `negocio_id`, `ruta_id`, `cobrador_id`, `snapshot`, `pagos_ids`, `reversales_ids`, `movimientos_ids`

---

### Q7. Contenido exacto actual de `datos`

| Tipo | Contenido |
|---|---|
| PAYMENT | `{'tipo': 'PAYMENT', 'monto': <int>, 'credito_id': '<uuid>'}` |
| REVERSAL | `{'tipo': 'REVERSAL', 'monto': <int>, 'reversal_of_payment_id': '<uuid>'}` |
| MOVIMIENTO | `{'tipo': '<tipo>', 'monto': <int>, 'nota': '<string>'}` |
| JORNADA_CIERRE | `{'contado': <int>, 'esperado': <int>, 'diferencia': <int>}` |

**Problemas detectados:**
- PAYMENT no tiene `jornada_id` ni `cobrador_id` ni `clave_idempotencia` ni `nota`
- REVERSAL no tiene `jornada_id` ni `cobrador_id` ni `clave_idempotencia` ni `motivo`
- MOVIMIENTO no tiene `jornada_id` ni `negocio_id` ni `cobrador_id` ni `clave_idempotencia` ni `naturaleza`
- JORNADA_CIERRE no tiene `idempotencia_cierre` ni `snapshot` ni `pagos_ids` ni `reversales_ids` ni `movimientos_ids`

---

### Q8. ¿Cómo se genera hoy cada idempotency key?

| Tipo | Generación | Persistida en sync_queue? |
|---|---|---|
| PAYMENT | `clienteIdempotenciaClave` (parámetro de `registrarPago()`) | NO — solo en tabla `pago.clave_idempotencia` |
| REVERSAL | `_uuid.v4()` (línea 135 de pago_service.dart) | NO — solo en tabla `pago.clave_idempotencia` |
| MOVIMIENTO | `id = _uuidMov.v4()` (UUID del movimiento) | NO — sync_queue usa `entidad_id` como referencia |
| JORNADA_CIERRE | `uid()` (UUID generado en cerrarJornada) | NO — solo en sync_queue.id |

---

### Q9. ¿Esa key ya se persiste o se regenera?

**En tabla `pago`:** Sí, `clave_idempotencia TEXT NOT NULL UNIQUE` existe.
**En sync_queue:** NO — no column `idempotency_key`. La clave se pierde cuando se sincroniza y se limpia.

---

### Q10. ¿El ID local del evento puede ser utilizado por el backend?

**Sí.** El backend acepta pagos/movimientos con IDs generados por el cliente:
- `register_payment()` genera `id=__import__("uuid").uuid4()` (nuevo UUID en servidor)
- `register_movimiento()` genera `id=uuid4()` (nuevo UUID en servidor)
- Los IDs del cliente se pierden — el servidor genera los suyos propios

**No hay mapping entre ID local y ID servidor.**

---

### Q11. ¿El backend genera un ID diferente?

**Sí, siempre.** En cada endpoint POST:
- `Pago(id=__import__("uuid").uuid4())` — línea 185 de payment_service.py
- `MovimientoCaja(id=uuid4())` — línea 287 de movimiento_service.py
- `Jornada(id=uuid4())` — línea 179 de jornada_service.py

El ID local del dispositivo NUNCA se transmite al servidor ni se usa allí.

---

### Q12. ¿Cómo se correlacionará `local_entity_id ↔ server_entity_id`?

**Opción A (recomendada):** Transmitir la idempotency key del cliente al backend. El backend busca por `clave_idempotencia` y devuelve el registro existente (idempotente).

**Opción B:** Transmitir `local_entity_id` en el payload y que el backend lo almacene como columna `local_id` para correlación posterior.

**Opción C (actual):** El pull del servidor trae los datos por `jornada_id` + `credito_id` + `monto` + `cobrador_id`. El cliente correlaciona por estos campos.

---

### Q13. ¿Cómo una reversión pendiente referencia al pago original si el servidor usa otro ID?

Actualmente:
- `reversal_of_payment_id` en `pago` apunta al **ID local** del pago original
- El pull del servidor trae `reversal_of_payment_id` como UUID del servidor
- Si el servidor genera un ID diferente, la referencia se rompe

**Solución:** Transmitir `reversal_of_payment_id` como `credito_id` + `jornada_id` + `monto` en el payload de REVERSAL, y que el backend resuelva por idempotencia.

---

### Q14. Contrato exacto de 409 por endpoint

**Pago (payment_service.py:80-113):**
```
409 = PaymentIdempotencyError
  - "Misma clave de idempotencia con tipo diferente" (clave existe pero tipo != PAYMENT)
  - "Misma clave de idempotencia con payload diferente" (credito_id/monto/jornada_id difiere)
  - Si payload idéntico → devuelve existente (200 implícito)
```

**Movimiento (movimiento_service.py:266-284):**
```
409 = MovimientoIdempotencyError
  - "Misma clave de idempotencia con payload diferente"
  - Compara: tipo, naturaleza, monto, jornada_id, nota, credito_id, renovacion_id, ajuste_de_movimiento_id
  - Si payload idéntico → devuelve existente (200 implícito)
```

**Jornada (jornada_service.py:294-342):**
```
409 = JornadaAlreadyClosed
  - "Misma clave de idempotencia con payload diferente"
  - Compara: efectivo_contado, motivo, version
  - Si payload idéntico → devuelve cierre existente (200 implícito)
  - "Jornada ya cerrada" (si estado en CLOSED_LOCAL_PENDING_SYNC o CLOSED_SYNCED)
  - "Solo se puede cerrar una jornada OPEN" (si estado != OPEN)
```

---

### Q15. Flujo exacto de `/cerrar` + `/sincronizar` de jornada

**POST `/api/jornadas/{jornada_id}/cerrar`** (jornada_service.py:257-466):
1. Valida jornada existe y pertenece al negocio
2. Valida cobrador ruta (si es cobrador)
3. Obtiene `idempotencia_cierre` del data
4. Check idempotencia: si misma clave + mismo payload → devuelve existente
5. Valida estado = OPEN (si no → 409)
6. Transiciona a CLOSING → recalcula caja → valida consistency
7. Transiciona directamente a CLOSED_SYNCED
8. Guarda snapshot JSON + hash
9. Calcula sobrante_manana

**POST `/api/jornadas/{jornada_id}/sincronizar`** (jornada_service.py:502-692):
1. Valida jornada existe y pertenece al negocio
2. Valida estado en {CLOSED_LOCAL_PENDING_SYNC, CLOSED_SYNCED}
3. Compara snapshot hash (canonical JSON)
4. Compara snapshot almacenado vs recibido (JSON canónico idéntico)
5. Compara IDs: jornada_id, negocio_id, ruta_id, cobrador_id, version
6. Compara valores financieros: efectivo_esperado, diferencia, motivo
7. Compara IDs de eventos: pagos_ids, reversales_ids, movimientos_ids, renovaciones_ids
8. Si no hay snapshot almacenado (sin cerrar por servidor): reconstruye desde eventos
9. Valida server_caja == client_snapshot
10. Transiciona a CLOSED_SYNCED
11. Actualiza sincronizada_el

---

### Q16. ¿Dónde está disponible la ruta activa server-derived en el cliente?

**`BootstrapIdentity`** — `apps/mobile/lib/auth/models.dart:115-153`
- `rutaId` — UUID de la ruta activa
- `rutaVersion` — versión de la ruta (para detectar R1→R2)
- `versionAsignacion` — versión de asignación del dispositivo

**`SyncDataset`** — `apps/mobile/lib/sync/sync_models.dart`
- `rutaId` — echo del servidor
- `rutaVersion` — echo del servidor

**`SyncRepository.limpiarDatosDeRuta()`** protege contra limpieza si hay outbox pendiente.

**No hay selector de rutas en mobile.** La ruta se obtiene de:
1. `BootstrapIdentity.rutaId` (post-bootstrap)
2. `SyncDataset.rutaId` (post-sync)

---

### Q17. ¿Qué información debe conservarse para bloquear R1 bajo una sesión R2?

Necesario:
- `ruta_id_origen` en sync_queue.row (para comparar con ruta actual)
- `negocio_id_origen` en sync_queue.row
- `cobrador_id_origen` en sync_queue.row
- `jornada_id` en sync_queue.row (para verificar jornada pertenece a la ruta correcta)
- `ruta_version` en BootstrapIdentity (detectar cambio)

**Regla:** Si `sync_queue.ruta_id_origen != ruta_actual`, NO enviar. Marcar como `CONFLICTO`.

---

### Q18. Orden necesario entre eventos de una misma jornada

1. Todos los PAYMENT de la jornada deben ACK antes de JORNADA_CIERRE
2. Todos los REVERSAL de la jornada deben ACK antes de JORNADA_CIERRE
3. Todos los MOVIMIENTO de la jornada deben ACK antes de JORNADA_CIERRE
4. JORNADA_CIERRE con `idempotencia_cierre` idéntico es idempotente
5. JORNADA_CIERRE con snapshot hash idéntico es idempotente

**Orden determinístico:**
1. ORDER BY creado_el ASC, id ASC
2. Dentro de misma jornada: PAYMENT primero, luego REVERSAL, luego MOVIMIENTO, luego JORNADA_CIERRE

---

# PHASE 0 RESUME

## Hallazgos críticos

1. **sync_queue tiene solo 6 columnas** — necesita evolucionar para S3
2. **Solo 2 estados existentes** — necesita ENVIANDO, ERROR_REINTENTABLE, CONFLICTO
3. **Payloads incompletos** — no tienen jornada_id, cobrador_id, ruta_id, idempotency_key
4. **Idempotency key no se persiste en sync_queue** — se pierde al sincronizar
5. **Backend genera IDs propios** — mapping local↔server necesario
6. **Jornada payload mínimo** — solo 3 campos, sin snapshot ni IDs de eventos
7. **Movimiento payload mínimo** — sin jornada_id ni naturaleza

## Próximos pasos

- Phase 1: Evolucionar sync_queue con migración compatible (v5)
- Phase 2: Completar payloads en cada productor de eventos
- Phase 3: Implementar push orchestrator
- Phase 4: Mapear HTTP → estados
