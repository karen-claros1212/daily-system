# Arquitectura — Daily System

**Documento:** Normativo
**Última actualización:** 2026-08-15
**Base verificada:** `product/web-premium-v1` @ `bbb3e102`

---

## Principios

1. **El backend es la autoridad.** El móvil calcula offline con reglas deterministas, pero el servidor valida, autoriza y registra el estado canónico.
2. **El servidor deriva el scope.** El móvil nunca envía `negocio_id`, `cobrador_id` o `ruta_id` como autoridad — se derivan del JWT + device binding.
3. **Rutas son dinámicas e indefinidas.** Nada asume R1/R2/R3/R4 de forma fija.
4. **Money = integers (COP).** Rates = NUMERIC.
5. **Append-only.** Pagos, reversiones, movimientos, cierres y ajustes son inmutables y trazables.
6. **El frontend web nunca deduce identidad ni rol.** La sesión consulta `/api/auth/me`; los permisos se resuelven por capacidades server-side.

---

## Stack

| Capa | Tecnología |
|---|---|
| Mobile client | Flutter (Android), SQLite local, offline-first |
| Mobile auth | JWT ES256 + AndroidKeyStore (EC P-256, SHA256withECDSA) |
| Backend | Python, FastAPI, SQLAlchemy, Alembic |
| Web admin | Next.js 16 · React 19 · TypeScript · Tailwind CSS · Playwright E2E |
| DB (prod) | PostgreSQL 18 |
| DB (test mobile) | SQLite in-memory |
| DB (test backend) | SQLite (default) / PostgreSQL scratch (concurrency) |
| CI | GitHub Actions: `backend-ci.yml` · `web-ci.yml` · `ui-gate.yml` (3 workflows) |

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
│   ├── sync/                  # Offline sync (S0-S5)
│   │   ├── sync_client.dart      # GET /api/mobile/sync, session renewal (S0-S1)
│   │   ├── sync_models.dart       # SyncDataset/Cliente/Credito/Cuota/Pago/Movimiento/Jornada
│   │   ├── sync_repository.dart   # UPSERT por PK (ON CONFLICT), protección pendientes
│   │   └── push_orchestrator.dart # Outbox push → ACK → retry (S3) + dependencias
│   ├── database/            # SQLite v2..v7, migraciones, seed, tablas
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
├── test/                    # Unit/widget/golden/semantics/paridad/sync (177)
├── test/auth/               # JCS vector, auth DTOs
├── test/sync/               # SyncRepository + push_orchestrator (S3-S5)
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
    sync_queue (outbox) → PushOrchestrator (push → server → ACK → retry → conflictos S3/S5)
```

### Backend FastAPI

```
apps/api/
├── src/
│   ├── main.py              # App, CORS, 15 routers, startup checks
│   ├── auth/
│   │   ├── deps.py          # get_request_context, JWT ES256 validation, fail-closed
│   │   ├── jcs.py           # RFC 8785 canonicalization (Python)
│   │   ├── auth_jcs.py      # Auth-profile canonicalization
│   │   └── context.py       # RequestContext (negocio, cobrador, ruta, rol, device)
│   ├── models/              # SQLAlchemy (negocio, usuario, ruta, dispositivo, cliente, credito, cuota_programada, jornada, pago, movimiento_caja, suscripcion, plan_limite)
│   ├── schemas/             # Pydantic (JornadaCreate, JornadaCierreCreate, JornadaSyncResponse, MeResponse, InversionistaSummaryResponse, SuscripcionStatusResponse, …)
│   ├── routes/              # 15 routers
│   │   ├── negocio.py       # /api/negocios — tenant
│   │   ├── onboarding.py    # /api/onboarding — registro de negocio (NIT invariante)
│   │   ├── ruta.py          # /api/rutas
│   │   ├── cliente.py       # /api/clientes
│   │   ├── credito.py       # /api/creditos
│   │   ├── pago.py          # /api/pagos (POST, reversar, GET — idempotencia)
│   │   ├── hoja_viva.py     # /api/hoja-viva
│   │   ├── jornada.py       # /api/jornadas (open, close, sync, caja, preparar-siguiente)
│   │   ├── movimiento.py    # /api/movimientos (POST/GET — idempotencia)
│   │   ├── dispositivo.py   # /api/dispositivos, /api/dispositivos/{id}/reemplazar
│   │   ├── activacion.py    # /api/activaciones/* (desafio, canje, bootstrap)
│   │   ├── mobile.py        # /api/mobile/* (bootstrap, sync)
│   │   ├── device.py        # /api/auth/device/* (daily-auth-v1)
│   │   ├── auth.py          # /api/auth/* (me — identidad web)
│   │   └── inversionista.py # /api/inversionista/* (resumen, suscripcion — panel web)
│   ├── services/
│   │   ├── calculation_service.py
│   │   ├── hoja_viva_service.py
│   │   ├── jornada_service.py    # cierre/sincronizar logic + state machine
│   │   ├── movimiento_service.py # register_movimiento, naturaleza server-derived
│   │   ├── payment_service.py    # register_payment, reverse_payment
│   │   ├── activacion_service.py # generar_codigo, desafio, canjear, bootstrappear
│   │   ├── auth_service.py       # JWT generation, desafio/canjear (daily-auth-v1), me
│   │   ├── mobile_sync_service.py # sync_dataset (ruta activa única)
│   │   └── conflict_service.py   # S5 — 6 verificadores server-authoritative de conflicto
│   ├── tests/               # 367 passed, 8 skipped (SQLite)
│   └── utils/
├── migrations/              # Alembic: init → m2..m8_negocio_nit (head)
├── alembic.ini
└── requirements.txt
```

**API routers (15):**

| Router | Prefix | Auth | Purpose |
|---|---|---|---|
| negocio | `/api/negocios` | JWT (admin) | Tenant management |
| onboarding | `/api/onboarding` | público (bootstrap) | Registro de negocio, NIT 201/409 |
| ruta | `/api/rutas` | JWT | Routes, scope |
| cliente | `/api/clientes` | JWT | Clientes (scoped por ruta) |
| credito | `/api/creditos` | JWT | Créditos, cuotas |
| pago | `/api/pagos/*` | JWT | POST, reversar, GET (idempotencia) |
| hoja_viva | `/api/hoja-viva` | JWT | Daily sheet for active route |
| jornada | `/api/jornadas/*` | JWT | Open/close/sync/caja/preparar |
| movimiento | `/api/movimientos` | JWT | POST (idempotency), GET |
| dispositivo | `/api/dispositivos/*` | admin / cobrador | Device lifecycle, replace |
| activacion | `/api/activaciones/*` | admin / público | Codigo, challenge, canje, bootstrap |
| mobile | `/api/mobile/*` | JWT (device) | bootstrap, sync |
| device | `/api/auth/device/*` | credencial_bootstrap | daily-auth-v1 challenge/auth |
| auth | `/api/auth/*` | JWT | me — identidad del panel web |
| inversionista | `/api/inversionista/*` | investor/admin | resumen, suscripcion (panel web) |

### Web — Panel administrativo (`apps/web/`) — PRODUCTIVO

Next.js 16 · React 19 · TypeScript · Tailwind CSS. El panel es una aplicación productiva; el
prototipo estático MOCK de `design/prototypes/web/` es histórico.

```
apps/web/
├── src/app/
│   ├── layout.tsx            # Metadata + HTML shell
│   ├── page.tsx              # `/` → LoginPage o redirect /dashboard
│   ├── dashboard/            # Despacha superficie según rol (COBRADOR / INVERSIONISTA / ADMINISTRADOR)
│   ├── caja/                 # Caja / jornada
│   ├── dispositivos/         # Gestión de dispositivos
│   ├── registro/             # Onboarding — registro de negocio
│   ├── reportes/             # Reportes
│   ├── routes/               # Rutas
│   ├── suscripcion/          # Plan / suscripción
│   ├── api/                  # BFF — route handlers (auth, dispositivos, rutas, jornadas,
│   │   │                    #   inversionista, activaciones, onboarding)
│   └── globals.css
├── src/lib/
│   ├── session.ts            # fetchSession: cookie httpOnly daily_admin_token → GET /api/auth/me
│   ├── rbac.ts               # hasCapability / canViewFinancial / isCobrador (puro)
│   ├── api/client.ts         # API_BASE, fetch helpers
│   ├── api/gateway.ts        # Gateway BFF hacia el backend
│   ├── api/generated/        # Cliente TS generado (openapi-typescript)
│   └── auth/
├── src/components/           # LoginPage + componentes del panel
├── e2e/                      # 19 spec files (Playwright mock + real + a11y axe)
├── playwright.config.ts      # mock (:8100)
├── playwright.config.real.ts # real (:8001, FastAPI + PostgreSQL)
├── next.config.mjs           # Next 16, devIndicators top-right
├── tailwind.config.* / postcss.*
└── package.json
```

**Web identity flow:**
```
POST /api/auth/web (BFF) → backend valida credenciales → JWT web
        ↓
Cookie httpOnly `daily_admin_token` (Bearer)
        ↓
Cada request: GET /api/auth/me → rol derivado de la DB (fuente canónica)
        ↓
hasCapability(...) server-side → renderizado por rol (COBRADOR / INVERSIONISTA / ADMINISTRADOR)
```

---

## Sync architecture (S0-S5)

Ver [`OFFLINE-SYNC.md`](OFFLINE-SYNC.md) para el contrato completo.

| Capa | Responsabilidad | Estado |
|---|---|---|
| S0 | Session maintenance (renew before expiry) | ✅ PASS |
| S1 | Route isolation (server-side scope) | ✅ PASS |
| S2 | Pull dataset + SQLite persistence (UPSERT PK) | ✅ PASS |
| S3 | Outbox push → ACK → retry → conflict resolution | ✅ PASS |
| S4 | Reasignación de ruta R1→R2 (ruta_id_origen inmutable) + orquestación sync | ✅ PASS |
| S5 | `conflict_service.py` — verificadores server-authoritative (pago, movimiento, jornada, apertura, reversal, ruta) | ✅ PASS |

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
