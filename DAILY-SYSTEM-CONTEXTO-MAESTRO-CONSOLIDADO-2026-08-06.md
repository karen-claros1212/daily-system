# DAILY SYSTEM — CONTEXTO MAESTRO CONSOLIDADO
## Producto, código real, decisiones, estado, riesgos y continuidad

**Fecha de consolidación:** 2026-08-06  
**Proyecto canónico:** `Daily System`  
**Repositorio:** `karen-claros1212/daily-system`  
**Ruta local conocida:** `/home/jesus/proyectos/daily-system`  
**Rama oficial conocida:** `master`  
**HEAD remoto verificado:** `486d08b1584684a4328825142209776fce477670`  
**Memoria del proyecto:** Engram, `project: "daily-system"`

---

# 0. PROPÓSITO DE ESTE DOCUMENTO

Este documento reúne en una sola fuente de continuidad:

- la visión completa de Daily System;
- las decisiones funcionales vigentes;
- las reglas financieras y operativas centrales;
- la arquitectura objetivo;
- la arquitectura realmente implementada;
- el estado comprobado del repositorio;
- la evidencia visual y de pruebas;
- las contradicciones documentales;
- los bloqueos técnicos encontrados;
- la clasificación correcta del bot;
- el orden de trabajo para continuar sin perder ni degradar lo existente.

No reemplaza el código. Cuando exista una contradicción, el agente debe distinguir entre:

```text
ESPECIFICACIÓN DEL PRODUCTO
CÓDIGO REAL
PRUEBAS Y EVIDENCIA
DOCUMENTACIÓN HISTÓRICA
DECISIÓN MÁS RECIENTE DEL USUARIO
```

No se debe declarar implementada una capacidad solamente porque aparezca marcada como completa en un plan.

---

# 1. JERARQUÍA DE FUENTES

Usar esta prioridad:

1. **Decisiones explícitas más recientes del usuario.**
2. **Código real del repositorio en el HEAD verificado.**
3. **Pruebas ejecutadas y evidencia reproducible.**
4. **Engram con `project: daily-system`.**
5. **Graphify actualizado sobre el HEAD actual.**
6. **Documento Maestro v1.3 cerrado**, como especificación funcional objetivo.
7. **Documento Maestro v1.1**, como antecedente útil.
8. `README.md`, `IMPLEMENTATION-PLAN.md`, `STATUS.md` y otros documentos, siempre contrastados contra el árbol real.

## 1.1 Relación entre v1.1 y v1.3

El archivo aportado más recientemente es:

```text
DOCUMENTO-MAESTRO-Plataforma-Cobro-Colombia-v1.1.md
```

Contiene una especificación clara y compacta de Colombia, hoja viva, rutas, pagos, jornada, caja, PDF, panel web, seguridad, sincronización, suscripción y etapas.

Sin embargo, posteriormente se creó:

```text
DOCUMENTO-MAESTRO-Plataforma-Cobro-Colombia-v1.3-CERRADO.md
```

La v1.3 se declara cerrada y reemplaza borradores anteriores. Por tanto:

- v1.3 gobierna el producto objetivo;
- v1.1 se conserva como antecedente y fuente de reglas útiles;
- cualquier punto de v1.1 que contradiga v1.3 queda superado, salvo decisión posterior del usuario;
- no se elimina información útil de v1.1 que sea compatible con v1.3.

## 1.2 Diferencia principal entre v1.1 y v1.3

La v1.1 limita la v1 inicial a administrador y cobrador, y coloca inversionista/Telegram Mini App fuera de alcance.

La v1.3 amplía el alcance:

- inversionista opcional y activable por negocio;
- PDF por Telegram;
- Telegram Mini App;
- chatbot administrativo futuro;
- bot proactivo basado en reglas.

La decisión más reciente del usuario aclara la ubicación correcta:

```text
EL BOT NO PERTENECE A LA APLICACIÓN DEL COBRADOR.
```

El bot, la Mini App y el asistente conversacional pertenecen al ecosistema administrativo/web/inversionista.

---

# 2. IDENTIDAD DEL PRODUCTO

Daily System es un SaaS multiempresa por suscripción para negocios colombianos que prestan dinero y realizan cobranza de campo por rutas.

## 2.1 Mercado inicial

```text
País: Colombia
Moneda: COP
Zona horaria: America/Bogota
Idioma: español
```

No es un ERP general. No incluye nómina, inventarios, facturación electrónica ni CRM general.

## 2.2 Promesa principal

Para el cobrador:

> Es la misma hoja que conoce, pero ahora hace las cuentas sola.

Para el administrador:

> Puede saber qué pasó en cada ruta y cuánto efectivo debería existir.

## 2.3 Modelo comercial

- SaaS multiempresa.
- Suscripción mensual por adelantado.
- Pago inicial por Nequi o Bancolombia.
- Referencia y comprobante.
- Sin pasarela obligatoria para el lanzamiento.
- El vencimiento bloquea operación sin borrar información.
- Permiso offline inicial de hasta 72 horas, limitado por el período realmente pagado.

---

# 3. ROLES

## 3.1 Cobrador

Trabaja solamente con su ruta.

Puede ver y operar:

- su ruta;
- clientes y créditos de su ruta;
- cuota, saldo, último pago y atraso individual;
- hoja viva;
- pagos y reversiones autorizadas;
- préstamos y renovaciones según reglas;
- movimientos de su jornada;
- su caja;
- TERMINAR JORNADA;
- historial de su operación;
- PDF local operativo;
- estado de sincronización.

No debe ver:

- cartera total del negocio;
- otras rutas;
- resultados de otros cobradores;
- capital total colocado;
- rentabilidad global;
- configuración de suscripción;
- PII o información fuera de su ruta.

## 3.2 Administrador

Tiene visión completa de su empresa:

- rutas y cobradores;
- clientes y créditos;
- cartera;
- pagos;
- caja y cierres;
- diferencias;
- renovaciones y refinanciación;
- dinero nuevo entregado;
- PDF y reportes;
- configuración;
- suscripción;
- dispositivos;
- riesgo, alertas y score cuando existan.

Su puesto principal es el panel web productivo. Puede tener acceso móvil complementario o acceso remoto administrativo.

## 3.3 Inversionista

En la v1.3 es un rol opcional y activable por negocio.

Ve agregados de portafolio:

- capital colocado;
- cobro real;
- refinanciación;
- cartera neta;
- atraso por alturas;
- salud y evolución del portafolio.

No puede recibir:

- nombres de deudores;
- documentos;
- teléfonos;
- direcciones;
- PII individual.

---

# 4. CLASIFICACIÓN DEFINITIVA DEL BOT

## 4.1 Aplicación móvil del cobrador

La aplicación Flutter del cobrador:

```text
NO TIENE BOT
NO NECESITA BOT
NO DEBE INCLUIR CHATBOT
NO DEBE INCLUIR TELEGRAM
NO DEBE DEPENDER DE UN BOT
```

Debe ser una herramienta rápida de trabajo de calle.

## 4.2 Plataforma administrativa

El bot puede formar parte de:

- backend de integraciones;
- panel web administrativo;
- informes automáticos;
- Telegram del administrador;
- acceso del inversionista;
- Mini App;
- alertas futuras;
- chatbot administrativo read-only en la etapa inteligente.

## 4.3 Función prevista

Bot Telegram:

- enviar PDF oficial después de `CLOSED_SYNCED`;
- enviar alertas generadas por reglas determinísticas;
- facilitar consultas administrativas autorizadas en etapas posteriores.

Telegram Mini App:

- navegación remota del administrador o inversionista;
- consultas y aprobaciones definidas;
- autenticación validada por el backend.

## 4.4 Corrección documental necesaria

Cualquier documento que diga:

```text
Bot Telegram del cobrador como parte de la app móvil
```

está mal clasificado.

Puede existir un destinatario o usuario asociado a una ruta, pero no una interfaz de bot dentro de `apps/mobile`.

---

# 5. FLUJO PRINCIPAL DEL COBRADOR

```text
ABRIR DÍA
→ recibir base y arrastre
→ descargar/abrir ruta disponible
→ consultar hoja viva
→ registrar abonos
→ registrar préstamos/renovaciones autorizadas
→ registrar movimientos
→ revisar caja
→ TERMINAR JORNADA
→ contar efectivo
→ calcular diferencia
→ sellar snapshot
→ generar PDF local
→ preparar el día siguiente
→ sincronizar cuando haya conectividad
```

La acción de cobro debe requerir aproximadamente:

```text
1. tocar cliente
2. tocar cuota o escribir valor
3. confirmar
```

Atajos esperados:

```text
PAGÓ CUOTA
2 CUOTAS
TODO EL SALDO
OTRO VALOR
```

---

# 6. REGLAS FINANCIERAS CENTRALES

## 6.1 Dinero

- COP en enteros/BIGINT para montos operativos.
- DECIMAL/NUMERIC para tasas y porcentajes.
- Nunca `float` para dinero ni cálculos financieros.

## 6.2 Crédito

Regla autoritativa:

```text
total_contratado = cuota × número_de_cuotas
```

El porcentaje comercial predeterminado no reemplaza el plan contractual redondeado.

Periodicidades:

```text
DIARIO
SEMANAL
QUINCENAL
```

La ruta sigue siendo diaria y un cliente puede pagar cualquier día.

## 6.3 Cálculos de hoja viva

```text
saldo = total - Abo
#_C = Abo // cuota
pico = Abo % cuota
```

Separar:

- `DC/PROMEDIO` legado;
- cuotas que realmente vencen hoy.

## 6.4 Pagos

Cada pago es un registro individual append-only.

Tipos básicos:

```text
PAYMENT
REVERSAL
```

Debe existir idempotencia:

```text
UNIQUE(negocio_id, idempotency_key)
```

Un pago confirmado no se edita silenciosamente. Se revierte mediante otro registro.

## 6.5 Renovación

Separar siempre:

```text
saldo_anterior
pago_efectivo_cliente
saldo_refinanciado
monto_credito_nuevo
dinero_nuevo_entregado
```

Invariante:

```text
saldo_anterior = pago_efectivo_cliente + saldo_refinanciado
```

El saldo refinanciado no es cobro real en efectivo.

## 6.6 Caja

Separar:

```text
opening_base
opening_carry
```

Fórmula objetivo:

```text
efectivo_esperado =
    opening_base
  + opening_carry
  + cobros_reales_en_efectivo
  + transferencias_entrada
  - desembolsos_reales
  - gastos
  - ahorro/custodia
  - vales
  - transferencias_salida
```

En renovación se descuenta `dinero_nuevo_entregado`, no el nominal completo.

Fixture crítico:

```text
275 + 805 - 400 - 20 - 18 - 50 = 592
```

---

# 7. TERMINAR JORNADA

Estados previstos:

```text
OPEN
CLOSING
CLOSED_LOCAL_PENDING_SYNC
CLOSED_SYNCED
```

La operación debe:

1. congelar nuevas entradas;
2. validar que no haya operaciones incompletas;
3. calcular cobro real, refinanciado, desembolsos y movimientos;
4. pedir efectivo contado;
5. calcular diferencia;
6. exigir motivo cuando la diferencia no sea cero;
7. confirmar y sellar;
8. crear snapshot inmutable;
9. actualizar créditos y carry;
10. preparar la ruta de mañana;
11. generar PDF local;
12. encolar sincronización;
13. validar el cierre en servidor;
14. generar/archivar reporte oficial;
15. actualizar el panel;
16. enviar reporte administrativo/Telegram cuando esté habilitado.

El cierre local debe funcionar sin internet.

El administrador no puede ver como recibido un cierre que todavía no llegó al servidor.

---

# 8. OFFLINE Y SINCRONIZACIÓN

## 8.1 Operación offline requerida

- abrir una ruta previamente disponible;
- buscar clientes;
- consultar créditos;
- cobrar;
- registrar movimientos;
- cerrar jornada;
- generar PDF;
- preparar mañana;
- reintentar sincronización.

Estados visibles:

```text
SINCRONIZADO
PENDIENTE
ERROR
```

## 8.2 Aislamiento

- Cada crédito tiene `ruta_id`.
- Cada jornada tiene negocio, ruta, cobrador y fecha.
- El cobrador de R1 no puede leer ni modificar R2.
- El aislamiento debe existir en servidor y sincronización, no solo ocultando botones.
- Los datos de otras rutas no deben llegar al dispositivo.

## 8.3 Autoridad

- El servidor valida operaciones al sincronizar.
- El reloj del servidor es autoridad para mora, jornada y licencia.
- El teléfono conserva la hora del dispositivo como evidencia, no como autoridad.
- No se confía en un `route_id` libre enviado por la app.

---

# 9. PDF Y REPORTES

## 9.1 PDF móvil

La app genera localmente, sin IA y sin conexión:

- PDF de cierre;
- planilla/resumen de ruta;
- recibo o comprobante;
- otros reportes operativos autorizados.

El PDF de cierre debe usar el mismo snapshot inmutable del cierre. No puede recalcular cifras por otro camino.

## 9.2 PDF servidor

El backend puede generar o regenerar una copia canónica para:

- archivo;
- descarga web;
- recuperación;
- auditoría;
- Telegram.

No requiere OCR, LLM, GPU ni RTX 5090.

## 9.3 Privacidad

Los reportes del inversionista no incluyen nombres, teléfonos, documentos ni direcciones de deudores.

---

# 10. PANEL WEB ADMINISTRATIVO

El panel web productivo es una pieza central y temprana del producto, no un extra final.

Menú objetivo:

```text
Inicio
Rutas
Clientes
Créditos
Cartera
Caja
Aprobaciones
Planilla
Riesgo
Alertas
Reportes
Configuración
Suscripción
```

Inicio esperado:

- cobro real hoy;
- refinanciado;
- dinero nuevo entregado;
- rutas cerradas y pendientes;
- diferencias de caja;
- alertas críticas.

Por ruta:

- cobrador;
- última sincronización;
- vence hoy;
- cobro efectivo;
- clientes que pagaron;
- caja esperada y contada;
- diferencia;
- estado de jornada.

La lógica financiera no se duplica en Next.js. La web consume cifras calculadas y autorizadas por el backend.

---

# 11. INTELIGENCIA

No se implementa antes de tener datos y etapas anteriores completas.

## 11.1 Score

Arranque en frío:

```text
score_status = INSUFFICIENT_DATA
score = NULL
color = GRIS
```

No se inventa un score neutral.

Estados:

```text
GRIS
VERDE
AMARILLO
ROJO
```

El score debe ser explicable y guardar snapshots históricos.

## 11.2 Chatbot administrativo

Pertenece a:

```text
panel web
Telegram Bot / Mini App
```

No a la app del cobrador.

Reglas:

- read-only en v1;
- no consulta directamente la base;
- no escribe SQL;
- no calcula dinero;
- no ejecuta operaciones financieras;
- usa catálogo cerrado de consultas;
- respeta roles y PII;
- devuelve los mismos números que dashboard y reportes.

## 11.3 Alertas

Primero reglas determinísticas:

- cuota vencida;
- crédito terminado/cerca de terminar;
- varios créditos activos;
- diferencia de caja;
- ruta sin sincronizar;
- jornada sin cerrar;
- renovación con poca reducción real.

Después, con historia suficiente:

- deterioro;
- predicción de recaudo;
- anomalías;
- probabilidad de atraso.

---

# 12. ARQUITECTURA OBJETIVO

La especificación v1.3 propone:

```text
Flutter app cobrador
SQLite cifrada
sincronización local-first / PowerSync Sync Streams
FastAPI modular monolith
PostgreSQL
Next.js panel administrativo
Telegram Bot / Mini App para administración e inversionista
```

Regla:

```text
No microservicios en v1.
```

Versiones estables, fijadas y reproducibles. Nada beta en producción.

---

# 13. ARQUITECTURA REAL DEL REPOSITORIO

En el HEAD `486d08b` el árbol `apps/` contiene solamente:

```text
apps/api
apps/mobile
```

No contiene:

```text
apps/web
apps/telegram-bot
```

## 13.1 Backend real

```text
apps/api
FastAPI
SQLAlchemy
Alembic
PostgreSQL para integración
SQLite in-memory en pruebas
```

Dominios encontrados:

- negocio;
- ruta;
- cliente;
- crédito;
- pago;
- hoja viva;
- jornada;
- movimientos;
- dispositivo;
- suscripción;
- inversionista.

## 13.2 Móvil real

```text
apps/mobile
Flutter Offline Alpha
SQLite con sqflite
colas propias de sincronización
PDF con paquete Dart
Material 3
```

Dependencias verificadas incluyen:

```text
sqflite
path
path_provider
pdf
printing
share_plus
intl
shared_preferences
uuid
crypto
```

No existe dependencia PowerSync en el `pubspec.yaml` actual.

## 13.3 Web real

No hay panel web productivo versionado.

Existe:

```text
design/prototypes/web
```

Es un prototipo visual, no una aplicación Next.js productiva.

## 13.4 CI real

Solo existe:

```text
.github/workflows/ui-gate.yml
```

No hay workflow GitHub Actions de backend con `pytest` y `alembic check`.

---

# 14. ESTADO VERIFICADO DEL REPOSITORIO

## 14.1 GitHub

```text
Repositorio: karen-claros1212/daily-system
Visibilidad: público
Rama por defecto: master
HEAD: 486d08b1584684a4328825142209776fce477670
Rama master protegida: no
```

El último commit remoto es documental y no declara cambios funcionales posteriores a la auditoría visual.

## 14.2 Móvil

Última ejecución real reportada:

```text
Flutter 3.44.0 stable
Dart 3.12.0
flutter analyze: PASS
flutter test: 68/68 PASS
scripts/ci/ui_gate.sh: PASS
```

Advertencia GTK de Linux no bloquea las pruebas móviles.

## 14.3 Evidencia visual

El repositorio contiene:

- 68 capturas before/after;
- teléfono y tableta;
- claro y oscuro;
- prototipo web;
- manifest con SHA-256;
- golden snapshots;
- pruebas semánticas y widgets;
- capturas de login, inicio, hoja viva, pago, movimientos, caja, cierre e historial.

## 14.4 APK

```text
APK debug construido
Emulador Android API 35: PASS
Dispositivo físico: PENDING
Release firmado: no verificado
Producción: pendiente
```

## 14.5 Backend

Última ejecución real reportada:

```text
137 passed
1 failed
```

La cifra documental `138/138` no se reprodujo en suite completa.

## 14.6 Alembic

```text
alembic heads: m3_dispositivo
alembic current: m3_dispositivo
alembic check: FAIL
```

Drift conocido:

- `jornada.cierre_snapshot_json`: JSON frente a JSONB;
- claves foráneas de `movimiento_caja`;
- `ruta.cobrador_id`;
- metadata/modelos no alineados completamente con el esquema real.

## 14.7 Graphify

Estado local más reciente reportado después de reconstrucción AST sin LLM:

```text
Graphify 0.9.29
HEAD analizado: 486d08b
2504 nodos
4062 aristas
173 comunidades
95 % extraído
0 tokens LLM
```

`tree_sitter_sql` fue instalado solo en el entorno aislado de Graphify.

El archivo versionado `docs/GRAPHIFY-CURRENT.md` continúa desactualizado y todavía describe un grafo antiguo.

---

# 15. CAUSA RAÍZ UUID

La investigación más reciente demostró:

- no es un fallo normal de orden de pruebas;
- es probabilístico, aproximadamente 0,045 % según la investigación reportada;
- `hash()` en `dispositivo_service.py` produce identificadores no determinísticos entre procesos;
- cuando el hexadecimal queda formado solo por dígitos, SQLite aplica afinidad NUMERIC;
- SQLite puede convertirlo a `float` o `int`;
- `uuid.UUID()` recibe un valor numérico y falla con:

```text
AttributeError: 'float' object has no attribute 'replace'
```

El aislamiento general del `conftest.py` fue verificado como correcto.

Opciones estudiadas, aún no aplicadas según el último resumen:

```text
A. Override test-only para UUID → CHAR(32) en SQLite
B. Modelos → sqlalchemy.Uuid, verificando DDL PostgreSQL idéntico
C. Ambas protecciones
D. Reemplazar hash() por uuid5 como corrección de producto
```

No elegir automáticamente. Antes de cambiar se debe comprobar compatibilidad con IDs existentes y PostgreSQL.

---

# 16. CONTRADICCIONES DOCUMENTALES

## 16.1 IMPLEMENTATION-PLAN y STATUS

Ambos afirman M3 completo con:

```text
apps/telegram-bot
apps/web/src/app/inversionista
Bot Telegram cobrador
Bot Telegram inversionista
Panel inversionista web
```

El árbol real de GitHub solo contiene:

```text
apps/api
apps/mobile
```

Por tanto, M3 no puede considerarse completo en esos componentes.

## 16.2 README

El README es más preciso al declarar:

```text
Backend API: implementado
Android Offline Alpha: implementado
Panel web productivo: planificado
Prototipo web visual: implementado
```

Pero su roadmap también marca M3 Telegram/inversionista como completo. Esa parte debe corregirse.

## 16.3 STATUS

`docs/STATUS.md` sigue declarando:

```text
HEAD b6d48bb
138/138
M3 Telegram/web completo
```

Está desactualizado frente a:

```text
HEAD 486d08b
137/138 en la última ejecución
apps/web ausente
apps/telegram-bot ausente
```

## 16.4 Graphify

`docs/GRAPHIFY-CURRENT.md` describe un grafo construido desde un SHA anterior con 63 nodos. El grafo local actualizado reportó 2504 nodos sobre `486d08b`.

## 16.5 PowerSync

La arquitectura objetivo incluye PowerSync, pero el móvil real usa `sqflite` y colas propias.

No se debe describir PowerSync como implementado.

## 16.6 Bot del cobrador

La clasificación "Bot Telegram (cobrador)" no significa que la app móvil deba tener bot. La decisión actual es que el bot pertenece a la plataforma administrativa/integraciones.

---

# 17. MATRIZ REAL DE AVANCE

## Etapa 1 — que funcione

| Capacidad | Estado real |
|---|---|
| Multiempresa/backend | Implementado parcialmente/verificado por código |
| Rutas aisladas | Implementado, requiere gates completos de seguridad |
| Clientes y créditos | Implementado |
| Calendarios | Parcial según código/pruebas; validar cobertura completa |
| Hoja viva Flutter | Implementado y auditado |
| Pagos idempotentes | Implementado |
| Offline | Implementado con SQLite/colas propias |
| PDF planilla/cierre | Implementado en móvil/backend según alcance actual |
| Panel web administrativo básico | **No implementado** |
| PowerSync Sync Streams | **No implementado** |

**Conclusión:** Etapa 1 no está completamente cerrada frente a la especificación v1.3.

## Etapa 2 — que cuadre

| Capacidad | Estado real |
|---|---|
| Jornada | Implementado |
| Opening base/carry | Implementado según dominio actual |
| Movimientos | Implementado |
| Renovación separando dinero nuevo | Implementado parcialmente; verificar todas las invariantes |
| TERMINAR JORNADA | Implementado en móvil/backend |
| Diferencia y motivo | Implementado |
| Snapshot y hash | Implementado |
| Preparación de mañana | Implementado según pruebas móviles |
| PDF cierre | Implementado |
| Reporte administrativo oficial | Parcial, falta panel productivo |
| Telegram automático | No encontrado en árbol real |
| Backend completamente verde | **No: 1 test + Alembic drift** |

**Conclusión:** Etapa 2 está avanzada, pero no puede cerrarse con gates backend rojos y sin canal administrativo completo.

## Etapa 3 — que se venda

| Capacidad | Estado real |
|---|---|
| Planes y suscripciones | Implementado |
| Límites por plan | Implementado |
| Dispositivo autorizado | Implementado en backend |
| Bloqueo/licencia completo | Implementado parcialmente; validar contra especificación total |
| Nequi/Bancolombia y comprobantes | Especificado; verificar implementación real completa |
| Alta de negocios | Backend parcial; falta experiencia administrativa productiva |
| Inversionista web/Mini App | No implementado productivamente |
| Bot/PDF automático | No encontrado en árbol real |

**Conclusión:** Etapa 3 es parcial, no completa.

## Etapa 4 — que se migre fácil

```text
OCR/foto/PDF
extracción
validación cruzada
revisión humana
importación
contingencia
```

**Estado:** pendiente.

## Etapa 5 — que sea inteligente

```text
score
semáforo
motivos
tendencia
alertas
predicción
anomalías
chatbot administrativo
bot proactivo
```

**Estado:** pendiente, salvo estructuras o campos preparatorios que deben inventariarse.

## Producción

```text
compose productivo
CI backend/web
nginx
TLS
monitoreo
backups
restore drills
logs
release Android firmado
prueba física
```

**Estado:** pendiente.

---

# 18. BLOQUEOS Y RIESGOS ACTUALES

## P0 — antes de continuar funciones financieras

1. Test UUID probabilístico.
2. Drift de Alembic.
3. Falta de gate backend en CI.

## P1 — antes de declarar etapas 1-3 completas

1. Panel web productivo ausente.
2. Telegram/bot/Mini App no encontrados en el árbol real.
3. PowerSync objetivo no integrado; falta decisión de arquitectura de sincronización.
4. Documentación de hitos incorrecta.
5. Rama `master` no protegida.
6. Prueba en dispositivo físico pendiente.
7. Build release firmado pendiente.

## P2 — antes de producción

1. Cifrado real de SQLite no demostrado por las dependencias actuales.
2. Infraestructura productiva y backups no cerrados.
3. CI/CD completo ausente.
4. Pruebas de restauración y seguridad pendientes.
5. Revisión de privacidad para OCR y almacenamiento.

---

# 19. ORDEN CORRECTO PARA CONTINUAR

No saltar directamente a OCR porque un plan desactualizado diga "M4".

Orden recomendado por coherencia funcional:

## Paso 1 — recuperar línea base verde

- resolver UUID de forma compatible;
- resolver drift de Alembic;
- ejecutar backend completo varias veces;
- conservar 68/68 móvil y UI Gate;
- crear CI backend.

## Paso 2 — cerrar la primera etapa realmente incompleta

- inventariar contrato API disponible para administración;
- construir panel web administrativo productivo básico dentro de `apps/web`;
- reutilizar el prototipo visual;
- no duplicar cálculos financieros;
- implementar autenticación y permisos;
- mostrar estado de rutas, cierres, caja y sincronización.

## Paso 3 — completar reporte administrativo y etapa comercial

- PDF oficial asociado a jornada;
- canal administrativo de descarga;
- Telegram opcional para administrador/inversionista;
- no incluir bot en móvil;
- terminar licencia, alta de negocios y comprobantes según código real.

## Paso 4 — decidir sincronización objetivo

Antes de introducir PowerSync:

- documentar el comportamiento de las colas actuales;
- medir cobertura offline;
- comparar contra requisitos de Sync Streams;
- definir migración incremental;
- evitar reemplazo masivo sin pruebas.

## Paso 5 — OCR

Solo después de cerrar etapas tempranas:

- foto/PDF;
- extracción;
- validación cruzada;
- confirmación humana obligatoria;
- nunca aplicar manuscritos automáticamente.

## Paso 6 — inteligencia

- capturar historial primero;
- score gris sin datos;
- reglas determinísticas;
- chatbot administrativo read-only;
- predicción/anomalías después.

## Paso 7 — producción

- release firmado;
- dispositivo físico;
- CI/CD;
- infraestructura;
- TLS;
- monitoreo;
- backups y restauración;
- piloto controlado.

---

# 20. DECISIONES COMERCIALES PENDIENTES

No debe definirlas el agente:

- dominio;
- precio mensual;
- métrica de cobro;
- plan anual;
- prueba gratis;
- precio de instalación;
- días de gracia;
- quién realiza la carga inicial;
- aprobación de créditos originados en calle;
- acción cuando un cobrador no sincroniza por varios días;
- umbral para automatizar conciliación bancaria;
- uno o varios inversionistas por negocio.

Decisiones ya cerradas:

- Colombia;
- COP;
- Nequi + Bancolombia inicial;
- hoja viva;
- rutas aisladas;
- TERMINAR JORNADA;
- local-first;
- panel web administrativo;
- seguridad obligatoria;
- bot fuera de la aplicación del cobrador.

---

# 21. PROTOCOLO OBLIGATORIO PARA AGENTES

1. Confirmar SHA local y remoto.
2. Leer Engram `project: daily-system`.
3. Consultar Graphify.
4. Leer directamente archivos afectados.
5. Buscar implementación existente antes de crear otra.
6. Revisar modelos, migraciones, rutas, servicios y pruebas.
7. Ejecutar gates antes del cambio.
8. Hacer cambios incrementales.
9. Ejecutar gates después.
10. Revisar diff completo.
11. Hacer commits pequeños y reversibles.
12. Guardar decisiones y resumen en Engram.

Prohibido:

```text
git reset --hard
force push
git clean destructivo
borrados masivos
reescritura de migraciones aplicadas
refactors amplios sin necesidad
crear repositorio/app/backend paralelo
confundir Daily System con NexusCorp
agregar bot a la app del cobrador
```

---

# 22. GATES MÍNIMOS

## Backend

```text
pytest completo PASS
alembic current = head
alembic check PASS
pruebas financieras
pruebas de permisos y aislamiento
pruebas de idempotencia
```

## Mobile

```text
flutter analyze PASS
flutter test 68/68 o más
UI Gate PASS
goldens sin regresión
semantics PASS
offline/cierre/PDF PASS
```

## Web cuando exista

```text
lint PASS
typecheck PASS
tests PASS
build PASS
permisos PASS
sin cálculos financieros duplicados
```

## Producción

```text
release firmado
prueba física
backup restore
TLS
secret scanning
monitoreo
rollback
```

---

# 23. DEFINICIÓN DE NO REGRESIÓN

No se acepta una mejora que:

- cambie cifras financieras;
- mezcle rutas;
- duplique pagos;
- pierda capacidad offline;
- haga que el cierre local quede incompleto;
- genere PDF con cifras distintas al snapshot;
- exponga PII al inversionista;
- agregue bot a la app del cobrador;
- rompa las capturas/goldens auditadas;
- modifique UI sin necesidad funcional;
- contradiga el documento maestro sin registrar la decisión.

---

# 24. FUENTES CONSOLIDADAS

## Especificaciones

- `DOCUMENTO-MAESTRO-Plataforma-Cobro-Colombia-v1.1.md`
- `docs/DOCUMENTO-MAESTRO-Plataforma-Cobro-Colombia-v1.3-CERRADO.md`

## Estado y planificación

- `README.md`
- `docs/IMPLEMENTATION-PLAN.md`
- `docs/STATUS.md`
- `docs/GRAPHIFY-CURRENT.md`
- `DAILY-SYSTEM-CONTEXT-HANDOFF.md`
- Engram `project: daily-system`

## Código y evidencia

- `apps/api`
- `apps/mobile`
- `design/prototypes/web`
- `docs/ui-audit`
- `docs/assets/readme`
- `.github/workflows/ui-gate.yml`
- `graphify-out`

## Evidencia externa a Git no versionada

- resultado local de gates;
- investigación probabilística UUID;
- grafo Graphify actualizado;
- APK debug local;
- handoff local actualizado.

---

# 25. RESUMEN OPERATIVO PARA EL PRÓXIMO AGENTE

```text
Daily System ya tiene un backend FastAPI sustancial y una aplicación Flutter
Offline Alpha visualmente auditada. No empezar de cero.

La app del cobrador es la hoja viva y no lleva bot.
El bot, Mini App y chatbot pertenecen a administración/inversionista.

El plan documental dice M3 completo, pero el árbol real no contiene apps/web
ni apps/telegram-bot. PowerSync tampoco está integrado.

Antes de nuevas funciones, cerrar UUID y Alembic y mantener 68/68 móvil.
Luego terminar la primera etapa funcional incompleta, principalmente el panel
web administrativo y los canales oficiales de reporte, antes de OCR y de la
inteligencia.

Código, pruebas, Engram, Graphify y documentación deben volver a coincidir.
```

---

# 26. DICTAMEN CONSOLIDADO

Daily System no es un proyecto vacío ni un prototipo aislado. Tiene:

- producto definido;
- reglas financieras claras;
- backend real;
- aplicación móvil real;
- offline real con SQLite;
- jornada, caja, snapshot y PDF;
- diseño y evidencia profesional;
- pruebas móviles verdes;
- repositorio organizado.

Pero tampoco está listo para declarar M0-M3 completamente terminados ni producción:

- el backend no está totalmente verde;
- existe drift de migraciones;
- el panel web productivo falta;
- Telegram/Mini App no están en el árbol;
- PowerSync es objetivo, no realidad;
- falta CI backend;
- falta release físico/productivo.

La continuidad correcta es preservar lo construido, corregir la línea base y completar las etapas tempranas reales antes de avanzar a OCR, score o chatbot.

--- End of file ---
