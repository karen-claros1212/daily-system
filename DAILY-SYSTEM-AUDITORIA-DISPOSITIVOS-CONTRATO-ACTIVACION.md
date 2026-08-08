# AUDITORÍA DEL SISTEMA DISPOSITIVO + CONTRATO DE ACTIVACIÓN

> **Entregable previo a código — dictamen de auditoría externa 2026-08-06.**
> **Revisión documental vigente: 4 — PASS DOCUMENTAL** (actualizada 2026-08-06; el encabezado histórico de la revisión 2 queda **SUPERADA/REEMPLAZADA** por la revisión 4 y se conserva como historia documental — ver conclusión al final del documento).
> Historial: revisión 1 (dictamen inicial) → revisión 2 (encabezado original, **SUPERADA**) → revisión 3 → **revisión 4 (vigente):** correcciones 1–7 aprobadas conceptualmente con condición + 4 precisiones del protocolo de canje (intento de un solo uso, nonce CSPRNG, transacción con bloqueo, serialización byte a byte) + matriz de librerías móviles verificada (sección 12) + **decisión de serialización resuelta: JCS (RFC 8785), CBOR canónico descartado (sección 13)**.
> Clasificación: **Backend multirruta probado: PASS** · **Contrato de activación: REQUIERE CORRECCIONES** · **Aislamiento móvil productivo: PENDIENTE** · **Implementación del contrato: NO AUTORIZADA TODAVÍA**.
> Estado documental (revisión 4): **PASS DOCUMENTAL** — la especificación queda **congelada documentalmente**. **NO está implementada** y **NO autoriza** código, modelos, migraciones, dependencias, autenticación, sincronización ni interfaz. No inicia el Bloque 6. La implementación futura requerirá una instrucción separada; las pruebas criptográficas y de concurrencia siguen pendientes de implementación.
> No modificar modelos ni migraciones hasta aprobar este documento. Sin commit/push/deploy/reinicio.

---

## 1. Inventario real del sistema de dispositivos existente

### 1.1 Backend — `Dispositivo` (existe desde Etapa 3 "que se venda")

| Pieza | Ubicación | Qué es hoy |
|---|---|---|
| Modelo | `apps/api/src/models/__init__.py:488-519` | Tabla `dispositivo`: `id`, `negocio_id` (FK, CASCADE), `usuario_id` (FK nullable), `huella` (String 64, unique por negocio), `modelo`, `plataforma`, `autorizado_por`, `autorizado_el`, `revocado_el`, `ultima_validacion_servidor`, `activo` (int), `creado_el`. Sin estados formalizados (solo `activo` + `revocado_el`). Sin versión de asignación, sin vínculo directo a `Ruta`. |
| Migración | `apps/api/migrations/versions/m3_dispositivo.py` | Crea la tabla; `downgrade` hace `drop_table`. Reversible. Cabecera actual: `m4_ruta_cobrador_fk` (down_revision `m3_dispositivo`). |
| Servicio | `apps/api/src/services/dispositivo_service.py` | `registrar_dispositivo` (crea/actualiza/reactiva; reactivación solo admin), `validar_dispositivo` (activo y no revocado → actualiza `ultima_validacion_servidor`), `revocar_dispositivo`, `reactivar_dispositivo` (admin, audita `autorizado_el`), `listar_dispositivos` (scoped a negocio). |
| Rutas | `apps/api/src/routes/dispositivo.py` | `POST /api/dispositivos` (registro), `GET /api/dispositivos` (cualquier rol, scoped negocio), `POST /api/dispositivos/{id}/validar` (cualquier rol), `POST /api/dispositivos/{id}/revocar` (admin), `POST /api/dispositivos/{id}/reactivar` (admin). **DEFECTO CONFIRMADO:** el comentario de la ruta y del servicio dicen "dispositivos nuevos solo ADMINISTRADOR", pero el código NO lo verifica — `is_admin` solo se usa para reactivar un dispositivo revocado (`dispositivo_service.py:60-69`); cuando la huella no existe, el servicio crea el dispositivo aunque el solicitante no sea admin (`dispositivo_service.py:79-94`). Además `user_id=ctx.user_id` (`routes/dispositivo.py:56`) hace que si el admin registra el celular, `usuario_id` apunte al **admin**, no al cobrador objetivo. |
| Schemas | `apps/api/src/schemas/__init__.py:349-371` | `DispositivoCreate` (huella, modelo, plataforma), `DispositivoResponse` (id, negocio_id, usuario_id, huella, modelo, plataforma, autorizado_por, autorizado_el, revocado_el, ultima_validacion_servidor, activo, creado_el). |
| Autenticación | `apps/api/src/auth/deps.py`, `auth/context.py` | **DEV ONLY (M1 stub):** identidad por query params (`negocio_id`, `route_id`, `role`); `COBRADOR` exige `route_id` en `get_request_context`. `RequestContext`: `is_admin`, `is_cobrador`, `has_negocio`, `has_route`. Deshabilitado si `DAILY_ENV != dev`. |

### 1.2 Móvil — estado real (PENDIENTE)

| Pieza | Ubicación | Qué es hoy |
|---|---|---|
| Cliente HTTP | `apps/mobile/pubspec.yaml` | **NO EXISTE.** Dependencias: sqflite, shared_preferences, uuid, crypto, pdf, printing, share_plus, intl, path, path_provider, cupertino_icons. Sin `http`/`dio`. La app es 100% offline demo con seed local. |
| Login demo | `apps/mobile/lib/main.dart:38-70` | Toma el **primer** usuario `COBRADOR` de la tabla local y el **primer** `negocio`; guarda `cobrador_id`, `cobrador_nombre`, `negocio_id` en SharedPreferences. No hay autenticación real. |
| Alcance | `main.dart` + `cobros_shell.dart:207-211` | Sin concepto de "ruta autorizada"; sin descarga de rutas desde servidor. |
| BD local | `apps/mobile/lib/database/tables.dart` | Tablas: negocio, usuario, ruta, cliente, credito, cuota_programada, jornada, pago, movimiento, sync_queue. **No existe tabla `dispositivo`.** |
| Sync | `apps/mobile/lib/services/sync_queue_service.dart` | `sync_queue` guarda `datos.toString()` de un `Map` Dart (no es JSON válido) con estado `PENDIENTE_DE_SINCRONIZAR`; **no hay código que envíe** esos eventos a ningún servidor. |
| Migraciones locales | `migration_v2/v3/v4.dart` | v2/v3/v4 son reparaciones de jornada/schema; ninguna introduce dispositivo ni activación. |

**Conclusión del inventario:** el backend tiene un esqueleto de autorización por `huella` (huérfano, sin consumidores móviles, sin activación, sin vínculo dispositivo→cobrador productivo, y con el defecto de registro sin admin). El móvil no tiene red, no tiene dispositivo, no tiene activación. La "descarga de todas las rutas" que describe el dictamen es la semilla local (`seed.dart`) + `cobros_shell` listando rutas activas sin `cobrador_id`.

**Referencias externas que respaldan la regla central ("el administrador asigna → el servidor autoriza → el celular recibe solo su alcance"):**
- **ODK:** configura el celular desde administración mediante QR y permite revocar acceso; los dispositivos ya configurados pierden acceso tras la revocación.
- **CommCare:** la asignación administrativa del trabajador a ubicaciones determina qué datos puede consultar.
- **Dynamics:** el administrador define usuarios y filtros del perfil offline; el dispositivo elimina los datos que dejan de cumplir esos filtros tras sincronizar.

---

## 2. Matriz campo / función / requisito / cambio mínimo / impacto de migración

Modelo actual (`Dispositivo`) vs. contrato de activación requerido.

| Campo actual | Función actual | Requisito cubierto | Requisito ausente | Cambio mínimo | Impacto de migración |
|---|---|---|---|---|---|
| `id` UUID | PK (default uuid4) | Identificador único | — | Se conserva. El ID vía `UUID(int=hash(...))` en `registrar_dispositivo` (`dispositivo_service.py:81`) **debe eliminarse** (colisión determinista no autorizada, logra que `id` no provenga del Keystore). | Sin datos en prod; tabla vacía hoy. |
| `negocio_id` FK | Tenant (CASCADE) | Aislamiento por negocio | — | Se conserva. | Ninguno (tabla vacía). |
| `usuario_id` FK nullable | Cobrador al que pertenece el celular (intención) | Semilla de la relación **dispositivo→cobrador** | **DEFECTO:** `user_id=ctx.user_id` hace que el registrante (admin) quede como `usuario_id`, no el cobrador objetivo. No es obligatorio al crear; no valida que el cobrador pertenezca al negocio | En el canje, `usuario_id` se asigna al cobrador **derivado del código** (no del cliente); NOT NULL en activación; validar `cobrador.negocio_id == negocio_id`. | Sin datos en prod. |
| `huella` String(64) unique/negocio | Fingerprint cliente enviado por el app | — | **Prohibido por dictamen** (huella calculada por cliente no es autenticador). Reemplazo: `public_key` o `public_key_hash` desde Android Keystore. | Renombrar/migrar `huella` → `public_key` (TEXT/PKCS8) con hash `SHA-256`; el servidor guarda la **clave pública** o su hash, no el secret. `uq_dispositivo_huella` → `uq_dispositivo_public_key_hash`. | Tabla vacía: no se requiere reescritura de datos. |
| `modelo`, `plataforma` | Metadatos | Metadatos | — | Se conservan como informativos. | Ninguno. |
| `autorizado_por` | Admin que autorizó | Auditoría de autorización | — | Se conserva. | Ninguno. |
| `autorizado_el` | Fecha autorización | Auditoría | — | Se conserva; en activación se setea en el canje del código. | Ninguno. |
| `revocado_el` | Fecha revocación | Soporta REVOKED | — | Se conserva. | Ninguno. |
| `ultima_validacion_servidor` | Heartbeat | Telemetría | — | Se conserva. | Ninguno. |
| `activo` int | Flag activo/inactivo | Booleano | **Estados mezclados en el diseño previo:** `PENDING_ACTIVATION`/`EXPIRED` son estados del **código/solicitud de activación**, no del celular. El Dispositivo se **crea al canjear** correctamente el código (no existe un dispositivo ficticio en `PENDING_ACTIVATION`) | Añadir `estado` ENUM/String(20) **solo para Dispositivo**: `ACTIVE`/`REVOKED`/`REPLACED` + check constraint; derivar/migrar `activo`→estado (`activo=1 ∧ revocado_el IS NULL` → ACTIVE; `revocado_el NOT NULL` → REVOKED). Los estados del código viven en `CodigoActivacion`: `PENDING`/`CONSUMED`/`EXPIRED`/`CANCELLED`. | Tabla vacía hoy. |
| `creado_el` | Timestamp | — | — | Se conserva. | Ninguno. |
| *(ausente)* `dispositivo_credencial` | — | — | Par de claves **EC P-256** en Android Keystore (privada NO exportable, solo firma desafíos, nunca se envía ni guarda en SharedPreferences). Clave pública en **X.509 SubjectPublicKeyInfo** (NO PKCS#8, que es formato de clave privada); alternativas válidas: JWK o COSE_Key. Firma `SHA256withECDSA`. | En Dispositivo: `public_key` (BYTEA o TEXT canónico SPKI), `public_key_hash` (SHA-256, 64 hex, unique), `algoritmo_clave` (ej. `EC_P256`). **Se conservan clave pública Y hash** (el hash solo no permite verificar firmas). | Sin datos. |
| *(ausente)* `dispositivo_id` en token | — | — | Token productivo: `negocio_id`+`usuario_id`+`dispositivo_id`+`rol`+`versión de asignación` | Nuevo esquema de token (auth real, Bloque 7). | N/A (auth dev-only hoy). |
| *(ausente)* `ruta` en Dispositivo | — | — | **NO AÑADIR `ruta_id` a Dispositivo** (duplicaría la autoridad de `ruta.cobrador_id`). El alcance lo deriva el servidor: negocio + cobrador + dispositivo ACTIVE + `ruta.cobrador_id == usuario_id`. | Ninguno (decisión de diseño). | N/A. |
| *(ausente)* `codigo_activacion` | — | — | Token de un solo uso con vencimiento; **el servidor entrega el token original UNA sola vez al admin** (el QR contiene el token original) y **almacena únicamente su digest/hash**; el prefijo solo identifica, no canjea. **El canje exige prueba de posesión de la clave privada (challenge-response):** sin ella, cualquiera con el token enviaría una clave pública arbitraria y se apropiaría de la activación | Nueva tabla `codigo_activacion`: `id`, `negocio_id`, `cobrador_id` (**derivado del código, no enviado por el cliente**), `hash_codigo` (digest del token), `prefijo` (identificación), `expira_el`, `intentos_fallidos` (si código corto manual), `estado` (`PENDING`/`CONSUMED`/`EXPIRED`/`CANCELLED`), `consumido_el`, `dispositivo_id_canjeado`, `creado_por`, `entregado_el`. | Migración nueva reversible. |
| *(ausente)* `intento_activacion` | — | — | Nonce criptográfico temporal para el canje (challenge-response). El código NO se consume al solicitar el desafío, solo al canjear con firma válida | Nueva tabla `intento_activacion`: `id`, `codigo_activacion_id`, `nonce` (base64url), `clave_publica` (SPKI), `public_key_hash`, `expira_el`, `firma_validada_el`, `consumido_el`. Vencimiento corto; una firma solo vale para su `intento_id`+`nonce`. | Migración nueva reversible. |

**Matriz móvil:**

| Artefacto | Función actual | Requisito cubierto | Requisito ausente | Cambio mínimo | Impacto |
|---|---|---|---|---|---|
| `pubspec.yaml` | Offline demo | — | Cliente HTTP + generación de par EC P-256 + firma nonce | **NO fijar librerías todavía.** Evaluar matriz (sección 6): `flutter_secure_storage`, `flutter_keystore`, `http`/`dio`, OAuth, PKCE vs **MethodChannel Android nativo**. Si ningún paquete demuestra las capacidades requeridas, usar MethodChannel; no degradar el requisito por acomodar una dependencia. **En Bloque 5 no se toca.** | Dependencias nuevas (por decidir). |
| `main.dart:38-70` login demo | Primer COBRADOR/primer negocio | — | Autenticación real + activación | Reemplazar por flujo de activación (Bloque 3). **Congelado** hasta contrato. | — |
| SharedPreferences | Persiste identidad demo | — | **Prohibido como autenticador** | Almacenar solo nonces/tokens de sesión efímeros; claves en Keystore. | — |
| `sync_queue` | Buffer local sin emisor | Cola offline | Envío real + tratamiento de pendientes | Se conserva como buffer; el emisor llega con sync (Bloque 5). `datos.toString()` debe ser `jsonEncode`. | Datos seed se re-sembrarán; cola limpia. |
| `cobros_shell.dart:207-211` | Lista rutas activas sin filtro | — | Solo ruta asignada | Bootstrap con la ruta única (Bloque 4). **Congelado**. | — |
| Canje de activación | — | — | **El móvil NO envía `negocio_id`/`cobrador_id`/`ruta_id`/`dispositivo_id`/`rol`/`estado` como autoridad.** Protocolo challenge-response: (A) `POST /api/activaciones/desafio` con `{token, clave_publica, modelo?, plataforma?}` → `{intento_id, nonce, expira_el}`; (B) firmar nonce con la clave privada del Keystore y `POST /api/activaciones/canjear` con `{intento_id, firma}`. Firma sobre mensaje canónico: `intento_id + nonce + public_key_hash + timestamp/expiración + identificador de protocolo` (impide reutilización entre intentos/ambientes). | Endpoint de canje con verificación de firma; el servidor deriva todo del intento+código. | — |

---

## 3. Diagrama de estados (separados: `CodigoActivacion` y `Dispositivo`)

### 3.1 `CodigoActivacion` + `IntentoActivacion` (el código o solicitud de activación)

```
                  ┌───────────────┐
   admin genera    │   PENDING     │  token de alta entropía; el servidor entrega
   token           └───┬───────┬───┘  el token original UNA vez (QR); guarda solo digest
                       │       │ vencimiento expira_el
          desafío (POST /desafio)│
          valida PENDING/vigente │
          crea intento+nonce     │
                       ▼         │
         ┌──────────────────┐    │
         │ INTENTO (nonce)  │    │
         │ expira (corto)   │    │
         └────────┬─────────┘    │
                  │ canje (POST /canjear):
                  │   firma válida con clave pública del intento +
                  │   token aún PENDING + asignación vigente +
                  │   sin otro dispositivo ACTIVE del cobrador
                  │   → en una transacción: código CONSUMED,
                  │     dispositivo ACTIVE creado
                  ▼
                  ┌──────────┐   ┌──────────┐
                  │ CONSUMED │   │ EXPIRED  │
                  └──────────┘   └──────────┘
    admin cancela PENDING/CONSUMED → CANCELLED (anula antes/después del canje)
```

- Reglas:
  - `PENDING` → `CONSUMED` en el canje válido (único; idempotente por token y por intento).
  - `PENDING` → `EXPIRED` al vencer `expira_el` sin canjear.
  - `CANCELLED`: anulación administrativa (rota códigos pendientes o revoca tras canje).
  - El **desafío NO consume** el código: crea un `IntentoActivacion` con `nonce` criptográfico y vencimiento corto; el dispositivo firma el nonce y presenta la firma en el canje.
  - Si se ofrece código corto manual (además del QR), requiere: `intentos_fallidos` con tope (p. ej. 5) que mueve a `EXPIRED`/`CANCELLED`, vencimiento estricto, y digest apropiado para secreto de baja entropía (bcrypt/argon2, NO un hash rápido).

**Precisiones documentales del protocolo de canje (dictamen rev. 4):**

1. **El intento es de un solo uso:** un `IntentoActivacion` solo puede consumirse una vez. Tras un canje válido (o un canje fallido de verificación de firma que lo invalide), cualquier reutilización del `intento_id` se rechaza. Idempotencia: el canje exitoso devuelve la misma credencial bootstrap si se repite con el mismo `intento_id` dentro del plazo (resultado idempotente), pero nunca genera un segundo dispositivo.
2. **El `nonce` se genera con CSPRNG:** se usa un generador criptográficamente seguro (p. ej. `secrets.token_bytes`/`os.urandom` en el servidor, ≥ 32 bytes) — nunca `random`, `uuid4`-sin-primera-lectura ni timestamp como fuente de entropía.
3. **Verificación y consumo en una sola operación con bloqueo/transacción:** el canje ejecuta, dentro de una transacción con bloqueo de fila (`SELECT ... FOR UPDATE` sobre el `CodigoActivacion` y el `IntentoActivacion`), todas las verificaciones (intento vigente, firma válida, token `PENDING`, asignación cobrador–ruta vigente, sin otro `ACTIVE`) y el consumo (código `CONSUMED`, dispositivo `ACTIVE`). Esto impide condiciones de carrera entre canjes concurrentes del mismo código.
4. **Serialización del mensaje firmado definida byte por byte:** no basta "mensaje canónico". Se fija una codificación concreta — **JSON Canonicalization Scheme (RFC 8785)** o **CBOR determinístico** — del siguiente objeto, en este orden de claves:
   ```json
   {
     "protocol_version": "daily-v1",
     "environment": "production",
     "attempt_id": "<uuid>",
     "nonce": "<base64url>",
     "public_key_hash": "<sha256-hex>",
     "expires_at": "<iso8601-utc>"
   }
   ```
   - `protocol_version` y `environment` hacen que una firma emitida en desarrollo/pruebas **no** sea válida en producción (ni entre ambientes).
   - La serialización canónica y el algoritmo (`SHA256withECDSA`) se fijan en el contrato; el servidor verifica el mensaje exacto (decode de la firma sobre el JCS/CBOR determinístico), no un payload reordenable.
   - **DECISIÓN RESUELTA en la revisión 4 (sección 13):** el formato canónico único y obligatorio es **JCS (RFC 8785)**; el **CBOR determinístico queda descartado** para esta versión del contrato (alternativa evaluada en §13.1–13.2). Perfil canónico mínimo congelado y vector de prueba obligatorio en §13.3–13.4.

### 3.2 `Dispositivo` (el celular; se CREA al canjear, no antes)

```
                 canje válido + clave pública
   (no existe dispositivo previo)  │
                                  ▼
                    ┌──────────────────────────┐
                    │  ACTIVE                   │──admin revoca──▶ REVOKED
                    │  (único por cobrador)    │──admin reemplaza─▶ REPLACED
                    └──────────────────────────┘     (el nuevo celular inicia ACTIVE)
```

- Reglas:
  - Un cobrador puede tener **un solo** Dispositivo `ACTIVE`.
  - El Dispositivo **nace en `ACTIVE`** directamente del canje del código (no pasa por `PENDING_ACTIVATION`).
  - `REVOKED` → no puede validar token ni sincronizar; token de sesión se invalida (bump `version_asignacion`).
  - `REPLACED` → el dispositivo viejo queda `REPLACED` y se crea/activa el nuevo; **no se borra ni se reasigna historia** (pagos/cierres conservan cobrador+ruta+dispositivo originales).
  - Reactivación explícita de `REVOKED` (admin) re-emite nueva activación o restaura ACTIVE con nueva sesión.
  - Cambio de ruta del cobrador **bloqueado** si: jornada abierta, cierre pendiente o cola local sin sincronizar.

---

## 4. Contrato de endpoints propuesto (sujeto a aprobación)

### Activación (nuevo, tras contrato — NO implementar ahora)

| Método | Ruta | Rol | Descripción |
|---|---|---|---|
| POST | `/api/activaciones/codigos` | ADMIN | Genera token de un solo uso para `negocio_id`+`cobrador_id`; **devuelve el token original UNA sola vez** (el admin lo pasa al QR del celular); el servidor almacena **solo el digest/hash** (`sha256` para alta entropía; bcrypt/argon2 si se permite código corto manual) + `prefijo` de identificación. Vence a los N minutos configurables. |
| POST | `/api/activaciones/desafio` | Público (app sin token) | Body: `token`, `clave_publica` (X.509 SPKI/JWK/COSE), `modelo`, `plataforma`. El servidor: calcula digest del token → localiza `CodigoActivacion` → valida `estado=PENDING`, no vencido, no consumido, no cancelado, cobrador aún asignado a ruta válida → genera `nonce` con **CSPRNG** (≥ 32 bytes) → guarda `IntentoActivacion` **de un solo uso** con vencimiento → devuelve `{intento_id, nonce, expira_el}`. **El código NO se consume aquí.** |
| POST | `/api/activaciones/canjear` | Público (app sin token) | Body: `intento_id`, `firma` (base64url). El servidor verifica, **en una transacción con bloqueo de fila** (`SELECT ... FOR UPDATE` sobre código e intento, para impedir canjes concurrentes): intento existente, no vencido y **no usado** (un solo uso); firma válida con la clave pública registrada en el intento (mensaje firmado según serialización JCS/CBOR fija de la sección 3.1, con `protocol_version`+`environment`); token aún `PENDING`; asignación cobrador–ruta vigente; ausencia de otro dispositivo `ACTIVE` del cobrador. Luego, en la misma transacción: código `CONSUMED` (`consumido_el`), dispositivo `ACTIVE` creado (`usuario_id` derivado del código), `public_key`+`public_key_hash`+`algoritmo_clave` guardados, `autorizado_por`/`autorizado_el` registrados, credencial bootstrap de corta vigencia devuelta. Reintento con el mismo `intento_id` → resultado idempotente (misma credencial), nunca un segundo dispositivo. |
| GET | `/api/dispositivos` | ADMIN/COBRADOR (scoped) | Lista dispositivos del negocio (existente). |
| POST | `/api/dispositivos/{id}/revocar` | ADMIN | Revocar (existente) → `REVOKED`. |
| POST | `/api/dispositivos/{id}/reactivar` | ADMIN | Reactivar (existente) → re-emite activación. |
| POST | `/api/dispositivos/{id}/reemplazar` | ADMIN | Marca `REPLACED` y emite nuevo código para el reemplazo. |
| GET | `/api/mobile/bootstrap` | App autenticada | **Sustituye a `GET /api/dispositivos/{id}/bootstrap`.** El servidor extrae de la credencial: `negocio_id`, `usuario_id`, `dispositivo_id`, `rol`, `version_asignacion` (sin parámetros en la URL). Devuelve SOLO la ruta autorizada (servidor deriva: `ruta.cobrador_id == usuario_id`) + negocio + cobrador. **Aquí nace el aislamiento móvil.** |

> **Regla del body público:** el canje/desafío NO acepta `negocio_id`, `cobrador_id`, `ruta_id`, `dispositivo_id`, `rol` ni `estado` — todos los deriva el servidor.

### Auth (Bloque 7, dev-only hoy)

- Token productivo = `negocio_id` + `usuario_id` + `dispositivo_id` + `rol` + `version_asignacion`.
- El servidor revalida la ruta en cada request; un token antiguo no sobrevive a reasignación.
- Clientes nativos: Authorization Code + PKCE (RFC 8252); Play Integrity opcional posterior.

---

## 5. Propuesta de migración reversible

**Migración `m5_dispositivo_activacion`** (down_revision `m4_ruta_cobrador_fk`):

1. `upgrade()`:
   - Añadir columna `estado` String(20) a `dispositivo` con default `ACTIVE` + check constraint **solo** `ACTIVE`/`REVOKED`/`REPLACED` (el Dispositivo nace al canjear; no hay `PENDING_ACTIVATION`/`EXPIRED`).
   - Renombrar `huella` → `public_key` (TEXT SPKI canónico) y añadir `public_key_hash` String(64) unique (`uq_dispositivo_public_key_hash`) + `algoritmo_clave` (ej. `EC_P256`). **Se conservan clave pública Y hash.**
   - Crear tabla `codigo_activacion` (FK negocio, FK cobrador, `hash_codigo`, `prefijo`, `expira_el`, `intentos_fallidos`, `estado` `PENDING`/`CONSUMED`/`EXPIRED`/`CANCELLED`, `consumido_el`, `dispositivo_id_canjeado`, `creado_por`, `entregado_el`).
   - Crear tabla `intento_activacion` (FK codigo, `nonce` base64url, `clave_publica` SPKI, `public_key_hash`, `expira_el`, `firma_validada_el`, `consumido_el`).
   - `usuario_id` pasa a NOT NULL (tras backfill de filas existentes, que hoy son 0).
   - Backfill: `estado` de filas existentes según `activo`/`revocado_el` (`activo=1 ∧ revocado_el IS NULL` → ACTIVE; `revocado_el NOT NULL` → REVOKED). Tabla vacía en la práctica.
2. `downgrade()`: revierte en orden inverso (drop `intento_activacion`, drop `codigo_activacion`, restaurar `huella`, drop `estado`/`algoritmo_clave`, `usuario_id` nullable). Verificar con `alembic check` + suite.

**Criterio de reversibilidad:** `upgrade` y `downgrade` idempotentes, `alembic check` limpio al final, y ninguna pérdida de datos (tabla `dispositivo` vacía; si llegara a haber filas, el downgrade conserva `public_key`/`public_key_hash` y restaura `huella` con el hash).

---

## 6. Política de revocación / reemplazo / reasignación

1. **Revocación:** admin revoca → Dispositivo `REVOKED`; el token queda inválido (bump `version_asignacion` o invalidar sesión); la app deja de recibir bootstrap; **los pagos/cierres ya registrados se conservan intactos**.
2. **Reemplazo (celular nuevo):** el dispositivo viejo pasa a `REPLACED`; el nuevo requiere nuevo código de activación; **la historia (pagos, cierres, snapshot, IDs) no se migra ni se reasigna**: los registros conservan cobrador+ruta+dispositivo originales; el nuevo dispositivo comienza su propio historial de sesión (con sync incremental desde servidor).
3. **Reasignación de ruta (cobrador cambia de ruta):** admin mueve `ruta.cobrador_id` (no se duplica en Dispositivo); **bloqueado si el cobrador tiene jornada abierta, cierre pendiente o cola local sin sincronizar**; el cambio bumpa la versión de asignación; el móvil re-bootstrappea a la nueva ruta única; los datos históricos de la ruta anterior permanecen como lectura.
4. **Un cobrador = un Dispositivo ACTIVE; una ruta = un cobrador activo.** El servidor es la única autoridad que valida ambas invariantes al canjear/reasignar.
5. **El canje exige prueba de posesión de la clave privada (challenge-response):** un token por sí solo NO es suficiente — cualquiera con el token podría enviar una clave pública arbitraria. El dispositivo debe: (A) obtener un `nonce` vía `POST /api/activaciones/desafio` presentando `token` + `clave_publica`; (B) firmar el nonce con la clave privada del Keystore y canjear con `{intento_id, firma}`. El servidor verifica la firma contra la clave pública registrada en el intento.
6. **El canje no confía en el cliente:** el móvil solo presenta token + clave pública + firma; el servidor deriva negocio+cobrador desde el código (el código se genera ligado a negocio+cobrador). Enviar `cobrador_id` (o `negocio_id`/`ruta_id`/`dispositivo_id`/`rol`/`estado`) como autoridad está **prohibido**.
7. **No se borra nada al revocar/reemplazar/reasignar.** Toda mutación de estado queda auditada (`autorizado_por`, `autorizado_el`, `revocado_el`, `consumido_el`, `creado_por`).

---

## 7. Tratamiento de eventos offline pendientes

- La cola local (`sync_queue`) se conserva como fuente de verdad del dispositivo para lo **no enviado**.
- Al reemplazar dispositivo o reasignar ruta, la cola NO se borra automáticamente: se intenta vaciar **antes** de permitir el cambio (regla de bloqueo del punto 6.3).
- Regla de cierre: no se puede revocar/reemplazar/reasignar con `estado = PENDIENTE_DE_SINCRONIZAR` en `sync_queue` o jornada abierta.
- El emisor (futuro) debe usar idempotencia ya soportada (`clave_idempotencia` en pago y movimiento) y reenviar hasta `SINCRONIZADO`; `datos` debe guardarse con `jsonEncode`, no `Map.toString()`.
- Si se fuerza un reemplazo con cola pendiente (policy override documentada), la cola se marca `ABANDONADA` y el servidor detecta huecos por idempotencia en el primer sync del nuevo dispositivo.

---

## 8. Las 15 pruebas obligatorias del cierre (para el contrato)

1. Admin asigna C1→R1, genera código para C1; D1 hace desafío + canje (firma) y obtiene bootstrap con **solo R1**.
2. D1 no puede consultar/descargar/operar R2 (404/403, listas vacías, `[]`).
3. Un **segundo celular** no puede reutilizar el token de D1: el canje exige firma con la clave privada cuyo par fue presentado en el desafío; un tercero con el token pero sin la privada es rechazado (prueba de posesión).
4. Un dispositivo sin canje no existe (sin fila) ni obtiene bootstrap (401/403); el desafío NO consume el código (`PENDING` sigue vigente).
5. Token vencido o ya usado → rechazado (digest verificado, `expira_el`); intento de desafío/canje vencido → rechazado; código manual: `intentos_fallidos` agota → `EXPIRED`.
6. Revocar D1 → el token de D1 queda inválido y el sync deja de funcionar.
7. Reemplazo D1→D2: D1 queda `REPLACED`, D2 nace `ACTIVE`; **historia de D1 conservada**.
8. Reasignar C1 R1→R2 conserva pagos/cierres históricos de R1.
9. Reasignar **falla** si C1 tiene jornada abierta o cola pendiente.
10. Admin ve todas las rutas; un cobrador solo su ruta asignada.
11. Crear R5/R6/R100 sin cambio de código ni límite fijo.
12. La BD local de D1 no contiene clientes/créditos de otras rutas.
13. Manipular manualmente `route_id`/query params no amplía permisos (servidor deriva, no confía en el cliente); el body público NO acepta `negocio_id`/`cobrador_id`/`ruta_id`/`dispositivo_id`/`rol`/`estado`; enviar una clave pública arbitraria sin la privada correspondiente es rechazado en el canje.
14. Dos celulares/cobradores/rutas operan offline y sincronizan sin cruce de datos.
15. `alembic check` + 148 tests backend + 68 tests móviles siguen PASS tras la migración m5.

---

## 9. Riesgos de compatibilidad

| Riesgo | Mitigación |
|---|---|
| `POST /api/dispositivos` NO exige admin para dispositivos nuevos (`routes/dispositivo.py:50-59` usa `is_admin` solo para reactivación; el servicio crea con huella nueva aunque el solicitante sea cobrador) | Cerrar en el contrato: creación de dispositivo SOLO vía canje de código admin-generado; el endpoint de registro directo se elimina o pasa a ADMIN y valida el cobrador objetivo. |
| `user_id=ctx.user_id` (`routes/dispositivo.py:56`) deja al admin como `usuario_id` al registrar | En el canje, `usuario_id` se asigna al cobrador derivado del código, nunca al solicitante. |
| `UUID(int=hash(...))` en `registrar_dispositivo` (`dispositivo_service.py:81`) — ID derivado del hash de huella, colisionable y no criptográfico | Eliminar: `id=uuid.uuid4()`; tabla vacía hoy, sin impacto de datos. |
| Cambio `huella`→`public_key`/`public_key_hash` rompería el `DispositivoCreate` y `DispositivoResponse` existentes | Contrato v2; sin consumidores móviles hoy, sin datos en prod; actualizar schemas y tests junto a la migración. |
| `auth` dev-only (query params) expone negocio/ruta si se despliega | Queda **prohibido desplegar** con query-auth (comentario ya en `deps.py:3-4`); el dictamen lo marca PENDIENTE. |
| Móvil sin red y con seed demo: la "paridad financiera" (Bloque 5) se prueba contra datos sembrados, no contra API | La matriz compara lógica, no transporte; el transporte llega con auth real. Bloque 5 no toca red. |
| La UI aprobada (goldens, Hoja Viva, temas) no debe cambiar en esta fase | **Confirmado: no se modifica la UI aprobada.** Cambios de Bloque 5 solo donde la matriz demuestre divergencia financiera; cambios de activación afectan flujo de entrada (login), no la UI operativa. |
| Migración m5 sin prueba de reversión | Cada paso validado con `alembic downgrade` + `alembic check` en el PR; tests de migración en CI. |
| Cola `sync_queue` guarda `Map.toString()` (no JSON) | Corregir en Bloque 5 como parte de la paridad, sin tocar alcance. |
| Canje sin prueba de posesión → cualquier portador del token roba la activación | Obligatorio challenge-response: el canje exige firma válida del nonce con la clave privada del par presentado en el desafío. |
| Reutilización de firmas entre intentos/ambientes | Serialización **byte a byte** fija — **JCS RFC 8785 (único; CBOR determinístico descartado en §13)** sobre `protocol_version + environment + attempt_id + nonce + public_key_hash + expires_at`; `environment` impide reutilizar firmas de dev/test en producción. |
| Canje concurrente del mismo código / reutilización de intento | Intento de **un solo uso** + verificación y consumo en una transacción con `SELECT ... FOR UPDATE` sobre código e intento; reintento idempotente (misma credencial), nunca un segundo dispositivo. |
| `nonce` débil o predecible | Generación con **CSPRNG** del servidor (≥ 32 bytes, `secrets`/`os.urandom`); nunca `random`/`uuid4` sin entropía segura como fuente. |
| Almacenar solo `public_key_hash` impide verificar firmas | Conservar SIEMPRE `public_key` (SPKI) + `public_key_hash` + `algoritmo_clave`. |
| Paquete Flutter elegido sin verificar capacidades Keystore (generar/firmar/no exportar/SPKI) | Matriz de la sección 12 con evidencia; si ninguna alternativa cubre el 100% → MethodChannel Android nativo. No degradar requisito por la dependencia. |

---

## 10. Archivos exactos que cambiarían (bajo aprobación, en su fase)

**Backend — contrato activación (Bloque 3/6):**
- `apps/api/migrations/versions/m5_dispositivo_activacion.py` (nuevo)
- `apps/api/src/models/__init__.py` (Dispositivo + `CodigoActivacion` + `IntentoActivacion`)
- `apps/api/src/services/dispositivo_service.py` (estados, canje, bootstrap, reemplazo)
- `apps/api/src/services/activacion_service.py` (nuevo: códigos, desafío, canje con verificación de firma)
- `apps/api/src/routes/dispositivo.py` (estados, reemplazar; bootstrap se muda a `/api/mobile/bootstrap`)
- `apps/api/src/routes/activacion.py` (nuevo: códigos, desafío, canje)
- `apps/api/src/schemas/__init__.py` (DispositivoCreate/Response v2, ActivacionRequest/Response)
- `apps/api/src/auth/deps.py` (reemplazo del stub por token real — Bloque 7)
- `apps/api/src/tests/test_m5_activacion.py` (nuevo, 15 pruebas + test del gate admin: cobrador NO puede crear dispositivo directo; `usuario_id` = cobrador derivado del código)

**Móvil (después de contrato):**
- `apps/mobile/pubspec.yaml` (librería por decidir tras matriz de la sección 12; NO fijar aún)
- `apps/mobile/lib/services/activacion_service.dart` (nuevo: desafío + firma + canje)
- `apps/mobile/android/...` (MethodChannel nativo de Keystore si ningún paquete cubre las capacidades)
- `apps/mobile/lib/services/sync_queue_service.dart` (jsonEncode)
- `apps/mobile/lib/main.dart` (flujo de activación reemplaza login demo)
- `apps/mobile/lib/database/migration_v5.dart` (tabla dispositivo local opcional)

**Bloque 5 (paridad financiera) — límites del dictamen:**
- NO tocar: `cobros_shell.dart` selección de rutas, `main.dart` login demo, SharedPreferences de alcance, descarga de datos, activación, revocación.
- SÍ (solo si la matriz demuestra divergencia): `pago_service.dart`, `caja_service.dart`, `hoja_viva_service.dart`, backend `payment_service.py`/`jornada`/`cierre` por regla financiera exacta.

---

## 11. Confirmación de UI aprobada intacta

- **La UI aprobada NO se modifica en esta fase.** No cambian pantallas, goldens (412x915 phone, 840x900 tablet), temas claro/oscuro, ni Hoja Viva.
- Los cambios de activación afectan el **flujo de entrada** (login→activación→bootstrap), que hoy es demo; la pantalla operativa existente permanece y solo se ajustará su origen de datos (ruta única) una vez aprobado el contrato.
- Cualquier desviación de UI requiere nueva autorización explícita y actualización de goldens.

---

## 12. Matriz de evaluación de librerías móviles (resultados verificados — dictamen rev. 4)

> **NO se fijan aún.** Alternativas evaluadas con documentación pública verificada: **A) `keystore_plugin` 1.2.0**, **B) `attested_secure_keys` 0.1.0**, **C) MethodChannel Android nativo**. `flutter_secure_storage` NO es candidato a motor de identidad (ver abajo). Si ninguna alternativa Flutter cubre el 100%, se usa MethodChannel. No degradar el requisito para acomodar una dependencia.

### 12.1 Matriz comparativa

| Capacidad | A) `keystore_plugin` 1.2.0 | B) `attested_secure_keys` 0.1.0 | C) MethodChannel nativo |
|---|---|---|---|
| Generar EC P-256 dentro de AndroidKeyStore | Sí (declara `secp256r1`) | Sí | Sí |
| Clave privada no exportable | Sí (Android Keystore; presumible) | Sí | Sí (Android Keystore) |
| Obtener clave pública SPKI (X.509) | **No demostrado** en API pública revisada | Sí (JWK) | Sí (certificado/clave pública) |
| Firmar nonce (SHA256withECDSA) | Sí | Sí (ES256) | Sí (`SHA256withECDSA`) |
| Borrar/rotar alias | **No demostrado** | Sí | Sí |
| StrongBox/TEE | Declara intento StrongBox + fallback TEE | Sí, con nivel efectivo reportado | Control directo |
| Attestation | — | Sí (cadena X.509 Android) | Posible (API nativa) |
| minSdk | No confirmado en docs | API 24 | API 23 (`KeyGenParameterSpec`) |
| Mantenimiento / madurez | Publicado hace ~10 meses; publicador **no verificado**, adopción limitada | Muy reciente (0.1.0); sin historial | Coste propio: Kotlin + tests instrumentados + mantenimiento |
| Pruebas instrumentadas | Pendiente (emulador API 35) | Pendiente (auditoría de código + PoC) | Plan propias |
| **Dictamen** | **NO aprobar todavía** (no acredita exportar pública en formato estable, borrar/rotar alias, comportamiento ante invalidación) | **Mejor cobertura técnica, NO aprobada para producción** sin auditoría de código, licencia, pruebas y comportamiento real en varios dispositivos | **Referencia segura y auditable para el MVP Android** |

### 12.2 `flutter_secure_storage` — NO es motor de identidad

| Capacidad | Resultado |
|---|---|
| Guardar secretos cifrados | Sí |
| Usar Android Keystore internamente | Sí |
| Generar identidad EC P-256 para la app | **No demostrado** |
| Exportar pública SPKI/JWK | No |
| Firmar desafío con identidad de dispositivo | No (no es su API principal) |
| **Dictamen** | No reemplaza el par asimétrico no exportable del challenge-response. Sirve solo para guardar tokens/metadatos de sesión |

### 12.3 Decisión preliminar

- Para el **motor de identidad criptográfica** (desafío/firma): la referencia segura es **MethodChannel Android nativo** (alternativa C); `attested_secure_keys` queda como candidata técnica a reevaluar tras auditoría de código + PoC; `keystore_plugin` **no se aprueba** por cobertura incompleta.
- `flutter_secure_storage` puede usarse **más adelante** (no ahora) para almacenar tokens/metadatos de sesión, nunca como identidad.
- `http`/`dio`, OAuth y PKCE: decisión separada de transporte/auth (Bloque 3/7), no fijada aún.
- **Criterio de salida:** columna ganadora con evidencia de API + minSdk + prueba instrumentada en emulador API 35. Para MethodChannel: PoC con generación, SPKI, firma, rotación y manejo de invalidación documentado.
- **No bloquea Bloque 5** (matriz de paridad financiera); solo es requisito previo del Bloque 3 (auth + vinculación).

---

## 13. Decisión de serialización canónica — JCS (RFC 8785) — RESUELTA en la revisión 4

### 13.0 Evidencia del árbol real (auditoría read-only)

- **Backend (Python/FastAPI/Pydantic v2):** serialización JSON nativa (`json.dumps`, `model_dump_json`). **Precedente de canonización ya en el repo:** `apps/api/src/services/jornada_service.py:67` y las pruebas `apps/api/src/tests/test_m2.py` verifican el hash del snapshot cierre con `json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)` — patrón de bytes reproducibles sobre JSON ya establecido.
- **Móvil (Flutter/Dart):** `dart:convert` (JSON nativo). Sin librería CBOR ni RFC 8785 en `pubspec.yaml`/`pubspec.lock`.
- **Web futura (TypeScript):** JSON nativo (carpeta `apps/web/src` vacía; sin paquetes instalados).
- **Sin uso de CBOR/protobuf/msgpack en código de producto.** No hay `cbor2`, `rfc8785` ni `canonicaljson` en el entorno Python del proyecto.
- **Payload firmado compuesto exclusivamente de strings** (UUID, base64url, hex, ISO-8601, literales de protocolo/ambiente): sin números, sin mapas anidados, sin binario crudo.

### 13.1 Comparación — JCS (RFC 8785) vs CBOR canónico (RFC 8949 §4.2.1)

| Criterio | JCS (RFC 8785) | CBOR canónico (RFC 8949 §4.2.1) |
|---|---|---|
| Interoperabilidad | JSON nativo en Python, Dart y TypeScript | Binario: exige librerías adicionales en las 3 plataformas |
| Disponibilidad de librerías | Python `jcs`/`rfc8785` · Dart `json_canonicalization` · TS `rfc8785` | Python `cbor2` · Dart `cbor` (tercero, menor adopción) · TS `cbor`/`cbor-x` |
| Compatibilidad con el stack | Ya hay canonización JSON en el repo (jornada) | Sin precedente en ninguna capa |
| Estabilidad de representación | Especificada (orden por punto de código §3.2.3; strings §3.2.2; números §3.3) | Especificada (mapas ordenados por longitud y lexicográfico) |
| Riesgos con números/Unicode | Números: único footgun conocido — **no aplica** (payload sin números). Unicode: UTF-8 válido sin normalización | Números: codificación mínima; igualmente irrelevante aquí. Unicode: representación de strings más expuesta a divergencia |
| Facilidad de depuración | Legible; el auditor verifica los bytes a ojo | Requiere hexdump; verificación manual inviable |
| Tamaño del payload | ~285 bytes (texto) | Algo menor; **irrelevante** en un canje de un solo uso |
| Riesgo de implementaciones divergentes | Bajo con librerías conformantes; el vector de prueba del contrato lo elimina | Moderado-alto: librerías Dart/TS menos maduras; divergencias sutiles de canonicalización |
| Impacto en firmas y hashes | Los bytes JCS se firman directo; mismo enfoque que el hash de jornada | Formato binario menos auditable |
| Impacto en el protocolo actual | Cero (no hay serialización firmada hoy); alinea con el patrón JSON del proyecto | Introduce un formato binario ajeno a un stack 100% JSON |

### 13.2 Selección y registro de la alternativa descartada

- **APROBADO por esta auditoría (2026-08-06): JCS (RFC 8785)** como **formato ÚNICO y obligatorio** de la serialización determinista del contrato de activación. Esta aprobación se produce con el presente dictamen de cierre de la revisión 4; no existía una aprobación previa.
- **Descartado para esta versión del contrato: CBOR canónico (RFC 8949 §4.2.1).** Queda registrado como alternativa evaluada y descartada: el stack completo (backend Python, móvil Dart, web futura TS) es JSON-nativo; el payload firmado ya está expresado como JSON; no existe infraestructura CBOR en ninguna capa; el payload firmado es pequeño y solo-strings, donde la única ventaja de CBOR (tamaño/binario) es irrelevante y su riesgo (divergencia entre librerías de menor madurez) es mayor.
- **No se fijan librerías en esta revisión** (decisión de implementación, Bloque 3): solo se fija el formato. Las librerías se elegirán al implementar con el criterio de salida **"producción de los bytes exactos del vector de prueba del §13.4"**.
- Advertencia sobre el precedente interno: el patrón actual `json.dumps(sort_keys=True, separators=(",",":"))` es **únicamente un precedente de intención de JSON estable** (orden de claves y compactación). **NO equivale ni demuestra cumplimiento de RFC 8785:** difiere de ella en el tratamiento de números y de strings no-ASCII (Python escapa a `\uXXXX` con `ensure_ascii`; RFC 8785 exige UTF-8 literal) y no cubre la totalidad de las reglas del estándar. El cumplimiento real se verifica solo contra el vector de prueba del §13.4.

### 13.3 Perfil canónico mínimo (CONGELADO)

1. **Estándar:** JSON Canonicalization Scheme — **RFC 8785**. Único formato permitido; CBOR canónico prohibido para esta versión del contrato (§13.2).
2. **Codificación de caracteres:** UTF-8, sin BOM. Los bytes que entran a la firma son la representación UTF-8 del texto JCS.
3. **Orden de claves/mapas:** el orden canónico de las claves de propiedad de RFC 8785 §3.2.3 (comparación por punto de código Unicode). El objeto firmado tiene **seis claves** cuyo orden JCS es: `attempt_id`, `environment`, `expires_at`, `nonce`, `protocol_version`, `public_key_hash`.
4. **Tratamiento de números:** el payload **no contiene números** (esquema cerrado de strings). Un productor que emita un número produce un payload no conforme y la verificación falla.
5. **Tratamiento de fechas:** `expires_at` = string ISO 8601 en UTC, formato exacto `YYYY-MM-DDTHH:MM:SSZ` (segundos completos, sin fracción, sufijo `Z`, sin offset).
6. **Tratamiento de valores nulos:** prohibidos. Los seis campos son obligatorios y no nulos.
7. **Tratamiento de binarios:** sin bytes crudos en el payload. `nonce` = string **base64url sin padding** (RFC 4648 §5, sin `=`); `public_key_hash` = **64 caracteres hexadecimales en minúscula** (SHA-256 del SPKI).
8. **Estructura de `environment`:** string ASCII en minúscula de un conjunto cerrado: `development` \| `staging` \| `production`. El servidor verificador solo acepta la firma si el `environment` de la carga coincide con su ambiente activo; la carga de un ambiente no es válida en otro (reutilización imposible).
9. **Campos desconocidos:** rechazados. El objeto firmado es un conjunto cerrado de 6 claves; cualquier clave adicional invalida la verificación (bytes no coincidentes y/o rechazo de esquema).
10. **Campos opcionales:** ninguno. Los 6 campos son obligatorios en todo canje.
11. **Versión del esquema:** `protocol_version` = `daily-v1`. Un cambio incompatible del esquema exige un nuevo `protocol_version`, no una reinterpretación del existente.
12. **Bytes exactos que entran a la firma:** la salida JCS (RFC 8785) del objeto completo, codificada en UTF-8 sin BOM; firma `SHA256withECDSA` sobre esos bytes exactos. El servidor **reconstruye** el objeto canónico a partir del intento (él generó `attempt_id`/`nonce`/`expires_at`, conoce `public_key_hash`, `environment` y `protocol_version`) y verifica la firma contra esos bytes; el cliente firma los bytes del mismo objeto canónico derivado de la respuesta al desafío. Sin reordenamiento ni reformateo.
13. **JCS resuelve la canonicalización del JSON, NO las opciones léxicas de cada campo.** RFC 8785 determina el orden de propiedades, el escapado y la representación de números; **no decide** si un nonce se expresa en base64url con o sin padding, si un hash va en hex o base64url, ni la precisión de una fecha. Esas decisiones se fijan **aquí**, en el perfil, y son tan vinculantes como el propio JCS. Representación lexical exacta por campo:

| Campo | Tipo JSON | Representación lexical exacta (única, obligatoria) |
|---|---|---|
| `protocol_version` | string | valor exacto `"daily-v1"` (ascii minúscula) |
| `environment` | string | enum cerrado, ascii minúscula: `"development"` \| `"staging"` \| `"production"` (un solo valor por carga) |
| `attempt_id` | string | UUID textual canónico: 8-4-4-4-12 en minúscula con guiones, generado en el servidor (ej. `3f2a1b0c-9d4e-4f8a-b6c1-2d5e7a9b0c1d`) |
| `nonce` | string | **base64url SIN padding** (RFC 4648 §5, sin `=`), exactamente 43 caracteres para 32 bytes CSPRNG |
| `public_key_hash` | string | **64 caracteres hexadecimales en minúscula** (SHA-256 del SPKI) — opción única; base64url NO permitido |
| `expires_at` | string | fecha-hora UTC en **RFC 3339 con precisión de segundos**, formato exacto `YYYY-MM-DDTHH:MM:SSZ` (sin fracción, sufijo `Z`, sin offset) |

> Si un valor no cumple la representación lexical de la tabla, la carga no es conforme y la verificación falla antes de la firma.

### 13.4 Vector de prueba canónico (obligatorio para toda implementación)

La siguiente entrada debe producir exactamente los bytes siguientes en **las tres plataformas**; es el criterio de salida para cualquier librería o implementación manual:

```json
{
  "protocol_version": "daily-v1",
  "environment": "production",
  "attempt_id": "3f2a1b0c-9d4e-4f8a-b6c1-2d5e7a9b0c1d",
  "nonce": "GGcDkg5kNS7t1zK9JkXLPgq6QszvUdmYPMdfXSJHS_Q",
  "public_key_hash": "92561e1d2633d5b7680ebefd7f92bc3e4084708ffabf82073bf028a24a90f24b",
  "expires_at": "2026-08-06T15:00:00Z"
}
```

Salida JCS (bytes UTF-8, 285 bytes):

```
{"attempt_id":"3f2a1b0c-9d4e-4f8a-b6c1-2d5e7a9b0c1d","environment":"production","expires_at":"2026-08-06T15:00:00Z","nonce":"GGcDkg5kNS7t1zK9JkXLPgq6QszvUdmYPMdfXSJHS_Q","protocol_version":"daily-v1","public_key_hash":"92561e1d2633d5b7680ebefd7f92bc3e4084708ffabf82073bf028a24a90f24b"}
```

Hex (los bytes UTF-8 del mismo texto — **vinculantes**):

```
7b22617474656d70745f6964223a2233663261316230632d396434652d346638612d623663312d326435653761396230633164222c22656e7669726f6e6d656e74223a2270726f64756374696f6e222c22657870697265735f6174223a22323032362d30382d30365431353a30303a30305a222c226e6f6e6365223a22474763446b67356b4e533774317a4b394a6b584c5067713651737a7655646d59504d646658534a48535f51222c2270726f746f636f6c5f76657273696f6e223a226461696c792d7631222c227075626c69635f6b65795f68617368223a2239323536316531643236333364356237363830656265666437663932626333653430383437303866666162663832303733626630323861323461393066323462227d
```

> El vector valida la canonicalización (igualdad byte a byte de la salida JCS en las tres plataformas), no la criptografía. No hay hash precomputado vinculante del vector: el vínculo contractual son los **bytes**.

---

*Documento de trabajo del entregable previo a código (revisión 4). Correcciones 1–7 aprobadas conceptualmente con condición (el auditor no pudo verificar línea por línea sin el archivo adjunto); integradas las 4 precisiones del protocolo de canje (intento de un solo uso, nonce CSPRNG, transacción con bloqueo, serialización JCS/CBOR byte a byte) y los resultados verificados de la matriz de librerías (sección 12). **Decisión de serialización APROBADA en el cierre de la revisión 4: JCS (RFC 8785) como único formato obligatorio; CBOR canónico descartado (sección 13).** La revisión 4 queda en **PASS DOCUMENTAL** (especificación congelada, no implementada; no autoriza código).*

---

### CIERRE FORMAL — REVISIÓN 4 DEL CONTRATO DE ACTIVACIÓN (2026-08-06)

**Estado documental: REVISIÓN 4 — PASS DOCUMENTAL.** La revisión 4 queda **congelada documentalmente** como especificación del contrato de activación (SUPERADA la revisión 2 del encabezado, conservada como historia). Este PASS DOCUMENTAL **NO autoriza ninguna implementación**.

**Garantías explícitas que el contrato deja definidas sin ambigüedad:**

| # | Garantía | Referencia en el documento |
|---|---|---|
| 1 | Intento de activación de **un solo uso** (rechazo de reutilización + idempotencia sin segundo dispositivo) | §3.1 precisión 1 · §4 `POST /api/activaciones/canjear` · §9 riesgo |
| 2 | **Nonce con CSPRNG de mínimo 32 bytes** (`secrets`/`os.urandom`, nunca `random`/timestamp) | §3.1 precisión 2 · §4 `POST /api/activaciones/desafio` · §9 riesgo |
| 3 | Verificación y consumo **transaccionales con bloqueo de fila** (equivalente a `SELECT ... FOR UPDATE` sobre código e intento) | §3.1 precisión 3 · §4 `canjear` · §9 riesgo |
| 4 | **Serialización determinista byte a byte — JCS (RFC 8785), único y obligatorio** (CBOR canónico descartado), orden de claves fijo y `SHA256withECDSA`; perfil canónico congelado + vector de prueba | §3.1 precisión 4 · §9 riesgo · **§13** |
| 5 | La carga serializada **incluye `environment` explícito** (`protocol_version` + `environment`) para impedir reutilización de firmas entre ambientes | §3.1 precisión 4 · §9 riesgo · §13.3 |

**Condiciones del PASS DOCUMENTAL (todas explícitas):**
- La especificación queda **congelada documentalmente** (serialización, estados, endpoints, migración, políticas — tal como figuran en este documento).
- **Todavía no está implementada** (no existe código de activación en el árbol).
- **No autoriza cambios de código, modelos, migraciones, dependencias, autenticación, sincronización ni UI.**
- **No inicia el Bloque 6.**
- La implementación futura requerirá una **instrucción separada** y explícita.
- Las **pruebas criptográficas y de concurrencia** (firma ECDSA, vector JCS, canje concurrente, un solo uso) siguen **pendientes de implementación**.

**Decisiones de implementación abiertas (NO bloquean el contrato documental; se resuelven en su fase):**
- Motor de identidad móvil: MethodChannel Android nativo (referencia segura) vs `attested_secure_keys` tras auditoría de código + PoC (§12) — decisión de implementación del Bloque 3.
- Transporte/auth: `http`/`dio`, OAuth, PKCE — decisión separada (Bloque 3/7), no fijada (§12.3).
- Código corto manual (bcrypt/argon2, `intentos_fallidos`) — condicional: solo si se habilita además del QR (§3.1).
- Librería JCS concreta por plataforma — se elige al implementar con el criterio de salida "bytes exactos del vector §13.4" (§13.2).

**Siguiente paso acordado (no iniciado):** Bloque 6 = implementar activación + autenticación backend, **solo después** de una instrucción separada de implementación. Sin commit/push/deploy/reinicio.
