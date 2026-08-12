# DAILY SYSTEM — S3 EXECUTION PACK
## Outbox real · Push · ACK · Retry · Conflictos

**Fecha:** 2026-08-11  
**Repositorio:** `karen-claros1212/daily-system`  
**Checkout canónico:** `/home/jesus/proyectos/daily-system`  
**Rama de trabajo:** `hardening/b1-b7-audit`  
**HEAD remoto verificado al iniciar este bloque:** `5708420617e72b429bebcf59c7d6b1251153c096`  
**Baseline de código S0-S2:** `c0a3a9c1646358fea4badc45bc9cdf5d6e2a1216`  
**master:** `486d08b1584684a4328825142209776fce477670` — NO tocar.

---

# 1. OBJETIVO

Completar **S3 — outbox móvil → servidor**, conectando las operaciones offline que ya existen con los endpoints financieros productivos existentes.

S3 queda terminado únicamente cuando exista evidencia reproducible de:

- outbox persistente y recuperable;
- payload completo y estable;
- clave de idempotencia generada una sola vez y conservada;
- procedencia de negocio/cobrador/ruta/jornada conservada;
- push de PAYMENT;
- push de REVERSAL;
- push de MOVIMIENTO;
- cierre/sincronización de JORNADA;
- ACK solo después de confirmación válida del servidor;
- retry con el mismo payload y la misma idempotency key;
- recuperación tras corte de red o reinicio;
- 401 sin pérdida del outbox;
- 409 real tratado como conflicto, no como sobrescritura;
- R1 → R2 sin reetiquetar ni enviar eventos de R1 bajo R2;
- `CLOSED_LOCAL_PENDING_SYNC → CLOSED_SYNCED` solamente después del ACK correcto;
- pruebas completas verdes;
- documentación reconciliada.

**No renombrar S3 a S4.**

---

# 2. ESTADO YA CERRADO — NO REABRIR SIN EVIDENCIA

| Bloque | Estado |
|---|---|
| B1-B7 hardening | PASS |
| Activación productiva | PASS |
| AndroidKeyStore EC P-256 | PASS |
| Challenge-response | PASS |
| JWT ES256 | PASS |
| Device binding | PASS |
| Bootstrap productivo single-route | PASS |
| Mobile auth bridge | PASS |
| S0 — session maintenance | PASS |
| S1 — route isolation | PASS |
| S2 — pull + SQLite persistence | PASS |
| DOC-SYNC | PASS remoto |

No reconstruir estas capas para implementar S3.

---

# 3. INVARIANTES NO NEGOCIABLES

1. **No rehacer el proyecto.** Cambios estrechos; preservar arquitectura existente.
2. **Reutilizar `sync_queue`.** No crear otra outbox paralela. No introducir PowerSync.
3. **Backend = autoridad financiera.** No duplicar reglas monetarias ni resolver conflictos sobrescribiendo al servidor.
4. **Hoja Viva se preserva.** No rediseñar pantallas ni cambiar fórmulas.
5. **No bot/chat/asistente en mobile.**
6. **Rutas dinámicas.** El servidor deriva el scope; el móvil no selecciona libremente la ruta.
7. **Eventos financieros append-only y trazables.**
8. **Idempotencia estable.** La clave se crea una sola vez; retry = misma clave + mismo request semántico.
9. **No reescribir migraciones ya aplicadas.** Si `sync_queue` necesita evolución, usar la siguiente migración compatible.
10. **No asumir SQLite vacía.** Preservar instalaciones existentes.
11. **No `INSERT OR REPLACE` en datos financieros.**
12. **No master / merge / tag / deploy / restart.**
13. **No golden regeneration sin autorización separada.**
14. **No commit ni push hasta revisión.**

---

# 4. PHASE 0 — BASELINE Y AUDITORÍA READ-ONLY

Antes de editar:

```bash
cd /home/jesus/proyectos/daily-system
pwd
git rev-parse --show-toplevel
git branch --show-current
git rev-parse HEAD
git status --short
git log --oneline -8
git rev-parse origin/hardening/b1-b7-audit
git rev-parse origin/master
```

Debe cumplirse:

- checkout = `/home/jesus/proyectos/daily-system`;
- branch = `hardening/b1-b7-audit`;
- HEAD esperado = `5708420617e72b429bebcf59c7d6b1251153c096` o descendiente conocido;
- working tree limpio;
- no cambios desconocidos.

## 4.1 Leer el código real antes de diseñar

### Mobile
- `apps/mobile/lib/database/`
- migraciones SQLite existentes;
- definición actual de `sync_queue`;
- `apps/mobile/lib/services/sync_queue_service.dart`
- `apps/mobile/lib/services/pago_service.dart`
- `apps/mobile/lib/services/movimiento_service.dart`
- `apps/mobile/lib/services/jornada_service.dart`
- `apps/mobile/lib/sync/`
- `apps/mobile/lib/auth/`
- modelos Pago / Movimiento / JornadaSnapshot;
- triggers financieros;
- pruebas existentes de sync, pago, movimiento, jornada y auth.

### Backend
- `apps/api/src/routes/pago.py`
- `apps/api/src/routes/movimiento.py`
- `apps/api/src/routes/jornada.py`
- schemas reales de `PagoCreate`, `PagoReversalCreate`, `MovimientoCreate`, `JornadaCierreCreate` y sincronización;
- `payment_service.py`
- `movimiento_service.py`
- `jornada_service.py`
- contexto auth / route isolation;
- tests de idempotencia y sync.

## 4.2 Responder antes de implementar

Dejar documentado en notas de trabajo:

1. schema exacto actual de `sync_queue`;
2. estados existentes;
3. quién encola PAYMENT;
4. quién encola REVERSAL;
5. quién encola MOVIMIENTO;
6. quién encola JORNADA_CIERRE;
7. contenido exacto actual de `datos`;
8. cómo se genera hoy cada idempotency key;
9. si esa key ya se persiste o se regenera;
10. si el ID local del evento puede ser utilizado por el backend;
11. si el backend genera un ID diferente;
12. cómo se correlacionará `local_entity_id ↔ server_entity_id`;
13. cómo una reversión pendiente referencia al pago original si el servidor usa otro ID;
14. contrato exacto de 409 por endpoint;
15. flujo exacto de `/cerrar` + `/sincronizar` de jornada;
16. dónde está disponible la ruta activa server-derived en el cliente;
17. qué información debe conservarse para bloquear R1 bajo una sesión R2;
18. orden necesario entre eventos de una misma jornada.

No implementar por suposición.

---

# 5. PHASE 1 — EVOLUCIÓN DEL OUTBOX EXISTENTE

## 5.1 No crear una segunda cola

Evolucionar `sync_queue` mediante la siguiente migración compatible con el repositorio.

El modelo final debe poder conservar como mínimo:

- identificador estable de la fila de outbox;
- `tipo`;
- `entidad_id` local;
- payload JSON real y parseable;
- clave de idempotencia original;
- `negocio_id` de origen;
- `ruta_id` de origen;
- `cobrador_id` de origen cuando aplique;
- `jornada_id` cuando aplique;
- fecha/hora de creación;
- estado;
- número de intentos;
- último error;
- timestamp de última transición si el diseño real lo necesita;
- mapping a `server_entity_id` **solo si el audit demuestra que los IDs local/server no son iguales**.

No añadir columnas decorativas.

## 5.2 Payload

**Prohibido:** `datos.toString()`.

Usar JSON (`jsonEncode` / `jsonDecode`) y conservar el request necesario para reconstruir el envío sin consultar ni recalcular datos mutables.

El outbox debe almacenar el **envelope original**, no una referencia incompleta para reconstruirlo después.

Retry debe reconstruir exactamente los mismos campos semánticos enviados originalmente. Para jornada, conservar los campos exactos que intervienen en hash/snapshot canónico.

## 5.3 Estados

Implementar un modelo equivalente a:

```text
PENDIENTE_DE_SINCRONIZAR
        ↓
     ENVIANDO
      ↙   ↘
SINCRONIZADO   ERROR_REINTENTABLE
                  ↓
               ENVIANDO

conflicto permanente probado
        ↓
     CONFLICTO
```

Reglas:

- `ENVIANDO` nunca significa “ya se envió”.
- Reinicio con `ENVIANDO` debe ser recuperable.
- `SINCRONIZADO` es terminal para esa fila.
- `ERROR_REINTENTABLE` conserva payload, key y procedencia.
- `CONFLICTO` conserva toda la evidencia; no borra ni reescribe historia.

## 5.4 Filas legacy

No asumir que no existen filas antiguas.

Si una fila histórica tiene `datos` en formato Dart `Map.toString()` y no puede reconstruirse de forma segura:

- NO inventar JSON;
- NO generar una idempotency key nueva;
- NO enviarla con datos adivinados;
- conservarla y clasificarla explícitamente como conflicto/legacy no recuperable;
- dejar evidencia del motivo.

---

# 6. PHASE 2 — PRODUCCIÓN ATÓMICA DE EVENTOS

Cada operación offline debe crear su fila de `sync_queue` **en la misma transacción SQLite** en la que registra el evento financiero correspondiente.

Si falla la escritura del outbox, debe fallar la operación completa cuando esa atomicidad sea necesaria para garantizar que ningún evento financiero quede sin posibilidad de sincronizar.

## 6.1 PAYMENT

Al registrar el pago local:

- generar `clave_idempotencia` una sola vez;
- persistirla con el pago y/o envelope según el modelo real;
- guardar el request completo requerido por `POST /api/pagos`;
- guardar procedencia y jornada;
- no recalcular monto/tipo/crédito al enviar;
- no regenerar timestamp ni clave durante retry.

## 6.2 REVERSAL

Al reversar offline:

- generar su idempotency key una sola vez;
- persistir `reversal_of_payment_id`;
- conservar la relación con el pago original;
- si backend requiere ID servidor del pago original y el local difiere, resolver mediante mapping probado;
- nunca apuntar a un pago distinto.

Si el pago original todavía está pendiente, la reversión no puede salir antes de que exista el pago original en el servidor.

## 6.3 MOVIMIENTO

Persistir el request completo para `POST /api/movimientos`.

Mantener jornada, tipo, monto, nota, timestamp, idempotency key y procedencia local necesaria. La `naturaleza` sigue bajo autoridad del backend según el contrato ya endurecido.

## 6.4 JORNADA_CIERRE

La fila de cierre debe conservar un envelope inmutable suficiente para completar el flujo de servidor sin recalcular:

- identificación de jornada;
- datos de cierre;
- snapshot exacto;
- `idempotencia_cierre`;
- IDs de eventos incluidos;
- hash/datos canónicos requeridos;
- procedencia;
- request necesario para `/cerrar`;
- request necesario para `/sincronizar`.

`CLOSED_LOCAL_PENDING_SYNC` se mantiene hasta confirmación válida del servidor.

---

# 7. PHASE 3 — PUSH ORCHESTRATOR

Implementar el envío dentro de la arquitectura actual de `lib/sync/` / servicios existentes. No crear otro subsistema paralelo.

## 7.1 Auth

Reutilizar:

- `AuthHttpClient`;
- `DeviceAuthClient`;
- `AuthTokenStore`;
- renovación S0.

No crear refresh token. No crear segundo cliente HTTP de auth. No modificar JWT/Keystore salvo incompatibilidad demostrada.

## 7.2 Orden

Procesar de forma determinística:

1. orden estable por creación + id;
2. pago antes de su reversión;
3. eventos financieros de una jornada antes de su cierre;
4. JORNADA_CIERRE no puede marcarse sincronizada mientras existan eventos previos de esa jornada sin ACK.

No depender solo de “se insertaron primero”; probar dependencias.

## 7.3 Route provenance — R1 → R2

La fila debe recordar la ruta de origen.

Antes de transmitir:

- obtener la ruta operativa actual desde el contexto ya autorizado/servidor;
- comparar contra `ruta_id_origen`;
- si difiere: NO enviar, NO reemplazar `ruta_id_origen`, NO editar payload para R2, NO borrar fila;
- llevarla a un estado determinístico de conflicto/bloqueo con evidencia.

No crear selector de rutas en mobile para “resolverlo”.

## 7.4 Estado ENVIANDO

Antes del request:

- transición persistente a `ENVIANDO`;
- incrementar intentos de manera coherente;
- conservar payload/key.

Si el proceso muere después de esto:

```text
ENVIANDO abandonado
→ recuperable
→ ERROR_REINTENTABLE o PENDIENTE
→ mismo request / misma key
```

---

# 8. PHASE 4 — MAPPING HTTP → ESTADO OUTBOX

## 8.1 2xx

Solo considerar ACK cuando:

- el endpoint respondió éxito;
- la respuesta pertenece al recurso esperado;
- la semántica confirma registro/idempotent replay correcto;
- no existe mismatch de identidad.

Después: `ENVIANDO → SINCRONIZADO`.

## 8.2 Response lost

Caso obligatorio:

```text
cliente envía
→ servidor COMMIT
→ respuesta se pierde
→ cliente reintenta
→ MISMA key + MISMO payload
→ backend devuelve existente/idempotent result
→ ACK
→ cero duplicados
```

## 8.3 Network / timeout / 5xx

`ENVIANDO → ERROR_REINTENTABLE`.

Conservar fila, payload, key y ruta. No generar duplicado. La política temporal/backoff se define durante S3 solo si es necesaria; no está congelada previamente.

## 8.4 401

- limpiar sesión usando el flujo existente;
- conservar outbox completo;
- detener ciclo actual;
- NO reinterpretar el evento bajo otra ruta;
- tras nueva sesión, volver a validar procedencia antes de enviar.

## 8.5 409

**No implementar `409 = éxito` global.** Clasificar por endpoint usando el contrato real.

### Pago / Movimiento
- replay idéntico debe converger según la idempotencia backend;
- 409 de payload diferente = `CONFLICTO`.

### Jornada
Si retry recibe “ya cerrada”:
- no asumir éxito ciego;
- verificar estado/resultado según contrato real;
- continuar a `/sincronizar` únicamente si estado servidor y snapshot corresponden.

Snapshot diferente / mismatch:
- `CONFLICTO`;
- preservar evidencia.

## 8.6 Otros 4xx permanentes

400 / 403 / 404 / 422 no deben reintentarse infinitamente. Clasificar como terminal/conflicto cuando el mismo request no pueda tener éxito sin intervención. No modificar dinero local para “hacer que pase”.

---

# 9. PHASE 5 — IDENTIDAD LOCAL ↔ SERVIDOR

Determinar con evidencia:

```text
¿Pago local usa el mismo UUID que el servidor?
¿Movimiento local usa el mismo UUID que el servidor?
¿Backend acepta client-generated IDs?
¿Backend genera un ID diferente?
```

Si existe diferencia:

- implementar mapping explícito y persistente;
- no cambiar IDs locales a ciegas si hay FKs/reversal links;
- ACK debe almacenar ID servidor cuando sea necesario;
- reversal debe usar el ID servidor correcto;
- pull posterior no debe duplicar el evento ya sincronizado.

Prueba obligatoria:

```text
pago offline local
→ push
→ ACK
→ pull posterior
→ una sola representación lógica
→ reversal_of_payment_id sigue apuntando al pago correcto
```

Si el contrato permite usar directamente IDs cliente-servidor, demostrarlo y no añadir mapping innecesario.

---

# 10. PHASE 6 — JORNADA: CIERRE + SINCRONIZAR

1. Push de pagos/reversos/movimientos previos de esa jornada primero.
2. Usar datos de cierre almacenados al cerrar localmente.
3. No recalcular snapshot en el envío.
4. No generar nueva `idempotencia_cierre`.
5. Ejecutar el flujo backend real: `/cerrar` cuando corresponda y `/sincronizar` con snapshot/idempotencia exactos.
6. Si una respuesta se pierde, retry debe converger.
7. `CLOSED_LOCAL_PENDING_SYNC` solo cambia con confirmación válida.
8. Solo después: jornada → `CLOSED_SYNCED`; queue row → `SINCRONIZADO`.
9. Mismatch hash/snapshot → `CONFLICTO`; no reabrir ni sobreescribir snapshot.

---

# 11. TEST MATRIX OBLIGATORIA

## Migración / outbox
- upgrade desde DB existente;
- datos financieros preservados;
- filas legacy preservadas;
- JSON nuevo roundtrip;
- no `Map.toString()`;
- estados nuevos válidos;
- restart con `ENVIANDO`;
- migración no reescribe v2/v3/v4.

## PAYMENT
- pago offline → queue;
- payload completo + key original;
- push → ACK;
- retry idéntico → cero duplicado;
- network antes de commit;
- server commit + response lost;
- 409 mismatch → conflicto;
- 401 conserva fila.

## REVERSAL
- pago conocido por server → reversal offline → ACK;
- pago local pendiente → payment primero → reversal después;
- relación original preservada;
- mapping ID correcto si aplica;
- response lost + retry;
- doble reversal bloqueado según reglas existentes.

## MOVIMIENTO
- offline → push → ACK;
- misma key/payload en retry;
- no duplicate;
- server-derived naturaleza intacta;
- conflicto payload mismatch.

## JORNADA
- cierre local → `CLOSED_LOCAL_PENDING_SYNC`;
- no sincroniza con eventos previos pendientes;
- close/sync servidor;
- snapshot exacto;
- misma `idempotencia_cierre`;
- ACK válido → `CLOSED_SYNCED`;
- response lost + retry;
- snapshot mismatch → conflicto;
- no reapertura silenciosa.

## AUTH / ROUTE
- 401 limpia sesión y conserva outbox;
- nueva auth misma ruta → retry válido;
- R1 pending + reassignment R2 → jamás enviado como R2;
- `ruta_id_origen` nunca muta;
- no cross-route visibility.

## Integración S2 ↔ S3
- push ACK → pull posterior;
- no duplicate;
- no overwrite de pending;
- no pérdida de reversal link;
- no corrupción de cuotas;
- no trigger perdido tras error.

---

# 12. GATES

## Mobile

```bash
cd /home/jesus/proyectos/daily-system/apps/mobile
flutter analyze
flutter test
```

Si existe test Android instrumentado relevante y el entorno está disponible, ejecutarlo. No regenerar goldens.

## Backend

```bash
cd /home/jesus/proyectos/daily-system/apps/api
python3 -m pytest src/tests/ -q
python3 -m alembic check
```

Ejecutar además PostgreSQL relevante para idempotencia, concurrencia y transacciones financieras usando solamente DB scratch/test bajo las protecciones existentes.

## Repository

```bash
cd /home/jesus/proyectos/daily-system
git diff --check
git status --short
git diff --stat
git diff --name-only
```

---

# 13. DOCUMENTACIÓN — GATE DE CIERRE

Si y solo si S3 pasa los gates, actualizar como mínimo:

- `docs/OFFLINE-SYNC.md`
- `docs/STATUS.md`
- `CHANGELOG.md`
- `DAILY-SYSTEM-CONTEXT-HANDOFF.md`

Actualizar también README/ARCHITECTURE/SECURITY/TESTING si el contrato correspondiente cambia.

Reglas:

- no hardcodear un HEAD autorreferencial;
- Git es autoridad para HEAD actual;
- conservar `c0a3a9c` como baseline histórico S0-S2 donde sea útil;
- S3 solo se marca PASS con evidencia real;
- tests locales ≠ GitHub CI;
- actualizar Engram/handoff al cierre.

---

# 14. STOP CONDITIONS

Detenerse y reportar antes de ampliar alcance si:

1. se requiere cambiar JWT/claims/protocolo auth;
2. se requiere reemplazar AndroidKeyStore;
3. se requiere reescribir Hoja Viva;
4. se requiere cambiar fórmulas financieras;
5. se requiere migración destructiva;
6. se requiere editar una migración ya aplicada;
7. se requiere un endpoint nuevo que replique lógica financiera;
8. el mapping de IDs exige reescritura masiva de PK/FK;
9. aparecen cambios locales ajenos;
10. una prueba existente solo puede pasar debilitándola.

No ocultar el problema con un parche.

---

# 15. DEFINICIÓN DE DONE

```text
[ ] sync_queue evolucionada, no duplicada
[ ] payload JSON completo
[ ] idempotency key estable
[ ] provenance estable
[ ] PAYMENT push/ACK
[ ] REVERSAL push/ACK
[ ] MOVIMIENTO push/ACK
[ ] JORNADA close/sync/ACK
[ ] response-lost convergence
[ ] restart ENVIANDO
[ ] 401 preserves outbox
[ ] 409 mismatch → conflicto
[ ] R1→R2 safe
[ ] local↔server ID mapping probado
[ ] pull posterior sin duplicado
[ ] CLOSED_SYNCED solo tras ACK
[ ] no Hoja Viva/formula regression
[ ] flutter analyze PASS
[ ] flutter test PASS
[ ] backend pytest PASS
[ ] PG tests relevantes PASS
[ ] alembic check PASS si backend schema tocado
[ ] git diff --check PASS
[ ] documentación reconciliada
[ ] Engram/handoff actualizado
```

---

# 16. REPORTE OBLIGATORIO ANTES DE COMMIT

Entregar:

### A. Baseline
- branch;
- HEAD de inicio;
- working tree inicial.

### B. Arquitectura S3 final
- componentes añadidos/modificados;
- flujo de ejecución;
- por qué no se creó una segunda outbox.

### C. Schema `sync_queue`
- antes;
- después;
- migración;
- estrategia legacy.

### D. Mapping por tipo

| Tipo queue | Endpoint | Path params | Body | Idempotency key | ACK validation |
|---|---|---|---|---|---|
| PAYMENT | | | | | |
| REVERSAL | | | | | |
| MOVIMIENTO | | | | | |
| JORNADA_CIERRE | | | | | |

### E. State machine
- transiciones;
- recovery;
- 401;
- 409;
- network/5xx;
- route mismatch.

### F. IDs
- local ID;
- server ID;
- mapping;
- reversal relationship.

### G. R1→R2
- prueba exacta;
- evidencia de no reetiquetado.

### H. Tests
- comando;
- passed/failed/skipped;
- SQLite/PG separados;
- local vs CI separados.

### I. Files
- modificados;
- creados;
- eliminados.

### J. Git

```bash
git diff --stat
git status --short
git diff --check
```

### K. Debt / riesgos
- deuda restante;
- decisiones pendientes.

---

# 17. PROHIBIDO AL FINAL

**NO COMMIT.**  
**NO PUSH.**  
**NO MERGE.**  
**NO TAG.**  
**NO DEPLOY.**  
**NO SERVICE RESTART.**

Esperar revisión y autorización después del reporte final.

---

# 18. SIGUIENTE BLOQUE

No empezar automáticamente. Primero cerrar S3 con evidencia.

Después de S3, la reasignación avanzada y política de conflictos debe preservar:

- procedencia histórica;
- outbox pendiente;
- server-derived route scope;
- JWT/device binding;
- autoridad financiera del backend.

--- End of file ---
