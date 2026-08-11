# Daily System

**Cobro diario offline — Tu ruta, tus cobros y tu caja, incluso sin internet.**

![UI Gate](https://github.com/karen-claros1212/daily-system/actions/workflows/ui-gate.yml/badge.svg)

---

## Estado

**Alpha — APK Debug Construido**

| Componente | Estado |
|---|---|
| Backend API | Implementado |
| Android Offline Alpha | Implementado / APK debug construido |
| Panel web productivo | Planificado (`apps/web/` vacío; prototipo MOCK) |
| Prototipo web visual | Implementado (MOCK — no productivo) |
| Auth productivo (JWT ES256 + AndroidKeyStore) | ✅ Implementado |
| Bootstrap single-route | ✅ Implementado |
| Mobile auth bridge | ✅ Implementado |
| Offline sync (S0-S2 pull + session) | ✅ Implementado |
| Offline sync outbox (S3 push/ACK/retry) | ⏳ PENDIENTE |
| Splash nativo (Android 12+) | ✅ Implementado |
| Icono adaptable (adaptive) | ✅ Implementado |
| Tema claro/oscuro | ✅ Implementado |
| Diseño tokens (JSON → Dart + CSS) | ✅ Implementado |
| UI Gate CI | ✅ Estricto (flutter analyze + flutter test) |
| Backend CI | ⏳ PENDIENTE (no hay GitHub Actions de backend) |
| APK debug construido | ✅ PASS |
| Verificado en emulador (API 35) | ✅ PASS |
| Verificado en dispositivo físico | ⏳ PENDING |
| Pantallas reales refactorizadas | ✅ Implementado (Theme.of en todas) |
| Pruebas golden y semantics | ✅ Implementado (31 goldens + 37 semantics/widgets) + 77 sync/paridad/integration |
| Producción | Pendiente |

> **Rama de trabajo verificada:** `hardening/b1-b7-audit` — código baseline `c0a3a9c`; HEAD repositorio documental `35adf24`.
> `master` (`486d08b`) no contiene el hardening B1-B7 (hardening está **9 commits ahead / 0 behind** de master). Ver [Estado del proyecto](docs/STATUS.md) para detalle en vivo.

---

## Capturas

Capturas reales del emulador Android (phone 412×915, light y dark) y del prototipo web.
Generadas por `scripts/android/capture_ui_evidence.sh`; el conjunto completo before/after
está en [docs/ui-audit/screenshots/](docs/ui-audit/screenshots/) con manifest SHA-256.

### Android (claro)

| Login | Inicio | Hoja viva |
|---|---|---|
| ![Login](docs/assets/readme/mobile/01-login.png) | ![Inicio](docs/assets/readme/mobile/02-inicio.png) | ![Hoja viva](docs/assets/readme/mobile/03-cobros.png) |

| Pago | Movimientos | Caja |
|---|---|---|
| ![Pago](docs/assets/readme/mobile/04-pago.png) | ![Movimientos](docs/assets/readme/mobile/05-movimientos.png) | ![Caja](docs/assets/readme/mobile/06-caja.png) |

| Cierre | Historial |
|---|---|
| ![Cierre](docs/assets/readme/mobile/07-cierre.png) | ![Historial](docs/assets/readme/mobile/08-historial.png) |

### Android (oscuro)

| Login | Inicio | Cierre |
|---|---|---|
| ![Login dark](docs/assets/readme/mobile/01-login-dark.png) | ![Inicio dark](docs/assets/readme/mobile/02-inicio-dark.png) | ![Cierre dark](docs/assets/readme/mobile/07-cierre-dark.png) |

### Web

| Inicio | Cartera | Caja | Reportes |
|---|---|---|---|
| ![Web index](docs/assets/readme/web/01-index.png) | ![Web cartera](docs/assets/readme/web/02-cartera.png) | ![Web caja](docs/assets/readme/web/03-caja.png) | ![Web reportes](docs/assets/readme/web/04-reportes.png) |

> **Prototipo web visual (MOCK):** HTML/CSS estático sin JS, API, auth ni build. No es aplicación productiva. `apps/web/` está vacío. Ver [Web Blueprint](docs/web/WEB-UI-BLUEPRINT.md).

---

## Funciones implementadas

### Auth y seguridad del dispositivo
- Auth productivo: JWT ES256 con device/user/business/version binding
- AndroidKeyStore EC P-256 no exportable (SHA256withECDSA)
- Challenge-response single-use (daily-v1 para activación; daily-auth-v1 para auth)
- Bootstrap: credencial_bootstrap temporal → desafío/auth → access JWT → GET /api/mobile/bootstrap → sesión persistente (envelope atómico daily_session)
- Android permissions y `MethodChannel daily_system/device_identity` en `MainActivity.kt`

### Negocio y cobro
- Gestión de negocios, rutas y clientes
- Crédito con cálculo de cuota, mora y recargo
- Hoja viva del día con estados de pago
- Registro de pagos parciales y reversiones
- Jornada de caja: apertura, movimientos, cierre
- Snapshot de jornada con hash reproducible (canonical JSON)
- Generación de PDF de cierre de jornada
- Idempotencia financiera (clave_idempotencia, full-payload comparison, 409 on mismatch)
- Suscripciones por plan (free 1 ruta/100 clientes, básico 5/500, pro ilimitado)
- Límite de rutas y clientes por plan

### Offline sync
- **S0**: session maintenance (renew antes de expirar) — ✅ PASS
- **S1**: aislamiento de ruta (scope derivado por servidor; cliente no elige ruta) — ✅ PASS
- **S2**: pull servidor→móvil (GET /api/mobile/sync) + persistencia SQLite (UPSERT por PK, ON CONFLICT) — ✅ PASS
- **S3**: outbox móvil→servidor, push, ACK, retry y resolución de conflictos — ⏳ PENDIENTE

### UI/UX
- Flutter Offline Alpha con SQLite local
- Material 3 Expressive rediseño visual
- Sistema de diseño compartido (tokens JSON → Dart + CSS)
- Tema claro/oscuro con marca consistente
- Splash nativo Android 12+ (SplashScreen API)
- Icono adaptable con monochrome
- DAILY_DEMO flag para builds de producción

---

## Arquitectura

```
daily-system/
├── apps/
│   ├── mobile/          # Flutter app (Android) — primary client
│   │   ├── lib/
│   │   │   ├── main.dart              # DAILY_DEMO, Theme.of(context)
│   │   │   ├── database/   # SQLite v2/v3/v4, migraciones, seed
│   │   │   ├── domain/     # Tipos financieros, excepciones (JornadaGuard, etc.)
│   │   │   ├── models/     # DTOs y modelos (JornadaSnapshot, CajaResultado)
│   │   │   ├── navigation.dart  # MainShell → Inicio/Cobros/Historial/Más
│   │   │   ├── config.dart      # Flags, URLs
│   │   │   ├── auth/       # AuthHttpClient, DeviceAuthClient, DeviceIdentity, JCS, models
│   │   │   ├── sync/       # SyncClient (GET /api/mobile/sync), SyncRepository (UPSERT PK), SyncModels
│   │   │   ├── services/   # Caja, pago, hoja_viva, jornada, movimiento, sync_queue, pdf
│   │   │   ├── shell/      # MainShell, CobrosShell
│   │   │   ├── screens/    # 13 pantallas (login, inicio, cobros, pago, caja, cierre, etc.)
│   │   │   ├── theme/      # Tokens, tema, generador
│   │   │   ├── ui/         # Componentes Daily*
│   │   │   ├── widgets/
│   │   │   └── utils/
│   │   ├── android/app/         # Manifest, themes, AndroidManifest.xml (permissions)
│   │   ├── android/app/src/main/kt  # MainActivity.kt (MethodChannel device_identity)
│   │   ├── test/                # unit/widget/golden/semantics/paridad/sync
│   │   ├── test/auth/           # JCS vector, auth DTOs
│   │   ├── test/sync/           # SyncRepository (pendientes, upsert, S2-H2)
│   │   ├── test/helpers/
│   │   ├── test/goldens/
│   │   ├── integration_test/    # jornada_cierre_test.dart
│   │   └── build/               # APKs (gitignored)
│   └── api/             # FastAPI backend
│       ├── src/
│       │   ├── main.py          # FastAPI app, CORS, 13 routers
│       │   ├── auth/            # JWT ES256, JCS, DeviceAuth, context
│       │   ├── models/          # SQLAlchemy (12 tablas, incl. dispositivo)
│       │   ├── schemas/         # Pydantic
│       │   ├── routes/          # cliente, credito, dispositivo, hoja_viva,
│       │   │                   #   jornada, movimiento, negocio, pago, ruta,
│       │   │                   #   activacion (bootstrap + auth + sync)
│       │   ├── services/        # calculation, hoja_viva, jornada, movimiento,
│       │   │                   #   payment, activacion, auth_service, mobile_sync
│       │   └── tests/           # 13 archivos, 257 test functions
│       ├── migrations/          # Alembic: init → m2 → m3 → m5 → m7_desafio_auth
│       ├── alembic.ini
│       └── requirements.txt
├── design/
│   ├── brand/           # Logo, conceptos, rationale
│   ├── tokens/          # Tokens compartidos (JSON + generados)
│   └── prototypes/      # Prototipo web estático (MOCK visual)
├── docs/
│   ├── STATUS.md          # Estado vivo actual
│   ├── README.md          # Índice documental
│   ├── ARCHITECTURE.md    # Arquitectura vigente
│   ├── SECURITY.md        # Auth + device + tenant + ruta + idempotencia
│   ├── OFFLINE-SYNC.md    # S0-S3 contract
│   ├── TESTING.md         # Suites, gates, CI
│   ├── IMPLEMENTATION-PLAN.md
│   ├── ENGRAM-PROTOCOL.md
│   ├── DOCUMENTO-MAESTRO-Plataforma-Cobro-Colombia-v1.3-CERRADO.md
│   ├── ADR-INFRA-NAMING.md
│   ├── ui-audit/        # Auditoría visual before/after
│   ├── web/             # Web UI blueprint
│   ├── assets/          # Capturas README optimizadas
│   └── decisions/
├── scripts/
│   ├── ci/              # ui_gate.sh (strict — analyze + test + tokens)
│   └── android/         # capture_ui_evidence.sh
├── tool/
│   └── generate_design_tokens.dart
├── infra/
│   ├── docker-compose.yml    # cobro-postgres (port 7103), DB cobro
│   ├── init.sql
│   └── .env.example
├── DAILY-SYSTEM-*.md    # Archivo maestro, auditoría activación, handoff
└── graphify-out/        # Regenerable (gitignored)
```

---

## Inicio rápido

### Requisitos

- Flutter 3.44+ / Dart 3.12+ (Android SDK 35)
- Python 3.12+ (backend)
- PostgreSQL 18+ (para backend productivo; tests usan SQLite por defecto)
- Docker (para PostgreSQL dev: `docker start cobro-postgres`)

### Backend

```bash
cd apps/api
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt  # dependencias Python
alembic upgrade head  # migraciones a PostgreSQL
uvicorn src.main:app --reload  # servidor desarrollo
```

### Móvil

```bash
cd apps/mobile
flutter pub get
flutter analyze          # No issues found!
flutter test             # 147/147 passing (incluye goldens, semantics, paridad, sync)
flutter run              # requiere dispositivo/emulador
flutter build apk --debug  # genera build/app/outputs/flutter-apk/app-debug.apk
```

---

## Pruebas y gates

> **Último baseline verificado (2026-08-11):** ejecutado localmente contra `hardening/b1-b7-audit` @ `c0a3a9c`.
> No equivale a GitHub Actions salvo el workflow `ui-gate.yml` que existe explícitamente.

```bash
# Gate de UI (strict — no --no-fatal flags)
scripts/ci/ui_gate.sh

# Tests móviles
cd apps/mobile
flutter analyze          # No issues found!
flutter test             # 147 passing

# Tokens (deterministic)
dart run tool/generate_design_tokens.dart --check

# Backend (SQLite default)
cd apps/api
python3 -m pytest src/tests/   # 255 passed, 7 skipped (257 funciones)
python3 -m alembic check       # No new upgrade operations detected

# Backend (PostgreSQL — requiere scratch DB)
#   API_DATABASE_URL=postgresql://cobro:cobro_secret@localhost:7103/cobro_scratch_b6_pg \
#   DAILY_ENV=test ALLOW_PG_TRUNCATE=1 python3 -m pytest src/tests/ -q
```

| Gate | Resultado | Tool |
|---|---|---|
| Flutter analyze | No issues found | flutter analyzer |
| Flutter test (mobile) | 147 passing | flutter_test |
| Backend pytest (SQLite) | 255 passed, 7 skipped | pytest |
| Alembic | head = m7_desafio_auth, clean | alembic |
| UI Gate CI | PASS (GitHub Actions) | `.github/workflows/ui-gate.yml` |
| Backend CI | ⛔ NO EXISTE | — |

---

## Roadmap

- [x] M0: Fundación ejecutable
- [x] M1: Hoja viva y pagos
- [x] M2: Jornada, caja y Terminar Jornada
- [x] M3 base: Suscripción / límites por plan
- [!] M3.2-M3.5 históricos: Bot Telegram, panel inversionista, reporte diario — **no implementados** en el árbol actual
- [x] M3.6: Flutter Offline Alpha + Visual Alpha Premium
- [x] UX/UI Premium: marca, tokens, componentes, tema
- [x] UX/UI Phase 2: splash nativo, DAILY_DEMO, light/dark, CSS generator, gate estricto
- [x] Splash nativo Android 12+ (SplashScreen API)
- [x] Icono adaptable con monochrome
- [x] Pantallas reales refactorizadas (inicio, cobros, pago, caja, cierre)
- [x] Pruebas golden y semantics
- [x] APK debug construido
- [x] Verificado en emulador (API 35)
- [ ] Verificado en dispositivo físico
- [x] Capturas profesionales before/after con manifest SHA-256
- [x] **B1-B7 hardening:** JWT ES256, AndroidKeyStore, challenge-response, bootstrap productivo, S0-S2 sync
- [ ] S3: outbox móvil→servidor (push/ACK/retry/conflictos)
- [ ] M4: Importación OCR (_`ocr_service.py` no existe en árbol_)
- [ ] M5: Score, chatbot, inteligencia
- [ ] M6: Producción y despliegue

> ⚠️ M3.3 (Bot Telegram) y M3.4 (Panel inversionista): **históricos, no implementados.**
> `apps/telegram-bot/` no existe; `apps/web/` está vacío. Ver nota de reconciliación en `docs/STATUS.md`.

---

## Seguridad

- Auth productivo: **JWT ES256** con device/user/negocio/version_asignacion binding
- **AndroidKeyStore** EC P-256, clave privada no exportable (SHA256withECDSA)
- Challenge-response single-use (daily-auth-v1; daily-v1 para activación)
- Tenant isolation (multi-negocio, filtrado server-side)
- Route isolation (scope derivado del servidor; cliente no elige ruta)
- Idempotencia financiera (clave_idempotencia + full-payload comparison; 409 on mismatch)
- JCS (RFC 8785) canonicalización byte-exacta en auth y activación
- SQLite local con migraciones versionadas (v2/v3/v4)
- Hash reproducible SHA-256 de snapshot de jornada (canonical JSON)
- Backend FastAPI con auth JWT (no sesión)
- Suscripciones y límites por plan

Ver [Security](docs/SECURITY.md), [Offline Sync](docs/OFFLINE-SYNC.md), [Architecture](docs/ARCHITECTURE.md).

---

## Documentación

| Documento | Tipo | Propósito |
|---|---|---|
| [STATUS.md](docs/STATUS.md) | **Estado vivo** | Estado productivo actual (verdad primaria) |
| [README.md](docs/README.md) | Índice | Navegador documental |
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | Normativo | Arquitectura vigente |
| [SECURITY.md](docs/SECURITY.md) | Normativo | Auth, device, tenant, ruta, idempotencia |
| [OFFLINE-SYNC.md](docs/OFFLINE-SYNC.md) | Normativo | S0-S3 contract + gaps |
| [TESTING.md](docs/TESTING.md) | Estado vivo | Suites, gates, CI |
| [IMPLEMENTATION-PLAN.md](docs/IMPLEMENTATION-PLAN.md) | Estado vivo | Roadmap reconciliado |
| [ENGRAM-PROTOCOL.md](docs/ENGRAM-PROTOCOL.md) | Normativo | Memoria de agentes |
| [Documento Maestro v1.3](docs/DOCUMENTO-MAESTRO-Plataforma-Cobro-Colombia-v1.3-CERRADO.md) | Normativo | Especificaciones |
| [Auditoría UI/UX](docs/ui-audit/) | Evidencia | Before/after premium |
| [Web Blueprint](docs/web/WEB-UI-BLUEPRINT.md) | Normativo | Prototipo web MOCK |

> 📌 **Verdad documental vigente:** `docs/STATUS.md` + `DAILY-SYSTEM-CONTEXT-HANDOFF.md` + `DAILY-SYSTEM-ARCHIVO-MAESTRO-CONTINUIDAD-OPENCODE.md`.
> El handoff operativo vigente es `DAILY-SYSTEM-CONTEXT-HANDOFF.md` (verificación 2026-08-11 sobre `c0a3a9c`).

---

## Licencia

Código con derechos reservados. No se concede licencia de uso,
copia o distribución fuera de los acuerdos autorizados.
