# Arquitectura — Daily System

**Documento:** Normativo
**Última actualización:** 2026-08-11
**Base verificada:** `c0a3a9c` (baseline código S0-S2)
**HEAD (repositorio):** dinámico — `git rev-parse HEAD`

---

## Principios

1. **El backend es la autoridad.** El móvil calcula offline con reglas deterministas, pero el servidor valida, autoriza y registra el estado canónico.
2. **El servidor deriva el scope.** El móvil nunca envía `negocio_id`, `cobrador_id` o `ruta_id` como autoridad — se derivan del JWT + device binding.
3. **Rutas son dinámicas e indefinidas.** Nada asume R1/R2/R3/R4 de forma fija.
4. **Money = integers (COP).** Rates = NUMERIC.
5. **Append-only.** Pagos, reversiones, movimientos, cierres y ajustes son inmutables y trazables.

---

## Stack

| Capa | Tecnología |
|---|---|
| Mobile client | Flutter (Android), SQLite local |
| Mobile auth | JWT ES256 + AndroidKeyStore (EC P-256, SHA256withECDSA) |
| Backend | Python, FastAPI, SQLAlchemy, Alembic |
| DB (prod) | PostgreSQL 18 |
| DB (test mobile) | SQLite in-memory |
| DB (test backend) | SQLite (default) / PostgreSQL scratch (concurrency) |
| CI | GitHub Actions: `ui-gate.yml` (móvil) — backend CI pendiente |

---

## Arquitectura

### Mobile Flutter (Android — collector offline)

```
apps/mobile/
├── lib/
│   ├── main.dart              # Entry: DAILY_DEMO flag, theme, routes
│   ├── config.dart            # Flags, API base URL, timeouts
│   ├── navigation.dart        # MainShell → Inicio/Cobros/Historial/Más
│   ├── auth/                  # Production auth bridge
│   │   ├── auth_http_client.dart   # Single HTTP client, bearer JWT, 401→borrarToken
│   │   ├── device_auth_client.dart  # Challenge-response (daily-auth-v1), renewal
│   │   ├── device_identity.dart     # MethodChannel → MainActivity.kt → AndroidKeyStore
│   │   ├── jcs.dart                  # RFC 8785 canonicalization (Dart)
│   │   ├── auth_token_store.dart     # Secure token persistence
│   │   └── models.dart               # DesafioAuth, CanjearAuth, BootstrapIdentity, etc.
│   ├── sync/                  # Offline sync (S0-S3 implemented)
│   │   ├── sync_client.dart      # GET /api/mobile/sync, session renewal (S0-S1)
│   │   ├── sync_models.dart       # SyncDataset/Cliente/Credito/Cuota/Pago/Movimiento/Jornada
│   │   └── sync_repository.dart   # UPSERT por PK (ON CONFLICT), protección pendientes
│   ├── database/            # SQLite v2/v3/v4, migraciones, seed, tablas
│   ├── domain/              # Tipos financieros, excepciones, JornadaGuard
│   ├── models/              # DTOs (JornadaSnapshot, CajaResultado)
│   ├── services/            # caja, hoja_viva, jornada, pago, movimiento, pdf, sync_queue
│   ├── screens/             # 13 pantallas
│   ├── shell/               # MainShell, CobrosShell
│   ├── theme/               # Tokens, tema, generador
│   ├── ui/                  # Componentes Daily*
│   ├── widgets/
│   └── utils/
├── android/app/             # Manifest, themes, icons, splash
├── android/app/src/main/kt/ # MainActivity.kt (device identity channel)
├── test/                    # Unit/widget/golden/semantics/paridad/sync
├── test/auth/               # JCS vector, auth DTOs
├── test/sync/               # SyncRepository upsert/pendientes/S2-H2
├── test/paridad_b5_test.dart
├── integration_test/        # jornada_cierre_test.dart
└── build/                   # APKs (gitignored)
```

**Flow diario:**
```
DeviceIdentity (AndroidKeyStore) → DeviceAuthClient (challenge/response JCS)
        ↓
    JWT ES256 (Bearer)
        ↓
    SyncClient.sincronizar() → GET /api/mobile/sync → SyncRepository (UPSERT PK)
        ↓
    Hoja Viva / Cobros / Caja / Cierre (offline)
        ↓
    MovimientoService / PagoService / JornadaService (local SQLite)
        ↓
    sync_queue (outbox) ← S3 IMPLEMENTADO (PushOrchestrator: push → server → ACK → retry)
```

### Backend FastAPI

```
apps/api/
├── src/
│   ├── main.py              # App, CORS, 13 routers, startup checks
│   ├── auth/
│   │   ├── deps.py          # get_request_context, JWT ES256 validation, fail-closed
│   │   ├── jcs.py           # RFC 8785 canonicalization (Python)
│   │   ├── auth_jcs.py      # Auth-profile canonicalization
│   │   └── context.py       # RequestContext (negocio, cobrador, ruta, rol, device)
│   ├── models/              # SQLAlchemy (12 tablas: negocio, usuario, ruta, dispositivo, cliente, credito, cuota_programada, jornada, pago, movimiento_caja, suscripcion, plan_limite)
│   ├── schemas/             # Pydantic (JornadaCreate, JornadaCierreCreate, JornadaSyncResponse, etc.)
│   ├── routes/              # 13 routers
│   │   ├── activacion.py    # /api/activaciones/* + /api/mobile/bootstrap + /api/auth/device/* + /api/mobile/sync
│   │   ├── cliente.py       # /api/clientes
│   │   ├── credito.py       # /api/creditos
│   │   ├── dispositivo.py   # /api/dispositivos, /api/dispositivos/{id}/reemplazar
│   │   ├── hoja_viva.py     # /api/hoja-viva
│   │   ├── jornada.py       # /api/jornadas (open, close, sync, caja, preparar-siguiente)
│   │   ├── movimiento.py    # /api/movimientos (POST/GET — idempotency)
│   │   ├── negocio.py       # /api/negocios
│   │   ├── pago.py          # /api/pagos (POST, reversar, GET) — idempotency
│   │   ├── ruta.py          # /api/rutas
│   │   ├── inversionista.py # (panel admin, pendiente)
│   │   └── __init__.py
│   ├── services/
│   │   ├── calculation_service.py
│   │   ├── hoja_viva_service.py
│   │   ├── jornada_service.py    # cierre/sincronizar logic + state machine
│   │   ├── movimiento_service.py # register_movimiento, naturaleza server-derived
│   │   ├── payment_service.py    # register_payment, reverse_payment
│   │   ├── activacion_service.py # generar_codigo, desafio, canjear, bootstrappear
│   │   ├── auth_service.py       # JWT generation, desafio/canjear (daily-auth-v1)
│   │   └── mobile_sync_service.py # sync_dataset (ruta activa única)
│   ├── tests/               # 13 files, 257 test functions
│   └── utils/
├── migrations/              # Alembic: init → m2_apertura → m2_jornada → m3_dispositivo → m5_dispositivo_activacion → m7_desafio_auth
├── alembic.ini
└── requirements.txt
```

**API routes (13 routers):**

| Router | Prefix | Auth | Purpose |
|---|---|---|---|
| activacion | `/api/activaciones/*` | admin / público | Codigo, challenge, canje, bootstrap, device auth, sync |
| cliente | `/api/clientes` | JWT | Clientes (scoped por ruta) |
| credito | `/api/creditos` | JWT | Créditos, cuotas |
| dispositivo | `/api/dispositivos/*` | admin / cobrador | Device lifecycle, replace |
| hoja_viva | `/api/hoja-viva` | JWT | Daily sheet for active route |
| jornada | `/api/jornadas/*` | JWT | Open/close/sync/caja/preparar |
| movimiento | `/api/movimientos` | JWT | POST (idempotency), GET |
| negocio | `/api/negocios` | JWT (admin) | Tenant management |
| pago | `/api/pagos/*` | JWT | POST, reversar, GET (idempotency) |
| ruta | `/api/rutas` | JWT | Routes, scope |
| inversionista | `/api/inversionista/*` | investor/admin | Reporting (future) |

### Web (`apps/web/`)

**VACÍO.** Solo prototipo estático HTML/CSS en `design/prototypes/web/`. No es aplicación productiva. Ver [WEB-UI-BLUEPRINT.md](web/WEB-UI-BLUEPRINT.md).

---

## Sync architecture (S0-S3)

Ver [`OFFLINE-SYNC.md`](OFFLINE-SYNC.md) para el contrato completo.

| Capa | Responsabilidad | Estado |
|---|---|---|
| S0 | Session maintenance (renew before expiry) | ✅ Implementado |
| S1 | Route isolation (server-side scope) | ✅ Implementado |
| S2 | Pull dataset + SQLite persistence (UPSERT PK) | ✅ Implementado |
| S3 | Outbox push → ACK → retry → conflict resolution | ✅ Implementado |

---

## Auth flow

```
1. Device genera EC P-256 en AndroidKeyStore (privada no exportable)
2. POST /api/activaciones/desafio → nonce + intento_id
3. Device firma nonce con JCS (RFC 8785) → SHA256withECDSA
4. POST /api/activaciones/canjear → credencial_bootstrap TEMPORAL (no JWT; un solo uso, nunca reutilizado como access token)
5. POST /api/auth/device/desafio (Bearer: credencial_bootstrap) → challenge (daily-auth-v1)
6. Device firma challenge → POST /api/auth/device/canjear → access token JWT ES256 (claims congeladas)
7. GET /api/mobile/bootstrap (Bearer: access JWT) → identity (negocio, cobrador, ruta única)
8. SyncClient usa Bearer JWT; DeviceAuthClient renueva antes de expirar (S0)
```

Ver [`SECURITY.md`](SECURITY.md) para detalles de claims, revocación y version_asignacion.
