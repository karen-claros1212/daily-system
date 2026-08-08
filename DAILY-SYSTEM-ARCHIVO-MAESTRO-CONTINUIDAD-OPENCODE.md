# DAILY SYSTEM — ARCHIVO MAESTRO DE CONTINUIDAD PARA OPENCODE

> Este archivo no vuelve a explicar qué es Daily System ni repite la estructura del repositorio.  
> OpenCode ya conoce el proyecto, su memoria en Engram, el código actual y el trabajo previo.  
> Su función es indicar **qué debe continuar, en qué orden, con qué límites y qué evidencia debe entregar**.

---

## 1. OBJETIVO DE CONTINUIDAD

Continuar desde el estado actual del proyecto sin reinicializarlo, sin rediseñarlo y sin sustituir componentes que ya funcionan.

La prioridad inmediata no es agregar funciones nuevas. Primero se debe:

1. dejar estable el backend;
2. cerrar el drift de base de datos;
3. demostrar aislamiento multirruta completo;
4. alinear móvil y backend en reglas financieras;
5. terminar la sincronización real y la autenticación productiva;
6. después avanzar al panel web administrativo y su bot.

No saltar etapas ni declarar una etapa terminada sin evidencia reproducible.

---

## 2. INVARIANTES QUE NO SE PUEDEN ROMPER

1. **No rehacer ni reestructurar el proyecto.**
   - Corregir de forma localizada.
   - Preservar arquitectura, pruebas, diseño, capturas, flujos y funcionalidades existentes.
   - No introducir frameworks, servicios o dependencias nuevas sin necesidad demostrada.

2. **La aplicación móvil del cobrador no lleva bot, chat ni asistente.**
   - El móvil sigue siendo la Hoja Viva, cobros, movimientos, caja, cierre, historial, PDF y operación offline.
   - El bot pertenece exclusivamente al panel web administrativo o a integraciones administrativas posteriores.

3. **Las rutas son dinámicas e indefinidas.**
   - Nunca asumir solamente R1, R2, R3 o R4.
   - Cada dato operativo debe pertenecer a negocio, ruta, cobrador y jornada cuando corresponda.
   - Una ruta nunca puede contaminar la cartera, pagos, caja, movimientos, cierre, historial o PDF de otra ruta.

4. **El backend es la autoridad financiera.**
   - El móvil puede calcular offline, pero sus resultados deben ser deterministas y equivalentes al backend.
   - No duplicar reglas con fórmulas diferentes.

5. **Dinero y eventos financieros deben conservar trazabilidad.**
   - Pagos, reversiones, movimientos, cierres y ajustes son append-only.
   - No borrar ni sobrescribir historia financiera.
   - Mantener idempotencia y transacciones atómicas.

6. **No debilitar pruebas para obtener verde.**
   - No eliminar asserts.
   - No aumentar tolerancias arbitrariamente.
   - No saltar pruebas.
   - No ocultar errores con mocks que eviten ejecutar la lógica real.

7. **No reescribir migraciones ya aplicadas.**
   - Si el esquema debe cambiar, crear una migración nueva y reversible.
   - Probar upgrade, downgrade y `alembic check`.

8. **No hacer commit, push, merge, tag, deploy ni reiniciar servicios sin autorización explícita.**

9. **Actualizar Engram y el handoff al finalizar cada bloque.**
   - Guardar decisiones, comandos, resultados, defectos, pruebas, archivos modificados y siguiente paso exacto.

---

## 3. ORDEN OBLIGATORIO DE EJECUCIÓN

No empezar el bloque siguiente hasta que el anterior tenga evidencia PASS o quede documentado como bloqueo real.

---

# BLOQUE 1 — BASELINE MÍNIMO ANTES DE CAMBIAR

No repetir una auditoría general. Solo confirmar que se trabaja sobre el estado esperado.

## Verificaciones

- rama y HEAD actuales;
- `git status`;
- diferencias locales;
- estado de PostgreSQL usado por pruebas;
- resultado actual de:
  - suite completa backend;
  - `alembic current`;
  - `alembic heads`;
  - `alembic check`;
  - `flutter analyze`;
  - `flutter test`;
  - UI Gate.

## Regla

Si aparecen cambios locales desconocidos, no sobrescribirlos. Detenerse y reportar.

## Evidencia de salida

Tabla corta:

| Gate | Resultado | Comando | Evidencia |
|---|---|---|---|

---

# BLOQUE 2 — ELIMINAR DEFINITIVAMENTE EL FLAKE UUID

## Problema ya demostrado

El fallo no depende del orden de pruebas. Es probabilístico.

La generación de identificadores mediante `hash()` puede producir un hexadecimal compuesto únicamente por dígitos. SQLite aplica afinidad numérica a la columna UUID y puede convertir el valor a `int` o `float`; después SQLAlchemy intenta reconstruirlo con `uuid.UUID()` y falla.

## Trabajo requerido

1. Crear una prueba de regresión determinista que fuerce exactamente el caso compuesto solo por dígitos.
   - No usar una prueba probabilística.
   - No depender de ejecutar miles de veces hasta fallar.

2. Comparar técnicamente estas opciones:
   - tipado portable con `sqlalchemy.Uuid`;
   - override SQLite de prueba a `CHAR(32)`;
   - combinación de ambas.

3. Elegir la corrección más pequeña que:
   - elimine la coerción numérica de SQLite;
   - mantenga PostgreSQL con tipo UUID;
   - no cambie el contrato de la API;
   - no cambie datos persistidos;
   - no altere innecesariamente el DDL productivo.

4. Ejecutar la suite completa en varios procesos nuevos.
   - No basta repetir en el mismo proceso.
   - Registrar cantidad de ejecuciones y resultados.

## Puerta separada: `hash()` → `uuid5`

No realizar este cambio automáticamente si modifica identificadores persistidos o contratos existentes.

Solo implementarlo cuando:

- se demuestre que es necesario además del arreglo de tipado;
- la entrada normalizada y el namespace sean estables;
- no se rompa compatibilidad con datos ya creados;
- exista prueba de determinismo;
- se documente claramente la migración o la ausencia de impacto.

Si existe impacto de compatibilidad, detenerse y solicitar autorización.

## Criterio PASS

- prueba determinista del caso extremo;
- suite backend completa en verde;
- varias ejecuciones desde procesos limpios;
- PostgreSQL conserva UUID;
- SQLite no vuelve a convertir el identificador en número.

---

# BLOQUE 3 — CERRAR EL DRIFT DE ALEMBIC

## Drift conocido

Revisar de forma exacta:

- `JSON` frente a `JSONB` en el snapshot de jornada;
- diferencias de claves foráneas en movimientos de caja;
- diferencia relacionada con `ruta.cobrador_id`;
- cualquier diferencia adicional que aparezca en el estado actual.

## Procedimiento

1. Comparar:
   - modelos SQLAlchemy;
   - migraciones existentes;
   - esquema PostgreSQL real;
   - intención funcional vigente.

2. Clasificar cada diferencia:
   - bug del modelo;
   - bug de migración;
   - drift legítimo que requiere nueva migración;
   - diferencia cosmética de autogenerate.

3. No modificar migraciones aplicadas.

4. Si corresponde, crear una sola migración nueva y coherente.

5. Probar:
   - base vacía → upgrade hasta head;
   - base actual → upgrade;
   - downgrade de la nueva revisión;
   - upgrade nuevamente;
   - `alembic current`;
   - `alembic heads`;
   - `alembic check`.

## Criterio PASS

- una sola cabeza;
- base en head;
- `alembic check` en verde;
- upgrade/downgrade reproducibles;
- ninguna pérdida de datos;
- ningún cambio accidental de semántica financiera.

---

# BLOQUE 4 — SELLAR EL AISLAMIENTO MULTIRRUTA

La arquitectura ya es multirruta. Este bloque no la rediseña: comprueba y cierra caminos donde todavía pueda cruzarse información.

## 4.1 Backend

Revisar y probar, como mínimo:

- detalle de ruta solicitado por un cobrador de otra ruta;
- lista y detalle de clientes para un cobrador;
- jornada activa solicitada con `ruta_id` distinto al contexto;
- detalle de movimiento por ID;
- creación, edición o asignación de rutas restringida a rol autorizado;
- créditos;
- pagos;
- reversiones;
- renovaciones;
- movimientos;
- caja;
- cierre;
- sincronización;
- historial;
- Hoja Viva;
- PDF y snapshot.

## Regla de respuesta

Para recursos que no pertenecen al alcance del cobrador:

- usar la política ya adoptada por el proyecto;
- mantener consistencia entre `403` y `404`;
- no revelar existencia de información de otra ruta.

## 4.2 Móvil

Comprobar que la base local y cada pantalla trabajen solo con el alcance autorizado.

Revisar especialmente:

- listado de rutas activas;
- selección de ruta;
- clientes y créditos disponibles al registrar un pago;
- validación `credito.ruta_id == jornada.ruta_id`;
- movimientos;
- historial;
- Hoja Viva;
- caja;
- cierre;
- PDF;
- cola de sincronización.

No confiar únicamente en que el backend rechazará el error. El móvil no debe ofrecer datos de otra ruta.

## 4.3 Prueba multirruta obligatoria

Crear fixtures sintéticos con:

- un negocio;
- administrador;
- varios cobradores;
- R1, R2, R3, R4 y una quinta ruta creada dinámicamente;
- clientes y créditos distintos por ruta;
- jornadas simultáneas;
- pagos, movimientos, cierre y PDF por ruta.

Demostrar:

- cada cobrador solo ve y opera su alcance;
- el administrador puede consultar y administrar todas las rutas del negocio;
- los totales de una ruta no cambian al operar otra;
- el carry de mañana proviene únicamente de la jornada anterior de la misma ruta;
- no hay límites codificados en cuatro rutas.

## Criterio PASS

- pruebas positivas y negativas en backend;
- pruebas locales móviles multirruta;
- ningún cruce en pagos, movimientos, caja, cierre, historial o PDF;
- ruta adicional creada dinámicamente funciona sin cambios de código.

---

# BLOQUE 5 — PARIDAD FINANCIERA ENTRE BACKEND Y MÓVIL

No rediseñar la Hoja Viva. Comparar resultados para los mismos eventos y corregir únicamente divergencias demostradas.

## Reglas que deben producir el mismo resultado

- abono neto:
  - pagos menos reversiones;
- saldo:
  - total contractual menos abono neto;
- cuotas pagadas:
  - división entera del abono neto por la cuota;
- pico:
  - residuo del abono neto respecto de la cuota;
- mora legacy:
  - fórmula vigente del proyecto;
- vencimiento real:
  - derivado del calendario contractual;
- semáforo:
  - gris mientras no exista score real;
- DC legacy;
- vence hoy;
- efectivo esperado;
- diferencia;
- carry de la siguiente jornada;
- renovación y dinero nuevo entregado.

## Pruebas requeridas

Construir una matriz de casos sintéticos:

- pago exacto de una cuota;
- pago parcial;
- pago de varias cuotas;
- pago superior a una cuota con pico;
- reversión;
- crédito diario;
- semanal;
- quincenal;
- cuota única;
- jornada con gastos, ahorro, vales, entregas, recibidos y desembolsos;
- cierre con diferencia;
- día siguiente con carry;
- operación separada en dos rutas.

Para cada caso, comparar:

```text
resultado backend == resultado móvil
```

## Criterio PASS

- cero divergencias en la matriz;
- una única definición documentada por regla;
- pruebas unitarias y de integración;
- no duplicación contradictoria de fórmulas.

---

# BLOQUE 6 — TERMINAR SINCRONIZACIÓN OFFLINE REAL

La cola local ya existe. Falta cerrar el transporte completo y verificable.

## Requisitos

1. Enviar eventos pendientes a la API:
   - pagos;
   - reversiones;
   - movimientos;
   - cierres;
   - documentos o metadatos cuando corresponda.

2. Mantener:
   - orden lógico;
   - idempotencia;
   - reintentos;
   - backoff;
   - persistencia tras reinicio;
   - no marcar sincronizado antes del ACK del servidor.

3. Descargar únicamente:
   - negocio autorizado;
   - cobrador autenticado;
   - rutas asignadas;
   - clientes y créditos permitidos;
   - cambios necesarios para operar offline.

4. Resolver:
   - pérdida de red durante una transacción;
   - cierre local pendiente;
   - duplicado;
   - evento ya aceptado por el servidor;
   - error permanente;
   - conflicto de versión;
   - dispositivo revocado.

5. El servidor debe reconstruir y validar cierres, no confiar en totales enviados por el cliente.

## Pruebas

- modo avión;
- reinicio de aplicación;
- reinicio de dispositivo/emulador;
- envío duplicado;
- respuesta 409;
- respuesta 401;
- revocación de dispositivo;
- dos rutas en teléfonos distintos;
- restauración de conectividad;
- cola finalmente vacía sin pérdida de eventos.

## Criterio PASS

- ningún evento financiero se pierde;
- ningún evento se duplica;
- el backend conserva autoridad;
- el móvil puede trabajar y cerrar sin conexión;
- al recuperar red, servidor y dispositivo convergen.

---

# BLOQUE 7 — AUTENTICACIÓN Y SEGURIDAD PRODUCTIVA

Eliminar la dependencia productiva de parámetros de consulta usados en desarrollo.

## Requisitos

- autenticación real;
- tokens firmados;
- claims de negocio, usuario, rol, ruta y dispositivo;
- refresh/revocación;
- dispositivo registrado;
- dispositivo revocado no puede sincronizar;
- cierre de sesión seguro;
- separación administrativa y cobrador;
- controles de autorización centralizados;
- secretos fuera del repositorio;
- configuración por ambiente;
- datos personales protegidos;
- logs sin información sensible.

El modo de autenticación por query debe quedar confinado a pruebas/desarrollo y ser imposible de activar accidentalmente en producción.

## Criterio PASS

- pruebas de RBAC;
- pruebas de token inválido, vencido y revocado;
- cobrador sin `route_id` no opera;
- administrador no queda limitado a una ruta;
- inversionista permanece en alcance de solo lectura definido;
- dispositivo revocado queda bloqueado.

---

# BLOQUE 8 — PANEL WEB ADMINISTRATIVO

Empezar este bloque solamente cuando backend, migraciones, multirruta, paridad, sincronización y autenticación estén estables.

## Alcance mínimo

- inicio de sesión administrativo;
- negocios;
- usuarios;
- cobradores;
- creación, activación y desactivación de rutas;
- asignación de cobradores;
- clientes;
- créditos;
- calendarios;
- cartera;
- estado de rutas;
- jornadas;
- pagos y reversiones;
- movimientos;
- caja;
- cierres;
- diferencias;
- documentos PDF;
- auditoría;
- dispositivos;
- reportes;
- filtros por ruta, cobrador y fecha.

## Regla

El panel consume el backend. No vuelve a implementar reglas financieras en el frontend.

---

# BLOQUE 9 — BOT Y CHATBOT ADMINISTRATIVO

El bot no se añade al móvil.

## Ubicación

- panel web administrativo;
- backend de integraciones;
- canal externo administrativo, cuando se autorice.

## Reglas

- respetar RBAC;
- no acceder directamente a la base;
- no calcular dinero por su cuenta;
- no ejecutar SQL libre;
- consumir endpoints y reportes autorizados;
- registrar auditoría;
- acciones sensibles requieren confirmación y permiso;
- comenzar en modo lectura antes de habilitar acciones.

## Funciones posibles

- consultar cartera por ruta;
- consultar recaudo y caja;
- alertas de cierres pendientes;
- diferencias de caja;
- reportes;
- estado de sincronización;
- dispositivos;
- entrega de PDF;
- resumen administrativo.

---

# BLOQUE 10 — CALIDAD, CI Y PREPARACIÓN DE PRODUCCIÓN

## CI obligatorio

Agregar gates reproducibles para:

- backend;
- migraciones;
- pruebas multirruta;
- móvil;
- UI;
- integración;
- análisis estático;
- seguridad;
- generación de artefactos.

## Producción

Cerrar:

- configuración por ambientes;
- Docker y despliegue reproducible;
- backups;
- restauración probada;
- observabilidad;
- métricas;
- logs;
- alertas;
- rate limiting;
- políticas de retención;
- privacidad;
- manejo de PII;
- APK/AAB firmado;
- versionado;
- rollback;
- documentación operativa.

## Rendimiento

Probar como mínimo:

- 150 clientes en una ruta;
- varias rutas activas simultáneas;
- varios cobradores sincronizando;
- jornadas largas;
- cola offline acumulada;
- generación de PDF;
- búsqueda y desplazamiento de Hoja Viva;
- modo claro/oscuro;
- texto aumentado;
- TalkBack.

---

## 4. PRIMER TRABAJO QUE DEBE EJECUTARSE AHORA

No empezar por web, bot, nuevas pantallas ni funciones comerciales.

Orden inmediato:

```text
1. Baseline mínimo
2. Flake UUID
3. Drift Alembic
4. Suite backend completa y repetida
5. Aislamiento multirruta
6. Paridad backend-móvil
```

Solo cuando esos seis puntos estén cerrados se continúa con sincronización y autenticación.

---

## 5. FORMATO OBLIGATORIO DEL INFORME DE CADA BLOQUE

OpenCode debe responder con esta estructura:

### A. Estado inicial
- HEAD;
- worktree;
- gates ejecutados;
- defectos reproducidos.

### B. Causa raíz
- archivo;
- función;
- línea o rango;
- mecanismo exacto del fallo;
- prueba que lo demuestra.

### C. Cambios realizados
- archivo por archivo;
- propósito;
- por qué es la modificación mínima;
- qué se preservó.

### D. Evidencia
- comandos exactos;
- resultados;
- número de pruebas;
- varias ejecuciones cuando aplique;
- migraciones;
- hashes o capturas cuando aplique.

### E. Riesgos restantes
- riesgo;
- severidad;
- impacto;
- siguiente acción.

### F. Estado de Git
- archivos modificados;
- archivos nuevos;
- ningún commit/push salvo autorización.

### G. Engram y handoff
- memoria actualizada;
- siguiente paso exacto;
- bloqueo, si existe.

---

## 6. CONDICIONES DE DETENCIÓN

Detenerse y reportar antes de continuar cuando:

- una corrección exige cambiar contratos públicos;
- se requiere migrar o reinterpretar datos existentes;
- aparece una contradicción financiera no resuelta;
- se necesita una dependencia arquitectónica nueva;
- un cambio afecta el flujo visual aprobado;
- una migración puede perder información;
- se requiere commit, push, deploy o reinicio;
- el reemplazo de `hash()` por `uuid5` afecta compatibilidad;
- no es posible demostrar el resultado con pruebas.

No improvisar una decisión silenciosa.

---

## 7. DEFINICIÓN GLOBAL DE TERMINADO

Daily System podrá considerarse preparado para una primera producción controlada cuando exista evidencia de:

- backend completamente verde;
- Alembic sin drift;
- aislamiento por negocio y ruta en todos los endpoints;
- móvil sin mezcla de rutas;
- reglas financieras iguales en backend y móvil;
- operación offline real con sincronización verificable;
- autenticación y dispositivo productivos;
- cierre y PDF íntegros;
- CI completo;
- recuperación ante fallos;
- pruebas multirruta;
- pruebas en dispositivo físico;
- release firmado;
- panel administrativo funcional;
- bot exclusivamente administrativo y separado del móvil.

Hasta entonces, cada elemento debe marcarse como:

```text
IMPLEMENTADO
PROBADO
PARCIAL
PENDIENTE
BLOQUEADO
```

Nunca usar "completado" sin evidencia mecánica reproducible.

---

## 8. ESTADO DE EJECUCIÓN (2026-08-06)

### BLOQUE 1 — BASELINE MÍNIMO → PASS

| Gate | Resultado | Comando | Evidencia |
|---|---|---|---|
| Git | PASS | `git status` | HEAD local = remoto = `486d08b`; divergencia 0/0; sin cambios locales desconocidos |
| Suite backend | PASS | `python3 -m pytest src/tests/ -q` | 138 passed, 1 warning |
| Alembic current | PASS (drift documentado) | `python3 -m alembic current` | `m3_dispositivo (head)` en ese momento |
| Alembic heads | PASS | `python3 -m alembic heads` | una sola cabeza: `m3_dispositivo` |
| Alembic check | FAIL esperado | `python3 -m alembic check` | drift JSONB/JSON + FKs movimiento_caja + ruta.cobrador_id → resuelto en Bloque 3 |
| Flutter analyze | PASS | `flutter analyze` | No issues found |
| Flutter test | PASS | `flutter test` | 68/68 PASS (incluye goldens 412x915 y tablet 840x900) |

### BLOQUE 2 — ELIMINAR EL FLAKE UUID → PASS

- **Opción elegida (autorizada): A — override exclusivo SQLite de pruebas `UUID → CHAR(32)`.**
- No se usó `sqlalchemy.Uuid`, no se combinó A+B, no se reemplazó `hash()` por `uuid5` (queda como deuda técnica separada).
- **Causa raíz confirmada**: `dispositivo_service.py:81` genera `UUID(int=hash(...) % 2**128)`; `hash()` es aleatorio por proceso; hex solo-dígitos (p≈0.045%) → SQLite afinidad NUMERIC → int/float → `uuid.UUID(float)` falla con `AttributeError: 'float' object has no attribute 'replace'`.
- **Cambios**:
  - `apps/api/src/tests/conftest.py` — `@compiles(UUID, "sqlite")` → `CHAR(32)` (afinidad TEXT).
  - `apps/api/src/tests/test_m3.py` — test determinista `test_dispositivo_id_hex_solo_digitos_sobrevive_sqlite` (monkeypatch de `builtins.hash` forzando `0x00000000000000009999999999999999`).
- **Evidencia**: sin el fix, el round-trip falla con el `AttributeError` exacto del flake; con el fix, 139/139 en 5 procesos limpios; DDL PostgreSQL sigue siendo `UUID` (el override solo dispara en sqlite).

### BLOQUE 3 — CERRAR EL DRIFT DE ALEMBIC → PASS

- **Clasificación del drift**:
  - `jornada.cierre_snapshot_json`: migración `m2` crea `JSONB`, modelo usaba `sqlalchemy.JSON` → **bug del modelo** (BD autoridad).
  - FKs `movimiento_caja` (credito_id, renovacion_id, ajuste_de_movimiento_id): `m2` las crea nombradas con `ON DELETE SET NULL`, modelo las declaraba anónimas sin ondelete → **bug del modelo** (BD autoridad).
  - `ruta.cobrador_id`: `init` crea la columna sin FK, modelo declara `ForeignKey("usuario.id")` → **bug de migración** → nueva migración `m4_ruta_cobrador_fk`.
- **Cambios**:
  - `apps/api/src/models/__init__.py` — `cierre_snapshot_json` → `JSONB().with_variant(JSON(), "sqlite")`; FKs MovimientoCaja con `name=` + `ondelete="SET NULL"`; `Ruta.cobrador_id` con `name="fk_ruta_cobrador"`.
  - Nuevo `apps/api/migrations/versions/m4_ruta_cobrador_fk.py` (reversible; no se reescribió init).
- **Evidencia**: `alembic check` limpio; upgrade m3→m4; downgrade m4→m3 (drift esperado de nuevo); upgrade otra vez; en BD scratch base vacía→head, downgrade→base, upgrade→head, check limpio; pytest 139/139; 0 huérfanos en `ruta.cobrador_id`.
- **Política de borrado confirmada**: `ruta.cobrador_id` sin `ON DELETE` → un cobrador asignado no puede borrarse físicamente mientras la ruta lo referencie; operación prevista es desactivar (`usuario.activo=0`) o reasignar. No se modifica la FK.

 ### BLOQUE 4 — SELLAR EL AISLAMIENTO MULTIRRUTA → PARCIAL (backend PASS; móvil productivo PENDIENTE; activación PENDIENTE)

> **Dictamen de auditoría externa (2026-08-06):** Bloque 4 global **PARCIAL**.
> - Aislamiento backend: **PASS** — mantener íntegro (no deshacer Bloques 2/3/4-backend).
> - Aislamiento móvil productivo: **PENDIENTE** — el móvil actual usa login demo (primer COBRADOR/primer negocio en `main.dart`), seed local, sin cliente HTTP; el celular no está vinculado a un cobrador activado.
> - Activación administrativa: **PENDIENTE** — no existe contrato de activación (QR de un solo uso, Keystore, vinculación dispositivo→cobrador). **[SUPERADA 2026-08-06:** el contrato de activación SÍ existe como diseño documental en `DAILY-SYSTEM-AUDITORIA-DISPOSITIVOS-CONTRATO-ACTIVACION.md` **revisión 4 — PASS DOCUMENTAL** (especificación congelada documentalmente; serialización resuelta: JCS RFC 8785, §13). La implementación sigue **NO AUTORIZADA** hasta instrucción separada; el bloque queda PENDIENTE de implementación, no de documento.**]**
> - **Autoridades separadas (sin duplicar fuente de verdad):** `ruta.cobrador_id` = asignación empresarial; `dispositivo.usuario_id` = celular autorizado del cobrador; alcance efectivo = servidor combina (negocio + cobrador + dispositivo activo + ruta asignada). El celular NO escoge ni descarga todas las rutas.
> - **Prohibido como autenticador principal:** IMEI, Android ID, huella calculada por el cliente, SharedPreferences, QR reutilizable. Requerido: par de claves en Android Keystore (solo clave pública registrada), código de activación de un solo uso con vencimiento guardado como hash, PKCE (RFC 8252), token que vincule negocio_id + usuario_id + dispositivo_id + rol + versión de asignación.
> - **Orden corregido:** 1) terminar paridad financiera (sin tocar navegación/activación); 2) contrato y pruebas de activación; 3) auth + vinculación del dispositivo; 4) bootstrap con la ruta única; 5) sync offline sobre ese alcance; 6) panel admin (rutas/dispositivos); 7) resto del panel; 8) bot exclusivamente administrativo.
> - **Entregable previo a código (obligatorio):** inventario del sistema Dispositivo actual, diagrama de estados (PENDING_ACTIVATION→ACTIVE→REVOKED|REPLACED|EXPIRED), contrato de endpoints, propuesta de migración reversible, política de revocación/reemplazo (sin borrar historia; bloqueo con jornada abierta/cola pendiente), tratamiento de eventos offline, 15 pruebas obligatorias, riesgos, archivos exactos, confirmación UI aprobada intacta.
> - **Restricciones:** sin commit, push, deploy, reinicio ni reestructuración.

- **Alcance ejecutado** (2026-08-06): cerrar huecos backend; documentar (no resolver) endpoints sin auth + restricciones de rol/PII; revisar capa móvil (documentar, sin tocar código móvil); prueba multirruta sintética R1–R4 + 5ª ruta dinámica; informe A–G. Conservar Bloques 2 y 3.

**4.1 Huecos backend cerrados (5):**

| Hueco | Archivo | Fix |
|---|---|---|
| `POST /api/pagos` sin validar `jornada_id` del body | `services/payment_service.py` (`register_payment`) | jornada existente del mismo negocio → `PaymentError` 404; `jornada.ruta_id == credito.ruta_id` → `PaymentRouteError` 403; `ctx.has_route` si cobrador → 403. Import de `Jornada` agregado |
| `GET /api/movimientos/{id}` sin check de ruta | `services/movimiento_service.py` (`get_movimiento`) | filtra por `negocio_id`; si cobrador, `join(Jornada)` y filtra `Jornada.ruta_id == ctx.route_id` |
| `GET /api/jornadas/active` sin check de ruta | `routes/jornada.py` | cobrador sin `ctx.has_route(ruta_id)` → `HTTPException(404, "No hay jornada activa para esta ruta")` (no revela existencia) |
| `GET /api/rutas/{ruta_id}` sin check de ruta | `routes/ruta.py` | cobrador sin `ctx.has_route(ruta_id)` → 404 "Ruta no encontrada". `listar_rutas` ya filtraba por `route_id` |
| clientes limitados al alcance del cobrador | `routes/cliente.py` (`listar_clientes`) | cobrador → `join(Credito)` filtrando `Credito.ruta_id == ctx.route_id` + `.distinct()` (Cliente no tiene `ruta_id`; alcance derivado de créditos) |

- `test_m1_gate.py::test_payment_saves_traceability_fields` actualizado: crea `Jornada` real (`jid`, `nid`, `rid`, `fecha=2026-07-01`, `estado="OPEN"`) porque el pago con `jornada_id` ficticio ya no pasa (fijación legítima de la prueba, no debilitamiento).

**4.2 Documentado, NO resuelto (dependiente de auth real — Bloque 7):**

1. `routes/negocio.py:38-52` — `GET /api/negocios` y `GET /api/negocios/{id}` **sin `get_request_context` ni auth** (fuga cross-tenant en modo dev).
2. `routes/inversionista.py` — ya valida rol INVERSIONISTA/ADMINISTRADOR (403), suscripción `al_dia` (403), `paid_through_at` vencido (403). Sin PII expuesta.
3. `routes/hoja_viva.py` — ya valida `has_negocio`/`has_route` (403), pero **cualquier rol puede leer** (sin control de rol).
4. `routes/dispositivo.py` — `POST /api/dispositivos` y `revocar|reactivar` requieren admin; `GET /api/dispositivos` cualquier rol scoped al negocio.
5. Creación/edición de rutas, clientes y dispositivos: **sin gate explícito de rol ADMINISTRADOR** en todos los caminos (depende de que el contexto dev default sea `ADMINISTRADOR`).

**4.3 Revisión de capa móvil (documentada, sin modificar código):**

- **Correctamente scoped por ruta/jornada**: `HojaVivaService.getHojaViva` (`ruta_id + ACTIVO`); `JornadaService.abrirJornada`/`getJornadaAbierta` (única abierta por `fecha+estado+ruta_id`); `getJornadasHistorial` (filtra `ruta_id` de prefs); `CajaService.calcularCaja` (por jornada → por ruta); `MovimientosScreen`/`CajaScreen`/`JornadaCierreScreen` (por jornada); `PdfService.generarPdfDesdeSnapshot` (por jornada, snapshot inmutable con hash); `PagoService.registrarPago`/`reversarPago` (transacciones + JornadaGuard).
- **Huecos client-side (documentados como pendiente de Bloque 7, NO resueltos):**
  - `screens/pago_screen.dart:37-45` — `_cargarCreditos` consulta `credito WHERE estado='ACTIVO'` **sin `ruta_id`**; `PagoScreen` no recibe `rutaId` → un cobrador ve créditos de otras rutas locales en el selector. El backend ahora rechaza el cruce (403 `PaymentRouteError`); el móvil depende del servidor (contradice "no ofrecer datos de otra ruta").
  - `screens/caja_main_screen.dart:34-36` — jornada abierta `WHERE estado='OPEN' ORDER BY fecha DESC LIMIT 1` **sin ruta**; con jornadas simultáneas puede mostrar la de otra ruta.
  - `screens/inicio_screen.dart:59-66` — jornada abierta `WHERE j.estado='OPEN' ORDER BY fecha DESC LIMIT 1` **sin ruta**; mismo problema con jornadas simultáneas.
  - `screens/cobros_shell.dart:207-211` — `_cargarRutas` `WHERE activa=1` **sin filtro `cobrador_id`** → cualquier cobrador ve todas las rutas activas (igual que el legado `ruta_screen.dart:50`).
  - `services/pago_service.dart` — `registrarPago`/`reversarPago` no validan localmente `credito.ruta_id == jornada.ruta_id` (se delega al servidor).
  - Legado huérfano: `screens/home_screen.dart` + `ruta_screen.dart` no están referenciados por `main.dart`/`MainShell` (flujo activo: `main.dart → MainShell → InicioScreen/CobrosShell`); `home_screen` tiene `_sinConexion=true`, `_jornadaAbierta=false` hardcoded.

**4.4 Prueba multirruta sintética — `apps/api/src/tests/test_m4.py` (nuevo, PASS, 528 líneas):**

Fixture: 1 negocio, 1 admin, varios cobradores, R1–R4 + R5/R6 dinámicas; créditos y clientes por ruta; jornadas simultáneas. 9 tests:

| Test | Demuestra |
|---|---|
| `test_r1_r2_jornadas_simultaneas` | dos rutas operan el mismo día con jornadas independientes |
| `test_operar_r2_no_altera_r1` | pagos/movimientos/cierre de R2 dejan intacta la caja de R1 (`recaudo_real`, `gastos`, `pagos_count`) y `get_net_paid` de la cartera R1 |
| `test_cobrador_r1_no_lee_r2` | 404 (mensaje exacto "No hay jornada activa para esta ruta", jornada por ID, pago por ID, movimiento por ID, ruta por ID); 403 hoja-viva y crédito por ID; listas scoped; movimientos de jornada R2 → 200 `[]` |
| `test_cobrador_r1_no_modifica_r2` | pago sobre crédito R2 → 403; pago crédito R1 + jornada R2 → 403; movimiento en jornada R2 → 409; cierre/caja/preparar-siguiente R2 → 404; R2 sigue OPEN sin pagos |
| `test_admin_accede_a_todas` | admin lee jornadas/pago/movimiento de cualquier ruta y ve las 4 rutas, 4 clientes, 1 pago |
| `test_snapshot_por_ruta_no_se_cruzan` | snapshot de cierre de cada ruta contiene solo sus `pagos_ids`/`movimientos_ids` (R1: 50000−5000=45000; R2: 80000−3000=77000) |
| `test_opening_carry_solo_misma_ruta` | `sobrante_manana` de R1 (1000) y R2 (2000) en D; `opening_carry` de D+1 es solo el de la misma ruta |
| `test_opening_carry_sin_jornada_previa_misma_ruta` | ruta sin jornada previa cerrada obtiene carry 0 aunque otra ruta haya cerrado |
| `test_quinta_ruta_sin_cambio_de_codigo` | R5 y R6 creadas vía API con admin (sin límite fijo de 4); R5 opera punta a punta (cliente/crédito/jornada/pago/cierre con `recaudo_real` 40000); cobrador R1 no ve R5 (404) |

**Evidencia Bloque 4:**

- `python3 -m pytest src/tests/ -q` → **148 passed, 1 warning** (139 previos + 9 nuevos). Repetición estable en múltiples ejecuciones.
- Alembic contra PG real (puerto 7103): `current` = `m4_ruta_cobrador_fk (head)`, una sola cabeza, `alembic check` → **No new upgrade operations detected**.
- Gates móviles (re-ejecutados el 2026-08-06): `flutter analyze` → **No issues found!**; `flutter test` → **68/68 PASS** (goldens 412x915 phone + 840x900 tablet, temas claro/oscuro); `scripts/ci/ui_gate.sh` → **UI Gate: ALL PASSED** (tokens Dart/CSS consistentes + analyze + 68/68).
- Sin cambios en código móvil (`apps/mobile/` intacto); la revisión fue documental.

### SIGUIENTE PASO

→ **BLOQUE 5 — PARIDAD FINANCIERA BACKEND-MÓVIL** (AUTORIZADO por dictamen 2026-08-06; EN EJECUCIÓN)
- **Decisión del dictamen (2026-08-06, revisión de desbloqueo):** continuar inmediatamente con el Bloque 5; no esperar otra revisión del contrato de activación. La revisión 4 del contrato queda como **diseño documental en curso, no implementable aún**. **[SUPERADA parcialmente 2026-08-06:** la revisión 4 quedó **cerrada como PASS DOCUMENTAL** (especificación congelada); la parte "no implementable aún / sin autorización" sigue vigente.**]** Backend = **autoridad financiera**.
- **Límites:** no modificar activación, challenge-response, Keystore, huella/public_key, tokens, JWT/OAuth/PKCE, bootstrap, sincronización HTTP, sync_queue, jsonEncode, selección de rutas, login demo, revocación, reasignación, dependencias Flutter de seguridad o red. No tocar la UI salvo que una cifra legítimamente corregida lo exija (entonces detenerse y reportar). No regenerar goldens. Web puede avanzar en módulos independientes.
- Matriz determinística de casos (pago normal, parcial, pago mayor que una cuota, varias cuotas, pico, reverso parcial, reverso total, mora, vence hoy, cuotas pagadas, saldo contractual, saldo neto, renovación, opening_carry, cierre, snapshot) comparando `resultado backend == resultado móvil` con los mismos datos. Clasificar cada diferencia: BUG BACKEND / BUG MÓVIL / DIFERENCIA DE REPRESENTACIÓN / REGLA NO DEFINIDA / SIN DIVERGENCIA.
- Corregir solo divergencias demostradas; una única definición documentada por regla. No alterar reglas donde ambos lados ya coinciden. No introducir otra calculadora paralela. Evidencia de 13 puntos (matriz, resultados, divergencias, cambios, pruebas, suite, analyze, test, UI Gate, git status, diff --check, riesgos).

### ENTREGABLE PREVIO A CÓDIGO (dictamen 2026-08-06) — REVISIÓN 4 DOCUMENTAL, NO IMPLEMENTABLE

> Documento `DAILY-SYSTEM-AUDITORIA-DISPOSITIVOS-CONTRATO-ACTIVACION.md` en **revisión 4**: correcciones 1–7 integradas + 4 precisiones del protocolo de canje (intento de un solo uso, nonce CSPRNG, transacción con bloqueo, serialización JCS/CBOR byte a byte) + matriz de librerías verificada. El auditor aprobó las correcciones 4–7 **conceptual**mente con condición (no verificó línea por línea; el archivo no fue adjuntado). **No se convierte en código todavía.** Los elementos de la auditoría (EC P-256, SPKI, JCS/CBOR, MethodChannel, librerías, estructura de tokens, nombres de migraciones, numeración de bloques) son **propuestas, no decisiones definitivas**; se compararán con el código local y la arquitectura existente antes de implementar.
>
> **[ACTUALIZADO 2026-08-06 — REVISIÓN 4 → PASS DOCUMENTAL:** la serialización quedó **resuelta: JCS (RFC 8785), CBOR canónico descartado** (§13 del documento, con perfil canónico congelado y vector de prueba obligatorio). La especificación del contrato queda **congelada documentalmente**, sigue **NO implementada** y **sin autorización de código**; el Bloque 6 no se inició; la implementación requerirá instrucción separada. Referencias "JCS/CBOR como alternativa" que aparezcan en el cuerpo del documento quedan **SUPERADAS** por la sección 13.**]**

### BLOQUE 5 — PARIDAD FINANCIERA BACKEND-MÓVIL → PASS (2026-08-06)

| Gate | Resultado | Comando |
|---|---|---|
| Paridad móvil | 14/14 PASS | `flutter test test/paridad_b5_test.dart` |
| Suite móvil completa | 82/82 PASS | `flutter test` |
| Suite backend | 166/166 PASS | `pytest src/tests/ -q` |
| `flutter analyze` | No issues found | `flutter analyze` |
| UI Gate | ALL PASSED | `scripts/ci/ui_gate.sh` |
| `git diff --check` | OK | `git diff --check` |

- **C-06 resuelto:** un reverso es **TOTAL** en ambas plataformas (REVERSAL monto = monto del pago original) → restituye el saldo contractual completo de **200.000**, no 195.000. Reverso parcial = REGLA NO DEFINIDA.
- **Fixes aplicados:** backend `reverse_payment` hereda `jornada_id` del original; `calcular_caja` acepta `entregas`/`recibidos`. Móvil `hoja_viva_service.dart` (pico/cuotas_pagadas/mora_legacy/semáforo GRIS/reportDate) y `jornada_service.dart` (carry de apertura + `sobrante_manana`).
- **UI (autorizada):** resumen de hoja viva = chip único **GRIS: N** (semáforo GRIS temporal hasta `score_snapshot` real; sin clasificación VERDE/AMARILLO/ROJO ni score). Goldens regenerados (solo los 3 de CobrosShell/Hoja Viva, autorizados).
- Evidencia completa en `DAILY-SYSTEM-BLOQUE5-MATRIZ-PARIDAD.md` (§10) y handoff.

### BLOQUE 6 — CONTRATO DE ACTIVACIÓN (BACKEND) → PASS (2026-08-06)

| Gate | Resultado | Comando |
|---|---|---|
| Suite backend | 181 passed + 1 skip | `pytest src/tests/ -q` (166 previos + 15 nuevos §9; skip = concurrencia PG) |
| `test_m5_activacion.py` | 15 passed + 1 skip | `pytest src/tests/test_m5_activacion.py -q` |
| `alembic check` | No new upgrade operations detected | `python3 -m alembic check` (PG dev, puerto 7103) |
| Alembic current dev | `m5_dispositivo_activacion (head)` | `python3 -m alembic current` |
| Migración reversible | upgrade→downgrade→re-upgrade OK | scratch `cobro_scratch_b6` (SQLite-compatible) y `cobro_scratch_b6_pg` (cadena m2→m5 desde cero) |
| Evidencia concurrencia PG | 1 consumo + 1 idempotente → 1 dispositivo | script `evidencia_concurrencia_b6.py` contra `cobro_scratch_b6_pg` |
| `git diff --check` | OK | `git diff --check` |

- **Implementado:** migración `m5_dispositivo_activacion` (estado/public_key/public_key_hash/algoritmo_clave, huella→nullable, backfill, 3 índices parciales únicos, `codigo_activacion`+`intento_activacion`, checks); modelos alineados con `Index` parciales (`postgresql_where`+`sqlite_where`); JCS RFC 8785 (§13.4, vector 285 bytes verificado); servicio `generar_codigo`/`desafio`/`canjear` (SELECT FOR UPDATE, idempotente, `MAX_INTENTOS_FALLIDOS=5`→EXPIRED)/`bootstrappear` (solo dispositivo ACTIVE); rutas `/api/activaciones/*` + `GET /api/mobile/bootstrap`; reemplazo de dispositivo (`POST /api/dispositivos/{id}/reemplazar`, admin-only).
- **Defectos §10 corregidos:** `POST /api/dispositivos` admin-only (403); device id = uuid4 (no derivado de `hash()`); bootstrap devuelve solo la ruta activa del cobrador.
- Evidencia completa en handoff §5 y en `apps/api/src/tests/test_m5_activacion.py`. Sin commit/push/deploy/reinicio.

### SIGUIENTE PASO → BLOQUE 7 — AUTENTICACIÓN Y VINCULACIÓN DEL DISPOSITIVO (backend productivo)

Orden seguro aprobado (dictamen 2026-08-06): **1)** ✅ contrato de activación revisión 4 (PASS DOCUMENTAL) → **2)** ✅ activación backend implementada y verificada (Bloque 6 PASS) → **3)** autenticación + vinculación del dispositivo móvil (bootstrap móvil limitado a una ruta) → **4)** crear `apps/web` productiva con el stack aprobado → **5)** integrar cobradores/rutas/activaciones/dispositivos/revocaciones/reemplazos → **6)** sincronización sobre identidad y alcance reales.

**NO** comenzar todavía sincronización que confíe en IDs de negocio/cobrador/ruta enviados libremente por el móvil. Hasta aprobar la revisión completa, NO crear/modificar: migraciones de activación, `CodigoActivacion`, `IntentoActivacion`, `public_key`, challenge-response, JWT/OAuth/PKCE, Keystore, bootstrap, sincronización HTTP, dependencias Flutter, módulo productivo de activación web.

### ESTADO WEB OFICIAL + NOTA DE RECONCILIACIÓN (2026-08-06)

> **Hallazgo de auditoría (aprobado):** la "aplicación web administrativa" NO existe como producto. `apps/web` está vacía; el material web real es un prototipo estático HTML/CSS en `design/prototypes/web/` (MOCK visual, datos hardcodeados, sin JS/API/auth/build) + `docs/web/WEB-UI-BLUEPRINT.md` (declara "prototipo visual, no aplicación productiva").

| Componente | Estado |
|---|---|
| Backend | Productivo en desarrollo, Bloques 1–6 PASS (activación backend implementada) |
| Móvil | Implementado y probado; activación/sync productivos pendientes |
| Web productiva (`apps/web`) | **PENDIENTE** (carpeta vacía) |
| Prototipo web HTML/CSS | MOCK visual |
| Blueprint web (`WEB-UI-BLUEPRINT.md`) | IMPLEMENTADO (documento) |
| Stack web | **APROBADO**: Next.js 14 + TypeScript + Tailwind CSS + shadcn/ui + Playwright E2E |
| Autenticación web | PENDIENTE |
| Integración API web | PENDIENTE |
| Bot administrativo | FUTURO (exclusivamente administrativo) |
| Bot en móvil | **PROHIBIDO** |

- No se crea aplicación web paralela; no se conserva el HTML estático como arquitectura productiva; se reutilizan del prototipo sus tokens, disposición, componentes visuales y criterios WCAG.
- `docs/IMPLEMENTATION-PLAN.md` y `docs/STATUS.md`: sus afirmaciones de `apps/web`, panel inversionista productivo y bot Telegram productivo están **DESACTUALIZADAS** (corregidas con nota de reconciliación sin borrar historia). **La evidencia real del repositorio y las pruebas prevalece sobre estados históricos incorrectos.**

--- End of file ---
