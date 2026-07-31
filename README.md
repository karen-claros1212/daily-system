# Daily System

**Cobro diario offline — Tu ruta, tus cobros y tu caja, incluso sin internet.**

---

## Estado

**Alpha — Pre-APK**

| Componente | Estado |
|---|---|
| Backend API | Implementado |
| Android Offline Alpha | Implementado / en pulido |
| Panel web productivo | Planificado |
| Prototipo web visual | Implementado |
| APK de prueba física | Pendiente |
| Producción | Pendiente |

---

## Capturas

### Android

<!-- Capturas optimizadas en docs/assets/readme/mobile/ -->

### Web

<!-- Prototipo visual en design/prototypes/web/ -->

---

## Funciones implementadas

- Autenticación de cobrador con sesión persistente
- Gestión de negocios, rutas y clientes
- Crédito con cálculo de cuota, mora y recargo
- Hoja viva del día con estados de pago
- Registro de pagos parciales y reversiones
- Jornada de caja: apertura, movimientos, cierre
- Snapshot de jornada con hash reproducible
- Generación de PDF de cierre de jornada
- Sincronización colas con backend FastAPI
- Suscripciones por plan (free, básico, pro)
- Límite de rutas y clientes por plan
- Flutter Offline Alpha con SQLite local
- Material 3 Expressive rediseño visual
- Sistema de diseño compartido (tokens)
- Tema claro/oscuro con marca consistente

---

## Arquitectura

```
daily-system/
├── apps/
│   ├── mobile/          # Flutter app (Android)
│   │   ├── lib/
│   │   │   ├── main.dart
│   │   │   ├── database/    # SQLite, migraciones, seed
│   │   │   ├── domain/      # Tipos financieros, excepciones
│   │   │   ├── models/      # DTOs y modelos
│   │   │   ├── routes/      # Rutas de navegación
│   │   │   ├── screens/     # Pantallas de la app
│   │   │   ├── services/    # Caja, pago, hoja viva, etc.
│   │   │   ├── shell/       # Shell principal
│   │   │   ├── theme/       # Tokens, tema, generador
│   │   │   └── ui/          # Componentes Daily*
│   │   └── test/
│   └── api/             # FastAPI backend
│       ├── src/
│       ├── migrations/  # Alembic migrations
│       └── tests/
├── design/
│   ├── brand/           # Logo, conceptos, rationale
│   ├── tokens/          # Tokens compartidos (JSON + generados)
│   └── prototypes/      # Prototipo web estático
├── docs/
│   ├── ui-audit/        # Auditoría visual before/after
│   ├── web/             # Web UI blueprint
│   ├── assets/          # Capturas README optimizadas
│   └── DOCUMENTO-MAESTRO-Plataforma-Cobro-Colombia-v1.3-CERRADO.md
├── scripts/
│   ├── ci/              # ui_gate.sh
│   └── android/         # capture_ui_evidence.sh
├── tool/
│   └── generate_design_tokens.dart
└── graphify-out/
```

---

## Inicio rápido

### Requisitos

- Flutter 3.44+
- Dart 3.12+
- PostgreSQL 18+ (para backend)

### Backend

```bash
cd apps/api
flutter pub get  # para dependencias Python en requirements.txt
alembic upgrade head  # migraciones a PostgreSQL
uvicorn src.main:app --reload  # servidor desarrollo
```

### Móvil

```bash
cd apps/mobile
flutter pub get
flutter analyze
flutter test
flutter run  # requiere dispositivo/emulador
```

---

## Pruebas y gates

```bash
# Gate de UI
scripts/ci/ui_gate.sh

# Tests móviles
cd apps/mobile
flutter analyze
flutter test

# Tokens
dart run tool/generate_design_tokens.dart --check

# Backend
cd apps/api
pytest src/tests/
alembic check
```

---

## Roadmap

- [x] M0: Fundación ejecutable
- [x] M1: Hoja viva y pagos
- [x] M2: Jornada, caja y Terminar Jornada
- [x] M3: Suscripción, Telegram, inversionista
- [x] M3.6: Flutter Offline Alpha + Visual Alpha Premium
- [x] UX/UI Premium: marca, tokens, componentes, tema
- [ ] Pantallas reales refactorizadas (inicio, cobros, pago, caja, cierre)
- [ ] Icono adaptable y splash nativo
- [ ] Pruebas golden y semantics
- [ ] APK de prueba física
- [ ] M4: Importación OCR
- [ ] M5: Score, chatbot, inteligencia
- [ ] M6: Producción y despliegue

---

## Seguridad

- SQLite local con migraciones versionadas
- Colas de sincronización con hash de integridad
- Idempotencia en pagos y apertura de jornada
- Snapshots de jornada con SHA-256
- Backend FastAPI con autenticación por sesión
- Suscripciones y límites por plan

---

## Documentación

- [Documento Maestro v1.3](docs/DOCUMENTO-MAESTRO-Plataforma-Cobro-Colombia-v1.3-CERRADO.md)
- [Plan de Implementación](docs/IMPLEMENTATION-PLAN.md)
- [Estado del proyecto](docs/STATUS.md)
- [Blueprint Web UI](docs/web/WEB-UI-BLUEPRINT.md)
- [Auditoría UX/UI Premium](docs/ui-audit/DAILY-SYSTEM-UX-UI-PREMIUM-AUDIT.md)

---

## Licencia

Código con derechos reservados. No se concede licencia de uso,
copia o distribución fuera de los acuerdos autorizados.
