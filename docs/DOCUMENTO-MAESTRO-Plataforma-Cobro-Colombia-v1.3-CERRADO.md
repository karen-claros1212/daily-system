# Plataforma inteligente de cobro diario — documento maestro Colombia

> **Versión:** 1.3 · Documento cerrado funcional y técnicamente
> **Reemplaza** a todos los borradores anteriores. Nada queda por fuera de aquí.
> **Estado:** listo para congelar como especificación maestra, salvo las decisiones comerciales expresamente abiertas en la Parte 20.
> **Mercado de esta versión:** Colombia exclusivamente.
> **Criterio:** fusionar la profundidad comercial y operativa del v1.0 con las correcciones financieras, de sincronización y seguridad de la v1.1. Ninguna capacidad solicitada se elimina.

---

## Índice

```
PARTE  1   Qué es y para quién
PARTE  2   Modelo de negocio y suscripción
PARTE  3   Qué lo hace único
PARTE  4   El sistema que se reemplaza
PARTE  5   Arquitectura general
PARTE  6   Convivencia con la infraestructura existente
PARTE  7   Cloudflare
PARTE  8   Modelo de datos
PARTE  9   Sincronización
PARTE 10   La aplicación del cobrador
PARTE 11   La aplicación del administrador
PARTE 12   El inversionista
PARTE 13   Seguridad y anti-manipulación
PARTE 14   El backend inteligente
PARTE 15   Importación y contingencia por foto
PARTE 16   PDF y Telegram
PARTE 17   Dirección visual
PARTE 18   Despliegue y costos
PARTE 19   Etapas de entrega
PARTE 20   Decisiones pendientes
PARTE 21   Riesgos
PARTE 22   Matriz de aceptación y no regresión
```

---

# PARTE 1 · Qué es y para quién

Un producto de software que se **arrienda mes a mes** a operadores de crédito de paga diario en **Colombia**.

No es una aplicación a la medida de un cliente. Es un producto con muchos clientes, cada uno con su operación aislada, que paga una mensualidad para poder usarlo.

**El cliente típico:**

```
1 administrador (dueño u oficina)
0 o más inversionistas por negocio; el rol y su acceso remoto forman parte de v1, aunque cada negocio decide si los activa
1 a 8 rutas, cada una con su cobrador
100 a 1.000 créditos activos
hoy: planilla impresa + digitación manual en oficina
```

El número de rutas es un dato, no una constante del sistema. Un negocio con una ruta y otro con siete usan el mismo producto.

**Distribución geográfica:** varios negocios independientes en distintas ciudades de Colombia. Esta especificación no compromete requisitos regulatorios, pagos, idiomas ni operaciones de otros países.

## 1.1 Decisiones de producto ya cerradas

```
PAÍS                    Colombia
MONEDA                  COP
ZONA HORARIA            America/Bogota
IDIOMA                  Español
COBRADOR                trabaja únicamente su ruta
RUTA                    recorrida diariamente
CRÉDITOS                diarios · semanales · quincenales
APP COBRADOR            la hoja conocida, convertida en hoja viva
ADMINISTRACIÓN          panel web completo + acceso remoto por Telegram Mini App
CIERRE                  botón TERMINAR JORNADA
PAGO SUSCRIPCIÓN V1     Nequi + Bancolombia, con referencia y comprobante
ARQUITECTURA            local-first, segura, sincronizada
TECNOLOGÍA              versiones estables y soportadas, no betas por moda
```

La simplificación se aplica a la **experiencia del usuario**, no al rigor del backend.

Una pantalla puede ser sencilla y, al mismo tiempo, estar protegida por aislamiento multiempresa, aislamiento por ruta, cifrado, idempotencia, auditoría, validación de servidor y respaldos.

---

# PARTE 2 · Modelo de negocio y suscripción

## 2.1 Cómo se cobra

Suscripción mensual **por adelantado**. El cliente paga antes de usar el mes.

La métrica de cobro debe cumplir tres condiciones: crecer con el negocio del cliente, que la cuente el sistema solo, y que el cliente no la pueda falsear. Las opciones quedan en la Parte 20.

## 2.2 Estados de la cuenta

| Estado | Qué puede hacer el cliente |
|---|---|
| **Al día** | Todo. |
| **Por vencer** (7 días antes) | Todo. Solo el administrador ve el aviso. El cobrador no ve nada. |
| **Vencido** | Nada. La aplicación no abre. Pantalla de pago con valor y medio. |
| **Reactivado** | Todo vuelve al instante, intacto. |

**El bloqueo es total, no parcial.** Un bloqueo a medias deja operar y le quita urgencia al pago.

**La información no se borra ni se retiene.** Se conserva completa y se devuelve apenas paga. Esto no es una concesión: es lo que hace que pague en vez de irse. Un cliente que cree que va a perder su cartera busca cómo sacarla y no vuelve. La palanca es la interrupción de la operación, no la amenaza sobre los datos.

## 2.3 El mecanismo técnico del bloqueo

Es el punto más importante del modelo. La aplicación trabaja sin señal; si la validación viviera solo en el servidor, el cliente apaga los datos y trabaja gratis para siempre.

```
Al sincronizar, la API emite credenciales de sesión y un permiso offline firmado.
PowerSync valida la identidad/autorización en cada conexión.
El dispositivo guarda la última hora confiable recibida del servidor.
Sin permiso offline vigente, la operación se bloquea incluso sin red.

offline_valid_until =
MIN(
    last_server_validation + 72 horas,
    subscription_paid_through
)
```

La consecuencia es exacta:

- un cobrador puede seguir trabajando hasta 72 horas sin cobertura si la suscripción sigue pagada;
- **el permiso jamás atraviesa la fecha hasta la que está pagada la suscripción**;
- vencida la suscripción, no se regalan 72 horas adicionales;
- un retroceso sospechoso del reloj local obliga a conectarse antes de continuar.

Las 72 horas son el valor inicial del producto y se revisan con el piloto, no con intuición.

## 2.4 Los tres roles

| Rol | Alcance |
|---|---|
| **Inversionista** | Rol incluido y activable por negocio. Ve capital colocado, plata que entró, refinanciación, cartera, atraso y salud del portafolio. **Nunca** nombres, teléfonos, documentos ni direcciones de deudores. |
| **Administrador** | Toda la operación de su negocio: clientes, créditos, cobradores, caja, configuración, suscripción. |
| **Cobrador** | Su ruta y su caja del día. Nada más. |

## 2.5 Qué significa exactamente VENCIDO

El bloqueo es funcionalmente total.

Cuando el negocio está `VENCIDO`, administrador y cobradores no pueden:

```
abrir rutas
registrar pagos
originar créditos
renovar
reencauchar
abrir/cerrar jornadas
generar nuevos reportes operativos
sincronizar nuevas operaciones financieras
```

La aplicación conserva disponibles únicamente:

```
estado de la suscripción
valor pendiente
Nequi
Bancolombia
referencia
subir/reportar comprobante
validar reactivación
soporte
```

Nada se borra. Al verificarse el pago, la operación vuelve con los mismos datos.

## 2.6 Pago de la suscripción en Colombia — v1

No se obliga a integrar una pasarela para lanzar.

Pantalla:

```
PAGAR SUSCRIPCIÓN

[ NEQUI ]
[ BANCOLOMBIA ]
```

**Nequi** muestra:

```
número
titular
valor
referencia única
[ COPIAR ]
[ YA PAGUÉ ]
```

**Bancolombia** muestra:

```
tipo de cuenta
número de cuenta
titular
valor
referencia única
[ COPIAR ]
[ YA PAGUÉ ]
```

El cliente puede adjuntar comprobante. El proveedor verifica el pago y reactiva.

La integración bancaria o pasarela se incorpora cuando el volumen vuelva ineficiente la conciliación manual; no condiciona el MVP.

---

# PARTE 3 · Qué lo hace único

Cuatro diferenciadores, y los cuatro salen de la ingeniería inversa que ya está hecha sobre el sistema legado.

## 3.1 Entra por la planilla, no por el teclado

**Es el argumento de venta principal.**

Un operador con 340 créditos no cambia de sistema porque tiene que digitar 340 clientes a mano antes de usar nada. Nadie lo hace.

Aquí le toma una foto a su planilla y el sistema la lee. Y funciona porque **la planilla se valida contra sí misma**: está demostrado que la suma de las cuotas debe dar igual al pie `PROMEDIO`, y la suma de los saldos igual a `CARTERA X COBRAR`. Si no cuadra, el sistema señala en qué renglones está la diferencia.

Se monta un operador en una hora en vez de en una semana. La competencia no lo puede copiar sin reconstruir primero la aritmética de esas hojas.

## 3.2 Le sigue imprimiendo su planilla igual

Todas las aplicaciones del mercado dicen *olvídese del papel*. Por eso fracasan: nadie apuesta una cartera de doscientos millones a un software que apenas conoce.

Aquí la planilla se sigue imprimiendo idéntica —mismas columnas, mismo pie, mismos números—, solo que la genera el sistema. El cliente trabaja en paralelo el tiempo que quiera.

Elimina la objeción de venta más difícil: *¿y si se cae?*

## 3.3 El número que el dueño nunca ha tenido

Cuando un cliente renueva, el sistema actual registra el saldo viejo como si hubiera entrado plata. No entró: cambió de crédito.

Medido sobre una ruta real: el cobrador reporta 7.909.000 recaudados; entraron **1.561.000**. La efectividad se ve en 152 % cuando es de 30 %.

Ninguna aplicación del mercado separa esos números, porque todas copiaron la forma de pensar del operador.

## 3.4 El control sobre el cobrador que hoy no existe

El formato de cierre en papel tiene casillas para conciliar la caja —oficina, diferencia, total— y están **en blanco en los veinte formatos revisados**. El control existe en el formulario y no en la práctica.

Aquí el cierre no se puede saltar. Es, en la práctica, lo que el dueño está comprando.

## 3.5 La hoja no se reemplaza: se vuelve viva

El cobrador no tiene que aprender una lógica nueva.

La aplicación conserva la estructura mental de la planilla:

```
Cliente · Cuota · Día · #_C · Abono · Pico · Monto · Abo · Saldo · Mora
```

pero cada abono actualiza la fila en el momento.

El valor comercial no está en poner veinte menús. Está en que el cobrador pueda pasar de papel a aplicación sin perder velocidad.

## 3.6 Las rutas no se chocan

Cada crédito pertenece a una ruta, no el cliente.

Una misma persona puede tener créditos en R1 y R2, pero:

```
cobrador R1 → recibe únicamente crédito(s) R1
cobrador R2 → recibe únicamente crédito(s) R2
administrador → ve la exposición completa de la persona
```

La separación no depende de ocultar botones. Los datos de otra ruta **no se sincronizan al dispositivo**.

## 3.7 El día se cierra una vez y mañana nace de ese cierre

El botón **TERMINAR JORNADA** sustituye la digitación nocturna:

```
cierra el día
→ calcula caja
→ pide efectivo contado
→ registra diferencia
→ sella movimientos
→ recalcula cada crédito
→ arrastra sobrante
→ prepara la ruta de mañana
→ genera PDF
→ sincroniza
→ actualiza al administrador
```

Ese flujo es un diferenciador operativo tan importante como la importación por foto.

## 3.8 Preguntar en lugar de buscar entre reportes

El administrador puede preguntar:

```
¿Cuánto entró hoy?
¿Qué ruta no ha cerrado?
¿Cuánto se refinanció esta semana?
¿Dónde hay diferencias de caja?
```

El asistente no inventa ni calcula: traduce la pregunta a consultas cerradas y probadas, y explica los resultados oficiales.

Esto vuelve accesible la inteligencia sin convertir el sistema en una caja negra.

---

# PARTE 4 · El sistema que se reemplaza

Reconstruido sobre 17 planillas de cuatro rutas y 20 formatos de cierre, con la aritmética verificada al peso.

## 4.1 Las fórmulas del legado

```
total  = cuota x n
saldo  = total - abo
#_C    = abo / cuota            (division entera)
pico   = abo modulo cuota
mora   = (fecha_reporte - 1 - inicia) en dias calendario - #_C
```

Precisiones verificadas:

- El ancla de la mora es **la fecha del reporte menos un día**, no el campo `Ultimo`.
- Cuenta **días calendario corridos**, sin excluir domingos ni festivos. Comprobado sobre horizontes de 128, 190 y 205 días.
- Cero se imprime como blanco. Aplica a `Mora`, `Pico` y `#_C`.
- `total / monto = 1,20` en la práctica totalidad de los registros, pero **no es regla del software**: existe contraejemplo sostenido con ratio 1,40.
- El redondeo del plan usa **techo y cobra el residuo**: `50 x 29 = 1.450` cuando `1.200.000 x 1,20 = 1.440.000`.

## 4.2 Agregados verificados

```
PROMEDIO = DC = suma de cuota de todos los creditos activos de la ruta
CARTERA X COBRAR = suma de saldo
CLIENTES = (personas en ruta, personas que abonaron, porcentaje truncado)
```

`PROMEDIO` no es un promedio. Es una etiqueta heredada mal puesta sobre una sumatoria.

## 4.3 La cadena de caja

La reconstrucción moderna separa conceptos para no contar el sobrante dos veces:

```
opening_base      = base/entrega nueva de oficina del día
opening_carry     = sobrante trasladado desde la jornada anterior

efectivo_esperado =
    opening_base
  + opening_carry
  + recaudo_real_en_efectivo
  + otras_transferencias_entrada
  - desembolsos_reales
  - vales
  - gastos
  - ahorro/custodia
  - transferencias_salida

closing_carry(D) = sobrante_para_manana(D)
opening_carry(D+1) = closing_carry(D)
```

En renovación se resta de caja **el dinero realmente entregado al cliente**, no el nominal completo del nuevo crédito.

El slip legado se puede reconstruir por compatibilidad, pero la contabilidad moderna usa flujos físicos.

**Caso de aceptación obligatorio** (R4, 6 de julio):

```
275 + 805 - 400 - 20 - 18 - 50 = 592    el talonario dice 592
```

## 4.4 Los quince hallazgos

| ID | Hallazgo |
|---|---|
| L-01 | No existe libro de pagos. `Abo` es un acumulador. Sin registro fechado no hay reversión ni conciliación. |
| L-02 | No existe identidad de cliente. Texto libre, sin documento. |
| L-03 | Los tres eventos de originación colapsan en la bandera `Nuevo`. |
| L-04 | `Mora` se aplica igual a diario, semanal, quincenal y cuota única. Para los no diarios no significa nada. |
| L-05 | Ni recaudo, ni porcentaje de clientes, ni cartera separan cobro de refinanciación. |
| L-06 | La renovación aplica recargo sobre saldo que ya lo incorporaba. |
| L-07 | Cartera nominal bruta con recargo capitalizado desde la originación. Sin provisión ni castigo. |
| L-08 | Los cuatro campos de conciliación del talonario, vacíos en 20 de 20. |
| L-09 | `VALE` y `OTROS` son texto libre sin contrapartida. Solo *ahorro* mueve ~$1.200.000 semanales. |
| L-10 | La semántica de `EFECTIVO` estaba oscurecida por el formulario, pero quedó reconstruida como caja residual después de entradas y salidas del día; el caso R4 06-jul la cierra con base y ahorro. |
| L-11 | `cuota`, `n` y `monto` son campos libres sin validación cruzada. |
| L-12 | El redondeo cobra el residuo, siempre a favor del prestamista. |
| L-13 | `PROMEDIO` como meta del día mezcla periodicidades y la infla. |
| L-14 | Créditos simultáneos por persona existen y no están modelados. |
| L-15 | No se calcula, no se almacena y no se topa la tasa efectiva. |

## 4.5 Marco regulatorio

Tasas efectivas implícitas: `30 x 40` da ~0,92 % diario (~2.700 % efectivo anual); `20 x 24` da ~1,51 % diario (~23.600 %). La tasa de usura certificada para julio de 2026 es 28,79 % efectivo anual en consumo y ordinario, con 62,66 % en consumo de bajo monto y 87,72 % en popular productivo urbano.

**Consecuencia de diseño:** el sistema calcula, persiste y **muestra** la tasa efectiva de cada crédito al operador. Es información para él, no un bloqueo. La primitiva `total = cuota x n` hace la tasa invisible por construcción, y eso es lo que se corrige.

**Posición del proveedor:** licenciante de software, sin participación en la cartera ni en los rendimientos. Requiere términos de servicio revisados jurídicamente antes de la primera venta.

## 4.6 DC legado no es lo que vence hoy

Se conservan dos magnitudes:

```
DC_LEGACY / PROMEDIO
= suma de cuota de todos los creditos activos

VENCE_HOY
= suma de obligaciones cuyo vencimiento contractual cae hoy
```

El primero existe para compatibilidad con las planillas.

El segundo es la meta operativa correcta para diario, semanal y quincenal.

## 4.7 Dos moras, no una

```
mora_legacy
= (fecha_reporte - 1 dia - inicia).days - #_C

mora_real
= derivada del calendario contractual de vencimientos
```

La primera reproduce el papel. La segunda sirve para riesgo, alertas y administración.

## 4.8 Tasa efectiva y política de cumplimiento

El sistema siempre calcula y persiste:

```
computed_effective_rate
calculation_version
applicable_reference
rule_version
```

La acción regulatoria debe ser una política configurable por producto y revisión jurídica:

```
SHOW
WARN
REQUIRE_OVERRIDE
BLOCK
```

No se hardcodea una decisión legal en la interfaz antes de validar el producto concreto con asesoría colombiana.

---

# PARTE 5 · Arquitectura general

## 5.1 El principio

**Local-first con servidor mínimo.** La base de datos vive en el teléfono y ahí se trabaja: cero espera, funciona sin señal, se siente instantáneo. El servidor es autoridad de identidad, licencia, llaves, consolidación y cálculo.

No es el diseño pesado donde el servidor atiende cada toque de pantalla. Tampoco es el diseño sin servidor, que no puede sostener licencia, inversionista remoto ni score entre rutas.

## 5.2 La pila

Línea base técnica verificada al 28 de julio de 2026:

```
postgres:18.4         base de datos + Row Level Security
powersync-service     1.23.3 stable
api (FastAPI)         0.140.7 - escrituras, score, PDF, licencia, OCR
web-admin (Next.js)   16.2.11 Active LTS - panel administrador
cloudflared           tunel hacia Cloudflare
```

Cliente móvil:

```
Flutter 3.44.7 stable
PowerSync Dart/Flutter SDK 2.3.3
```

Cinco procesos/servicios principales en servidor contando el panel web desplegado como servicio propio; el panel también puede desplegarse estático/edge según la decisión de infraestructura.

La regla es **último estable soportado**, no "último aunque sea beta". PostgreSQL 19 está en Beta 2 y no entra en producción.

## 5.3 Por qué no Supabase

Se evaluó y se descarta para esta arquitectura, pero con la comparación actualizada. La documentación oficial de Supabase self-hosted indica actualmente **2 cores / 4 GB mínimos** y **4 cores / 8 GB+ recomendados** para el conjunto completo; además permite retirar servicios que no se usen.

La decisión de no usarlo no se apoya en cifras infladas, sino en evitar duplicar servicios que este producto ya resuelve de otra manera.

Pero el argumento de fondo es la redundancia:

| Servicio | Para qué | Realidad |
|---|---|---|
| Realtime | sincronizar | Lo hace PowerSync |
| PostgREST | API automática | Las escrituras van por la API propia |
| GoTrue | autenticación | Telegram autentica al inversionista y administrador; el cobrador usa JWT propio |
| Studio | consola | `psql` o DBeaver |
| Analytics + Vector | logs | Peso puro |
| Storage + imgproxy | archivos | Cloudflare R2 |

Queda Postgres, que corre solo. Pagar 13 contenedores para usar uno.

## 5.4 Licencias

| Componente | Licencia |
|---|---|
| SDK de cliente de PowerSync | Apache 2.0 y MIT — abiertos |
| Servicio PowerSync | FSL-1.1-ALv2 — *source-available*, convierte a Apache 2.0 a los dos años |
| PostgreSQL | PostgreSQL License |
| FastAPI, WeasyPrint, Flutter | MIT / BSD |
| Colima | MIT |

La FSL permite usos distintos de un **Competing Use**, cuya definición incluye productos o servicios que sustituyan o ofrezcan funcionalidad sustancialmente similar a PowerSync. La aplicación de cobranza parece un uso de PowerSync como componente y no un producto de sincronización, pero antes de depender comercialmente de Open Edition se debe conservar una revisión de licencia y, preferiblemente, confirmación escrita del proveedor.

**Detalle de implementación:** PowerSync usa MongoDB por defecto para el almacenamiento de sus *buckets*, pero existe la variante con **Postgres como almacenamiento**. Se usa esa y desaparece Mongo.

## 5.5 Los cuatro repositorios

```
cobro-api        FastAPI - SQLAlchemy - WeasyPrint
                 auth - score - licencia - llaves - OCR - eventos

cobro-app        Flutter - PowerSync Dart SDK
                 app local-first del cobrador

cobro-web        Next.js - TypeScript
                 un solo código web con tres modos:
                 1. panel administrativo independiente
                 2. Mini App de Telegram para administrador remoto
                 3. Mini App de Telegram para inversionista

cobro-infra      Docker Compose - Colima - cloudflared
                 migraciones - semillas - respaldos - runbooks
```

No se crea un repositorio separado para la Mini App. Telegram Mini Apps son aplicaciones web: `cobro-web` reutiliza los mismos componentes, permisos y consultas agregadas.

### Autenticación de `cobro-web`

```
PANEL ADMINISTRATIVO INDEPENDIENTE
- sesion emitida por cobro-api
- contrasena robusta + MFA/TOTP o passkey
- cookies HttpOnly/Secure/SameSite
- revocacion de sesiones y auditoria

MODO TELEGRAM
- valida initData firmado por Telegram
- intercambia por sesion corta de cobro-api
- aplica rol ADMINISTRADOR o INVERSIONISTA
```

El inversionista no recibe PII. Su sesión solo puede consultar agregados y documentos sin nombres, teléfonos ni direcciones.

### Costo y despliegue del panel

El panel añade un contenedor y un código web, pero no exige un servidor adicional en el piloto ni en la primera instalación pagada: puede ejecutarse en el mismo nodo de aplicación detrás de Cloudflare Tunnel. Se separa físicamente cuando carga, disponibilidad o seguridad lo justifiquen.

## 5.6 Política de actualización tecnológica

Cada componente se fija a una versión exacta mediante lockfile o tag reproducible.

Antes de promover una actualización:

```
leer changelog
revisar CVE/security advisory
ejecutar pruebas unitarias
ejecutar integracion offline/sync
ejecutar fixtures financieros
ejecutar prueba de PDF
ejecutar prueba de cierre de jornada
```

No se actualiza producción automáticamente solo porque salió una versión nueva.

## 5.7 Sync Streams

PowerSync recomienda **Sync Streams** para proyectos nuevos. En la matriz oficial consultada el 27-jul-2026 figuran como **GA**.

Se usan porque permiten definir exactamente qué datos puede recibir cada cobrador.

La configuración de autorización debe derivar de identidad autenticada/claims confiables del servidor, nunca de un `route_id` libre enviado por el teléfono.

## 5.8 Por qué se mantienen panel web y Mini App

No son duplicados funcionales:

| Canal | Uso |
|---|---|
| App Flutter del cobrador | Trabajo diario, offline, escritura financiera |
| Panel web | Operación de oficina, configuración, búsqueda, cartera, caja y auditoría |
| Telegram Mini App | Consulta remota rápida y aprobaciones; acceso del inversionista |
| Bot de Telegram | Entrega automática de PDF y alertas |

La lógica de dominio, permisos y datos vive en `cobro-api`. Las tres interfaces no implementan reglas financieras distintas.

## 5.9 Decisión confirmada: Next.js para `cobro-web`

Se mantiene Next.js por una decisión funcional explícita:

```
panel web administrativo
+
Mini App de Telegram
+
una sola base de componentes
```

El costo de esta decisión queda reconocido:

```
autenticacion propia del panel
MFA/passkeys
sesiones
proteccion CSRF
gestion de sesiones/dispositivos
pipeline web
contenedor web
parches de seguridad
```

No se presenta como "gratis" ni como eliminación de complejidad. Se acepta porque el panel de oficina necesita una experiencia completa que la Mini App por sí sola no reemplaza.

Para no duplicar lógica:

```
auth y permisos - cobro-api
datos/calculos - cobro-api
componentes web - cobro-web
modo navegador y modo Telegram - mismo repositorio
```

---

# PARTE 6 · Convivencia con la infraestructura existente

Este proyecto es **independiente**. No comparte código, base de datos ni dominio con Nexus Core, Agent Zero, OpenClaw, Engram ni `cobropro`.

Si durante desarrollo/piloto utiliza el mismo Mac Mini, la única relación es de **convivencia física del host**. Nada de los otros proyectos puede tocarse y esta aplicación no depende de ellos.

## 6.1 Colima y Mac Mini: decisión pendiente

La Mac Mini M4 de 24 GB es candidata para desarrollo, pruebas o piloto ligero. Su capacidad real se evaluará cuando llegue la fase de despliegue: se revisarán servicios existentes, memoria, CPU, almacenamiento y runtime actual.

Colima, Docker Desktop u otro runtime no se seleccionan todavía. No se creará un perfil adicional sin auditoría. Producción comercial no dependerá obligatoriamente de la Mac Mini.

Si durante desarrollo se usa Colima, debe contar con recursos explícitos:

```bash
colima start --profile cobro \
  --cpu 2 --memory 4 --disk 40 --arch aarch64 \
  --vm-type vz --mount-type virtiofs
```

Nexus Core sigue en su propio perfil o en Docker Desktop, sin verse. Ninguno puede robarle memoria al otro.

## 6.2 Aislamiento adicional

| Medida | Detalle |
|---|---|
| Proyecto de Compose | `-p cobro` — red y volúmenes con espacio de nombres propio |
| Puertos | Rango **7100–7199**. No toca 5433 (`cobropro`), 5080 (Agent Zero), 8080 (llama-server), 7437 (Engram), 18789/18800 (OpenClaw) |
| Postgres | Instancia **propia dentro del contenedor**. Jamás la de 5433 |
| Límites | `deploy.resources.limits` explícito en cada contenedor |
| Volúmenes | Ruta dedicada `~/cobro/data`, fuera de cualquier carpeta de Nexus |

## 6.3 Verificación antes de instalar

```bash
lsof -iTCP -sTCP:LISTEN -P | grep -E ':(71[0-9][0-9])'   # rango libre
colima list                                               # perfiles activos
docker context ls                                         # contexto correcto
```

Radiografía primero, instalación después.

---

# PARTE 7 · Cloudflare

Se aprovecha la cuenta existente. Todo bajo nombres propios para no cruzarse con el otro proyecto.

| Servicio | Uso | Costo |
|---|---|---|
| **Registrar** | Dominio del producto | ~$10/año, a precio de costo |
| **DNS** | Zona del dominio nuevo | Gratis |
| **Tunnel** | Expone el Mac Mini sin abrir puertos del router, sin IP fija, funciona detrás de CGNAT | Gratis |
| **R2** | PDFs, fotos de planillas, respaldos cifrados | 10 GB gratis, luego ~$0,015/GB. **Sin costo de salida** |
| **Pages** | Mini App de Telegram (archivos estáticos) | Gratis |
| **WAF y límite de tasa** | Protección básica de la API; capacidades dependen del plan | Incluye capacidades en Free, con límites |

## 7.1 Cloudflare Tunnel es la pieza clave

Resuelve de un golpe: sin IP fija, sin abrir puertos en el router de la casa, TLS automático, protección ante denegación de servicio, y funciona aunque el proveedor use direccionamiento compartido.

Y elimina dos contenedores: no hace falta Caddy —Cloudflare termina el TLS— ni MinIO —R2 hace de almacenamiento—.

## 7.2 Separación del otro proyecto

```
Zona DNS      dominio propio, distinto
Tunel         nombre 'cobro-prod', credenciales propias
R2            bucket 'cobro-docs', token con alcance solo a ese bucket
Pages         proyecto 'cobro-web (modo Telegram Mini App)'
Reglas WAF    aplicadas a la zona nueva unicamente
```

Una cuenta de Cloudflare aloja muchas zonas y muchos túneles sin interferencia. La disciplina está en el nombrado y en el alcance de los tokens.
# PARTE 8 · Modelo de datos

## 8.1 Principios

**Todo el dinero operativo en COP se guarda como entero de pesos.** Sin coma flotante.

**Tasas, porcentajes y resultados de cálculos de tasa** usan `NUMERIC/DECIMAL`, nunca `float`.

**Nada derivado se vuelve fuente primaria.** `abo`, `saldo`, `#_C`, `pico`, mora legacy y agregados se calculan desde los eventos/datos contractuales. Pueden existir vistas/materializaciones para rendimiento, pero siempre reconstruibles.

**UUIDv7** para identificadores generados de forma distribuida y ordenable temporalmente.

**Multiempresa por fila.** `negocio_id` en todas las tablas de dominio más Row Level Security y validación de aplicación.

**Ruta en el crédito, no en el cliente.**

**Pagos append-only.** Una corrección es un evento nuevo.

## 8.2 Tablas

```sql
negocio
  id, nombre, nit, pais='CO', moneda='COP', zona_horaria='America/Bogota',
  plan, estado_suscripcion, paid_through_at, creado_el

usuario
  id, negocio_id, rol, nombre, documento,
  telegram_id, activo, creado_el
  -- rol: INVERSIONISTA | ADMINISTRADOR | COBRADOR

ruta
  id, negocio_id, nombre, cobrador_id, activa,
  version, creado_el

cliente
  id, negocio_id,
  tipo_documento, documento_normalizado,
  identity_status,
  primer_apellido, segundo_apellido, nombres,
  telefono_1, telefono_2,
  direccion, barrio, ciudad, ocupacion,
  creado_el
  -- identity_status: PROVISIONAL | VERIFIED | POSSIBLE_DUPLICATE

credito
  id, negocio_id, cliente_id, ruta_id,
  origination_type,
  cuota, n_cuotas, monto, total,
  periodicidad, dia_semana, ancla_quincenal,
  fecha_inicio, estado, credito_anterior_id,
  tasa_efectiva_anual, residuo_redondeo,
  version, creado_el
  -- origination_type: NEW | RETURNING | PARALLEL | RENEWAL
  -- total = cuota x n_cuotas  (autoridad)

cuota_programada
  id, negocio_id, credito_id,
  numero, fecha_vencimiento, monto,
  estado
  -- fuente para VENCE_HOY y mora real

pago
  id, negocio_id, credito_id, jornada_id,
  cobrador_id, dispositivo_id,
  tipo, reversal_of_payment_id,
  monto,
  registrado_el_dispositivo,
  recibido_el_servidor,
  clave_idempotencia,
  nota
  -- tipo: PAYMENT | REVERSAL
  -- UNIQUE(negocio_id, clave_idempotencia)
  -- sin UPDATE/DELETE financiero

renovacion
  id, negocio_id,
  credito_viejo_id, credito_nuevo_id,
  saldo_anterior,
  pago_efectivo,
  saldo_refinanciado,
  monto_nuevo,
  dinero_nuevo_entregado,
  creado_por, creado_el

jornada
  id, negocio_id, ruta_id, cobrador_id, fecha,
  estado,
  opening_base, opening_carry,
  esperado, contado, diferencia, diferencia_motivo,
  sobrante_manana,
  cerrada_local_el, recibida_servidor_el, sincronizada_el
  -- estado: OPEN | CLOSING | CLOSED_LOCAL_PENDING_SYNC | CLOSED_SYNCED
  -- UNIQUE(negocio_id, ruta_id, fecha)

movimiento_caja
  id, negocio_id, jornada_id,
  tipo, naturaleza,
  monto, nota, creado_por, creado_el

dispositivo
  id, negocio_id, usuario_id,
  huella, modelo, plataforma,
  autorizado_por, autorizado_el, revocado_el,
  ultima_validacion_servidor

score_snapshot
  id, negocio_id, cliente_id,
  score_status, score, semaforo, tendencia,
  factores_json, score_version, calculado_el

alerta
  id, negocio_id, cliente_id, ruta_id,
  tipo, severidad, mensaje,
  creada_el, resuelta_el
```

## 8.3 Invariantes estructurales

### La ruta pertenece al crédito
Cada cobrador recibe únicamente sus créditos autorizados.

### El total contractual lo manda el plan
`total = cuota x n_cuotas`. El 20% ayuda a formar la propuesta, pero no se usa para reescribir el total después del redondeo.

### La renovación es un evento de primera clase
`saldo_anterior = pago_efectivo + saldo_refinanciado` y se guarda aparte: `dinero_nuevo_entregado`.

### La mora real necesita calendario
`periodicidad` por sí sola no basta. `cuota_programada` permite calcular diario/semanal/quincenal correctamente.

## 8.4 Identidad de cliente

El documento es el identificador fuerte cuando existe, pero la migración histórica tiene clientes sin documento. Nunca se fusionan dos clientes automáticamente por parecido de nombre.

Proceso: sin documento -> PROVISIONAL, documento confirmado -> VERIFIED, coincidencia sospechosa -> POSSIBLE_DUPLICATE.

En la cartera histórica analizada, los dos apellidos aportan más señal discriminante que el nombre de pila. El nombre de pila es frecuente y ruidoso, por lo que nunca se usa como criterio principal de emparejamiento.

## 8.5 Score histórico

No se guarda solo el último score. Cada cálculo crea `score_snapshot`, de modo que se pueda responder: por qué estaba amarillo en agosto, cuándo empezó a deteriorarse, qué versión del algoritmo tomó esa decisión.

---

# PARTE 9 · Sincronización

## 9.1 Alcance por rol

| Rol | Qué baja al dispositivo |
|---|---|
| Cobrador | `negocio_id = X AND ruta_id = Y` |
| Administrador | `negocio_id = X`, todas las rutas |
| Inversionista | **nada** |

El inversionista no sincroniza. Recibe agregados por Mini App y PDF. Así la regla de que nunca ve datos de deudores no depende de que la interfaz se los oculte: los datos no llegan al aparato.

## 9.2 Por qué no hacen falta CRDTs

Cada ruta es dueña exclusiva de sus filas. Ningún cobrador toca las de otro. Juntar la información no es fusionar: es sumar.

## 9.3 Quién manda sobre qué

| Dato | Dueño |
|---|---|
| Pagos, movimientos, jornada, caja | La ruta |
| Créditos originados en la calle | La ruta |
| Nombre, documento, dirección, teléfono | El administrador |
| A qué ruta pertenece un crédito | El administrador |
| Productos, porcentajes, topes | El administrador |
| Score | El servidor |

El administrador ve los pagos pero no los corrige. Si hay error, lo reversa quien lo registró y queda el rastro.

## 9.4 Los tres momentos de sincronización

```
ABRIR DIA        descarga ruta, base, hora del servidor, licencia
DURANTE          oportunista: sube cuando hay senal
CERRAR DIA       boton explicito. Sube todo, cierra la jornada,
                 genera el PDF y dispara el informe de Telegram.
```

Si no hay señal al cerrar, el cierre se completa igual en el teléfono y queda marcado como pendiente de subir. Al haber señal, sube solo y entonces el panel puede mostrar el cierre.

El cierre es idempotente: si la subida se corta a la mitad, el reintento no duplica nada.

## 9.5 Aislamiento de ruta de extremo a extremo

El JWT/credencial del cobrador contiene como mínimo: sub, negocio_id, role, route_id, device_id, exp.

Nunca: route_id = parámetro libre enviado por el cliente.

Prueba de seguridad obligatoria: token R1 + intento de consultar R2 -> 0 filas / acceso denegado.

## 9.6 Cierre offline: lo que sabe cada lado

Si el cobrador pulsa TERMINAR JORNADA sin señal: TELÉFONO = CLOSED_LOCAL_PENDING_SYNC. SERVIDOR/ADMIN = último estado conocido + última hora de sincronización + "cierre no recibido".

## 9.7 Conflictos que no se resuelven con last-write-wins

pago append-only + idempotencia, reversión nuevo evento, renovación transacción + version check, reasignación ruta operación administrativa versionada, cierre jornada idempotency key + snapshot.

---

# PARTE 10 · La aplicación del cobrador

## 10.1 El principio: la hoja es la aplicación

Ellos no quieren una app. Quieren actualizar esa hoja. La pantalla no es un menú con opciones: es la planilla.

Mismas columnas, mismo orden, mismos nombres: Cliente, Cuota, Día, #_C, Abono, Pico, Monto, Abo, Saldo, Mora.

La columna Abono es la única editable. Es exactamente lo que hoy hacen con el esfero.

La diferencia: hoy el cobrador escribe 30 y el saldo nuevo lo ve mañana. Aquí la fila se recalcula delante de él.

## 10.2 La acción principal

La mayoría de abonos son exactamente el valor de la cuota. Entonces cada fila lleva un botón que ya dice el monto —"Pagó 30.000"— y el teclado queda para el que paga distinto. Dos toques en vez de seis.

## 10.3 Pantallas

ABRIR DÍA, MI RUTA (hoja viva), ABONAR (teclado grande con atajos), RECIBO, PRESTAR, RENOVAR, GASTO, TERMINAR JORNADA, MI PDF.

## 10.4 Qué NO ve el cobrador

cartera total del negocio, otras rutas, rentabilidad, datos de la suscripción, el score de otras rutas.

## 10.5 La pantalla de renovar

Debe X, Paga en efectivo ahora 0, Se pasa al nuevo X. Crédito nuevo Y, Recargo 20%, Queda debiendo Z. LE ENTREGA (dinero nuevo) en grande. Advertencia: Esto no cuenta como cobro.

## 10.6 El cierre del día

Base recibida + Cobrado en efectivo - Prestó a clientes - Gasolina - Oficina - Ahorro = Debería tener. Contó [___]. Diferencia.

Si la diferencia no es cero, exige motivo y avisa al administrador. No cierra en silencio.

## 10.7 PDF desde el teléfono

La aplicación móvil genera localmente los PDF operativos usando los recursos normales del teléfono, sin conexión:

- PDF de `TERMINAR JORNADA`;
- comprobante o recibo de pago;
- hoja o resumen de ruta;
- estado de cuenta del cliente;
- reportes operativos que se definan para el cobrador.

Generación con paquete `pdf` de Dart:

- funciona sin conexión;
- se construye desde datos estructurados y snapshots locales;
- permite vista previa, guardar, compartir e imprimir;
- se conserva pendiente de sincronización cuando no hay internet.

El PDF de `TERMINAR JORNADA` se genera desde el mismo snapshot inmutable usado para cerrar la jornada, incluyendo: negocio, ruta, cobrador, fecha y hora, identificador de jornada, base de apertura, arrastre, cobrado real, desembolsos, dinero nuevo entregado, gastos, ahorro, vales, transferencias, efectivo esperado, efectivo contado, diferencia, motivo de diferencia, sobrante para el día siguiente, resumen de pagos, resumen de movimientos, resumen de renovaciones, versión y hash del cierre, estado de sincronización.

No debe recalcular cifras con una fórmula distinta a la del snapshot. Nunca debe existir PDF móvil con un total y servidor con otro total.

El servidor almacena o regenera posteriormente una copia canónica del PDF usando un motor open source de generación documental y CPU normal. No usa inteligencia artificial, modelos de lenguaje, visión por computadora ni OCR. No requiere GPU. Sirve para archivo, descarga web, Telegram, recuperación y auditoría. La selección concreta del motor se realizará en la fase de reportes.

## 10.8 El botón TERMINAR JORNADA

Paso 1: congelar entrada. Paso 2: comprobar consistencia local. Paso 3: recalcular el día. Paso 4: contar caja. Paso 5: confirmar una sola vez. Paso 6: sellar (OPEN -> CLOSING -> CLOSED_LOCAL_PENDING_SYNC). Paso 7: preparar mañana automáticamente. Paso 8: sincronizar y reportar.

## 10.9 Semáforo en la hoja viva

Estados: gris (historial insuficiente), verde (favorable), amarillo (precaución), rojo (riesgo alto). Al abrir el cliente se muestran razones breves.

## 10.10 Qué agregados se ocultan al cobrador

CARTERA X COBRAR, cartera agregada de la ruta, cartera global, rentabilidad.

---

# PARTE 11 · La aplicación del administrador

Panel web completo como puesto principal de oficina. Acceso móvil complementario desde Flutter/Telegram Mini App.

Pantallas: HOY (una fila por ruta), RUTAS, CLIENTES, CARTERA, CAJA, APROBACIONES, PLANILLA, CONFIGURACIÓN, SUSCRIPCIÓN.

## 11.1 Panel web inteligente

Primera pantalla: Cobro real, Refinanciado, Dinero nuevo entregado, Rutas cerradas/pendientes, Diferencias de caja, Alertas críticas.

## 11.2 Salud de cartera

Solo administrador/inversionista según permisos. Estados: gris, verde, amarillo, rojo. Tendencias: mejorando, estable, empeorando.

## 11.3 No mezclar DC legado con meta real

DC/PROMEDIO para compatibilidad histórica. VENCE HOY para obligación contractual del día. Nunca presentarlos como la misma cifra.

---

# PARTE 12 · El inversionista

Rol incluido en v1 y activable por negocio. Bot de Telegram: informe diario en PDF empujado. Mini App de Telegram: consulta remota. Sin inicio de sesión, sin contraseñas, sin tienda de aplicaciones. Ve capital colocado, entró de verdad, refinanciado, cartera neta, atraso por alturas, salud del portafolio. Ni un solo dato personal de deudor.

---

# PARTE 13 · Seguridad y anti-manipulación

## 13.1 El servidor es la autoridad

Los pagos se validan en el servidor al sincronizar. Los números del teléfono son provisionales hasta que suban. El reloj es el del servidor.

## 13.2 Registro que no se puede editar

La tabla `pago` es de solo inserción. No hay UPDATE ni DELETE. Una reversión es una fila nueva con motivo y autor. Cada pago lleva clave de idempotencia.

## 13.3 Un dispositivo por cobrador

Una ruta queda atada a una huella de dispositivo. Cambiar de teléfono exige aprobación del administrador.

## 13.4 Medidas en la aplicación

Ofuscación Flutter, base local cifrada con SQLite3MultipleCiphers, TLS estándar, Play Integrity, advertencia si modo desarrollador activo.

## 13.5 Detección de anomalías en el servidor

Pago exactamente igual al saldo a hora inusual, muchos pagos en menos de sesenta segundos, diferencia de caja repetida, silencio largo seguido de sincronización, patrón de renovación que sube saldo sin bajar deuda. Ninguna bloquea sola: todas levantan bandera.

## 13.6 Llaves y respaldos

Cifrado en sobre con 'age', llave de datos por negocio cifrada con llave maestra, llave maestra respaldada en gestor de contraseñas y en papel. Tres copias de backup: PostgreSQL, R2 cifrado, destino independiente.

## 13.7 Seguridad de rutas

API y sincronización validan conjuntamente: negocio_id, role, route_id, device_id, token signature, token expiry.

## 13.8 Seguridad del cierre

El cierre guarda snapshot firmado: ids de pagos, ids de movimientos, totales, efectivo esperado, efectivo contado, diferencia, última secuencia local. Reintento determinista.

## 13.9 Registro de seguridad

Eventos mínimos: login, alta/revocación dispositivo, cambio de ruta, reversión de pago, ajuste de caja, cierre con diferencia, cambio de configuración financiera, cambio de suscripción.

---

# PARTE 14 · El backend inteligente

## 14.1 El motor de riesgo

Regresión logística con variables de comportamiento: promedio de días de atraso, días de retraso en crédito anterior, meses como cliente, atraso máximo, número de renovaciones, créditos paralelos, exposición total, tendencia 30 días.

## 14.2 Cómo se implementa

Año uno: tarjeta de puntuación transparente. Después: regresión logística comparada contra la tarjeta. Se guarda score_version con cada cálculo.

## 14.3 Tres restricciones

Nunca decidir por barrio, ocupación, sexo ni nombre. El score aporta a la decisión, no la toma. Arranque en frío honesto: sin historia no hay score (gris/INSUFFICIENT_DATA).

## 14.4 Lo demás que hace el backend

Conciliación, predicción de recaudo, alerta de fuga, renovación forzada, tasa efectiva, anomalías de caja, orden de ruta, asistente administrativo, bot proactivo.

## 14.5 Arranque en frío

Cliente migrado trae estado, no historia fechada completa. score_status = INSUFFICIENT_DATA, score = NULL, semaforo = GRIS. Alertas determinísticas sí funcionan desde el primer día.

## 14.6 Historia del score

Cada cálculo se almacena como score_snapshot. Se puede explicar qué factores cambiaron.

## 14.7 Inteligencia por ruta

El panel muestra distribución de semáforos por ruta sin compartir clientes entre cobradores.

## 14.8 Predicción no sustituye conciliación

La predicción de recaudo es estimación. La caja y el saldo son aritmética exacta. Nunca una predicción puede cambiar un pago, un saldo, una jornada ni una diferencia de caja.

## 14.9 Asistente conversacional del administrador

Chatbot para consultar la operación en lenguaje natural desde panel web y Telegram.

## 14.10 Arquitectura segura del chatbot

El modelo no consulta directamente la base, no escribe SQL, no calcula dinero, no ejecuta operaciones financieras. Flujo: pregunta -> intérprete -> catálogo cerrado -> backend ejecuta query probada -> backend devuelve datos -> modelo redacta.

## 14.11 Catálogo cerrado de consultas

Herramientas: get_today_summary, get_route_close_status, get_real_collection, get_refinanced_balance, get_due_today, get_portfolio_summary, get_risk_distribution, compare_routes, etc. No existe run_sql ni execute_arbitrary_query.

## 14.12 Permisos y privacidad

Administrador consulta datos de su negocio. Inversionista solo agregados autorizados sin PII. Cobrador solo su ruta.

## 14.13 Respuesta trazable

Toda respuesta muestra: fecha/hora de corte, zona horaria, período, ruta/filtros, query_version, última sincronización.

## 14.14 El chatbot no modifica dinero en v1

Read-only en v1. No puede crear crédito, registrar pago, reversar, cerrar jornada, cambiar ruta, aprobar diferencia, reactivar suscripción.

## 14.15 Bot proactivo por reglas

El sistema envía avisos por reglas determinísticas del backend: ruta no cerrada, cierre con diferencia, cobrador sin sincronizar, cliente en rojo, suscripción por vencer.

## 14.16 Auditoría del asistente

Guardar: usuario, rol, canal, pregunta, intención, herramientas, query_version, filtros, respuesta, fecha/hora, latencia, errores. No guardar secretos ni más PII de la necesaria.

## 14.17 Pruebas obligatorias del chatbot

R1 solo ve R1, inversionista no recibe PII, no existe herramienta SQL, pregunta ambigua pide aclaración, ruta offline informa corte incompleto, dashboard y chatbot devuelven mismo valor.

---

# PARTE 15 · Importación y contingencia por foto

## 15.1 Migración inicial

El operador fotografía sus planillas. Validación cruzada: suma de cuota = PROMEDIO, suma de saldo = CARTERA X COBRAR, cuota x n = total de cada fila. Si no cuadra, señala el renglón.

## 15.2 Contingencia

Si el teléfono se dañó o usó papel, se fotografía la planilla trabajada y se pone al día.

## 15.3 Tecnología

La RTX 5090 **no es servidor de Daily System**. No se usa para producción, piloto, generar PDF, OCR operativo, visión 24/7 ni recibe automáticamente documentos de clientes. Daily System debe funcionar con la torre apagada.

La RTX 5090 queda fuera de la arquitectura operativa. Su uso se limita a programación, compilación, pruebas manuales y experimentos autorizados expresamente por el dueño.

La importación de planillas (fotografía → OCR → validación) se ejecuta en fase posterior. Se seleccionará motor de OCR cuando se diseñe el flujo de importación.

## 15.4 La regla que protege al producto

Lo impreso se lee con alta exactitud. Lo escrito a mano, no. La aplicación muestra la foto al lado de las filas extraídas y el operador confirma o corrige. Los números manuscritos nunca se aplican solos.

---

# PARTE 16 · PDF y Telegram

## 16.1 Los informes

Al cerrar cada ruta, PDF por Telegram: entró de verdad, refinanciado, prestado, clientes que pagaron, estado de caja, meta y cartera. Sin nombres ni datos personales de deudores.

## 16.2 Por qué Telegram y no WhatsApp

Telegram: gratis, sin trámite, archivos sin restricción, Mini App. WhatsApp cuesta por mensaje de utilidad. Solución: bot para flujo automático, PDF se puede compartir con botón nativo a WhatsApp.

## 16.3 Generación

```text
Generar PDF: datos estructurados → plantilla → PDF
  - Dispositivo: paquete `pdf` de Dart, offline
  - Servidor: motor open source con CPU (no GPU, no IA, no LLM)

Leer documentos externos: PDF escaneado o fotografía → OCR → reconstrucción de datos → revisión humana → importación
  - PaddleOCR u otro motor: se selecciona en fase posterior
```

El PDF debe verse impreso, no como página web. La generación de PDF está separada de la lectura con OCR.

## 16.4 Reporte automático al terminar jornada

Disparador: jornada CLOSED_SYNCED. Flujo: cierre local -> sincronización -> validación servidor -> PDF oficial -> panel actualizado -> Telegram.

## 16.5 Dos versiones de planilla por permisos

Administrador: planilla completa + PROMEDIO/DC + CARTERA X COBRAR. Cobrador: hoja operativa sin cartera agregada.

---

# PARTE 17 · Dirección visual

Cifras tabulares obligatorias. Casi ningún borde, espaciado generoso. El color solo significa: verde entró, rojo salió. Movimiento: cuando el cobrador escribe, los números cuentan hasta su nuevo valor. Un botón por pantalla, objetivo táctil mínimo 56 píxeles.

## 17.1 Estado del arte sin sacrificar ergonomía

Flutter estable + Material 3. 60 fps, sin espera de red, contraste AA mínimo, teclado numérico grande, haptics discretos al confirmar dinero, modo oscuro si no sacrifica legibilidad.

## 17.2 El diseño se prueba al sol y con una mano

Validado con: brillo alto, una mano, dedos grandes, conectividad mala, 50-150 filas, scroll largo.

---

# PARTE 18 · Despliegue y costos

## 18.1 Dónde corre qué

Desarrollo/piloto: Mac Mini candidata + Colima o Docker Desktop por evaluar + Cloudflare Tunnel. Producción: VPS/hosting después de revisión de privacidad, ubicación y benchmark. Producción comercial no dependerá obligatoriamente de la Mac Mini.

## 18.2 Costos

Arranque y piloto: Mac Mini M4 candidata por evaluar, Cloudflare según plan, dominio pago anual, PowerSync Open Edition sin tarifa, Telegram sin tarifa del bot, Play Store tarifa de registro.

Referencia Hetzner (jul-2026, sin IPv4/impuestos): CX23 $6.49/mes, CAX11 $6.99/mes, CX33 $9.99/mes. Decisión de producción exige región jurídicamente aprobada, benchmark, precio visible en orden.

## 18.3 Lo que sí cuesta

Su tiempo. 50 clientes que no manejan tecnología llaman. Instalación se cobra aparte, horario de soporte va en contrato.

## 18.4 Región de producción y datos personales

Antes del primer cliente pago: documentar responsable, encargado, proveedores, ubicación de almacenamiento, flujos, contratos. Ley 1581 de 2012. Región se selecciona después de revisión de privacidad.

## 18.5 El OCR local también es un flujo de datos

Si una planilla viaja de producción a RTX 5090: origen, destino, retención, cifrado, borrado posterior deben documentarse.

---

# PARTE 19 · Etapas de entrega

**Etapa 1 — que funcione:** Multiempresa con RLS, clientes, créditos, calendario, hoja viva Flutter, abonos idempotentes, panel web básico, PDF planilla, PowerSync Sync Streams.

**Etapa 2 — que cuadre:** Jornada, caja, renovación, TERMINAR JORNADA transaccional, diferencia, sobrante encadenado, PDF oficial, Telegram.

**Etapa 3 — que se venda:** Suscripción, licencia con bloqueo, alta de negocios, Mini App inversionista, dispositivo autorizado.

**Etapa 4 — que se migre fácil:** Importación por foto con validación cruzada, contingencia.

**Etapa 5 — que sea inteligente:** Tarjeta de puntuación, semáforo, detección anomalías, predicción, chatbot read-only, bot proactivo.

El orden no es negociable. El score va de último porque necesita historial real.

---

# PARTE 20 · Decisiones pendientes

| # | Decisión | Opciones |
|---|---|---|
| 1 | Nombre del producto y dominio | — |
| 2 | Qué se cobra | Por ruta activa, por cobrador, por cliente activo, plano por rangos |
| 3 | Precio mensual y plan anual | — |
| 4 | Días de gracia tras vencimiento | 0 = bloqueo el mismo día |
| 5 | Duración permiso sin sincronizar | 72 horas iniciales, limitada por subscription_paid_through |
| 6 | Prueba gratis | — |
| 7 | Quién hace carga inicial | Proveedor como servicio o cliente solo |
| 8 | Instalación aparte | — |
| 9 | Número de inversionistas | Uno o varios con participaciones |
| 10 | Pago suscripción v1 | Cerrado: Nequi + Bancolombia manual |
| 11 | Crédito en calle inmediato o pendiente | — |
| 12 | Cobrador sin sincronizar 3 días | Aviso, limitación, bandera |
| 13 | Umbral verificación automática | 20 negocios activos recomendado |

## 20.0 Escalamiento de Nequi y Bancolombia

Volumen bajo: comprobante + revisión manual. Medio: importación de movimientos. Alto: integración bancaria/pasarela. SLA: reactivación en menos de 30 minutos.

## 20.1 Decisiones técnicas ya cerradas

Colombia, local-first, Flutter app cobrador, panel web + Telegram Mini App, PostgreSQL, PowerSync Sync Streams, TERMINAR JORNADA, aislamiento negocio+ruta+dispositivo, Nequi+Bancolombia, PDF local+servidor.

## 20.2 Decisiones que no bloquean desarrollo temprano

Nombre comercial, dominio, plan anual y precio final pueden cerrarse antes de Etapa 3.

---

# PARTE 21 · Riesgos

Dependencia de PowerSync (mitigación: fijar versión, lógica de negocio fuera del motor). Exposición legal del proveedor (términos de servicio, tasa efectiva visible). Datos personales Colombia (Ley 1581, contrato de tratamiento). Concentración de clientes (plan anual). Copia (ventaja: validación cruzada de planilla). Reconocimiento escritura a mano (se vende como asistida). Colisión entre rutas (claims firmadas, RLS). Cierre parcial/repetido (idempotencia). Falsa inteligencia (gris hasta historial). Tecnología beta (estable/LTS).

---

# PARTE 22 · Matriz de aceptación y no regresión

## 22.1 Fixtures financieros

Legado básico: cuota=30, n=40, abo=260 -> total=1200, saldo=940, #_C=8, pico=20. Caja R4: 275+805-400-20-18-50=592. Renovación: saldo_anterior=2740, pago_efectivo=0, saldo_refinanciado=2740, monto_nuevo=3000, dinero_nuevo_entregado=260.

## 22.2 Aislamiento de rutas

Token R1 lee R1=OK, R1 lee R2=DENY, R1 escribe R2=DENY, negocio A accede B=DENY.

## 22.3 Offline y sincronización

Descargar ruta, cortar Internet, registrar 20 pagos, renovar, gastos, TERMINAR JORNADA, cerrar/reabrir app, preparar día siguiente, recuperar Internet, sincronizar. Resultado: 20 pagos exactos, 0 duplicados, 1 renovación, 1 cierre, caja exacta, mismo saldo local/servidor.

## 22.4 TERMINAR JORNADA

Atómico: o queda OPEN o queda cerrado localmente con snapshot válido. Nunca mitad de pagos incluidos, carry sin cierre, PDF con un total y servidor con otro.

## 22.5 UI

50, 100, 150 filas. Pantalla pequeña, sol, una mano, TalkBack, texto aumentado. Cobro normal no debe requerir navegar por formularios innecesarios.

## 22.6 PDF

Columnas, orden, totales, PROMEDIO/DC, CARTERA X COBRAR, mora legado contra fixtures históricos.

## 22.7 Seguridad

RLS, Sync Streams, JWT expirado, token otro dispositivo, idempotencia, replay cierre, revocación dispositivo, backup restore, secretos, R2 desde R1.

## 22.8 Asistente conversacional

Dashboard y chatbot mismo valor, no herramienta SQL, no calcula montos, R1 no obtiene R2, inversionista no PII, ruta offline se marca incompleta, prompt injection no altera herramientas.

## 22.9 Definición de terminado

unit test, integration test, offline test, sync/retry test, audit test, permission test. Belleza visual es requisito pero nunca reemplaza estos gates.

---

*Fin del documento maestro.*


---

## Apéndice A · Evidencia técnica consultada — 28 de julio de 2026

Esta sección no reemplaza el pinning de implementación. Registra qué se verificó, dónde y cuándo. Antes de iniciar el repositorio y antes de cada release: volver a consultar la fuente, fijar patch exacto, guardar lockfiles/digests, ejecutar la matriz de no regresión.

### Flutter

Propuesta de pin inicial: Flutter 3.44.7. Documentación oficial indica que refleja Flutter 3.44.7. Consultado: 27-jul-2026.

### FastAPI

Release observada: FastAPI 0.140.7. La serie 0.140 recibió parches el 27-jul-2026. No se fija "0.140.x" flotante. Consultado: 27-jul-2026.

### PostgreSQL

Propuesta de pin inicial: PostgreSQL 18.4. Release 18.4: 14-may-2026. PostgreSQL 19 Beta 2: 16-jul-2026. Beta no se utiliza en producción. Consultado: 27-jul-2026.

### Next.js

Propuesta de pin inicial: Next.js 16.2.11. Comunicación oficial del 20-jul-2026 denomina 16.2.11 Active LTS. La rama 16.3 aparece en publicaciones Preview. Consultado: 27-jul-2026.

### PowerSync

Propuesta de pin inicial: PowerSync Service 1.23.3 stable, Dart/Flutter SDK 2.3.3. Service 1.23.3 publicado 07-jul-2026. SDK 2.3.3 publicado 28-jul-2026. EncryptionOptions integra SQLite3MultipleCiphers desde SDK 2.0. Sync Streams: GA. Flutter SQLCipher: Beta (alternativa no elegida). Consultado: 27-jul-2026.

### Licencia de PowerSync

FSL define Competing Use de forma amplia. La plataforma usa PowerSync como componente, no vende sincronización como producto autónomo. Se exige: revisión de licencia, confirmación escrita, versión fijada, plan de salida, lógica de negocio fuera del motor.

### Cloudflare Tunnel

Crea conexiones salientes. No requiere IP pública ni abrir puertos entrantes. Cuatro conexiones persistentes hacia al menos dos centros de datos. Consultado: 27-jul-2026.

### Cloudflare R2

Standard storage USD 0.015/GB-month. Free tier 10 GB-month. Egress sin cargo de ancho de banda. Consultado: 27-jul-2026.

### Supabase self-hosted — comparación

Mínimo 2 CPU / 4 GB RAM, recomendado 4 CPU / 8 GB+ RAM. Se descarta por redundancia arquitectónica.

### Hetzner — precios orientativos

Ajuste para nuevas órdenes: 15-jun-2026. CX23 USD 6.49/mes, CAX11 USD 6.99/mes, CX33 USD 9.99/mes. CPX22 no se utiliza en estimación. Consultado: 28-jul-2026.

### Telegram Mini Apps

Validación de initData, almacenamiento seguro Keychain/Keystore, hasta 10 elementos de SecureStorage. Consultado: 27-jul-2026.

### Play Integrity

Cuota diaria predeterminada: 10,000 solicitudes por proyecto. Consultado: 27-jul-2026.

### Protección de datos Colombia

Ley 1581 de 2012, SIC Circular Externa 002 de 2025. No sustituyen revisión jurídica del contrato, hosting, OCR y subencargados.

### Tasas certificadas — julio de 2026

Superintendencia Financiera: Consumo y ordinario 28.79% EA, Consumo bajo monto 62.66% EA, Popular productivo urbano 87.72% EA. La modalidad aplicable no se decide solo por el nombre comercial.

---

## Apéndice B · Decisión confirmada del panel y la Mini App

La decisión queda confirmada: el producto requiere panel web administrativo completo, administrador e inversionista requieren acceso remoto por Telegram, una sola aplicación web evita duplicar componentes.

Se aprueba una sola aplicación web: cobro-web. Construida con Next.js 16.2.11 como pin inicial.

Modo 1: panel administrativo independiente con login propio, MFA/passkey, sesiones, gestión de dispositivos, cartera, caja, configuración, reportes, auditoría.

Modo 2: Telegram Mini App. La misma aplicación detecta y valida initData y expone administrador remoto, inversionista, aprobaciones rápidas, consulta de agregados.

Impacto presupuestario: un repositorio web, un pipeline de build, un contenedor web, auth y sesiones dentro de cobro-api, mismo VPS durante piloto/primeras cuentas.

---

## Apéndice C · Decisiones abiertas que sí requieren al dueño

nombre y dominio, métrica/precio de suscripción, precio de instalación, plan anual, prueba gratis, uno o varios inversionistas con participaciones, activación inmediata o aprobación de créditos originados en calle, umbral definitivo para conciliación manual de suscripciones.

Decisiones ya expresamente cerradas: Colombia, Nequi, Bancolombia, administrador, cobrador, inversionista, bot de Telegram con PDF, Mini App de Telegram, Cloudflare, PDF móvil obligatorio y offline con `pdf` de Dart, snapshot inmutable para cierre, RTX 5090 fuera de arquitectura operativa, OCR pendiente para fase posterior, Mac Mini y Colima pendientes de evaluación, TERMINAR JORNADA, rutas sin cruce, hoja viva.


*Fin del documento maestro.*
