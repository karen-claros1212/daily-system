# Daily System — UX/UI Premium Audit

**Fecha:** 2026-07-31
**BASE_SHA:** 3a1a566ce68ad01be1050583575061c17d7a39b7
**CODE_SHA:** 8cfe225 (código de la app auditado — UI, tests, goldens)
**EVIDENCE_SHA:** 95b2488 (68 capturas before/after + script autovalidado + manifest)
**GATE_SHA:** fec6fa5 (corrección del paso de generador) + 30b2984 (dedupe generador)
**AUDIT_SHA:** (se registra en el commit final)
**FINAL_HEAD:** (se registra en el commit final)

---

## Resumen Ejecutivo

**Veredicto: PASS — Todos los controles críticos corregidos**

7 defectos críticos corregidos en UX/UI Phase 2 + refactorización completa.

**Tests:** 68/68 passing, 0 errors, 0 warnings
**Analyzer:** No issues found!
**APK:** Debug construido exitosamente (demo 228MB / default 228MB)

---

## 1. Splash

| Aspecto | Antes | Después |
|---|---|---|
| Fondo | Blanco genérico | `#0B4654` petrol de marca |
| Símbolo | Ninguno | `ic_launcher_foreground` centrado |
| API | AndroidManifest old | SplashScreen API (Android 12+) |
| Compatibilidad | Solo pre-Android 12 | Android <31 + Android 12+ |

**Files:**
- `apps/mobile/android/app/src/main/res/drawable/launch_background.xml`
- `apps/mobile/android/app/src/main/res/values-v31/styles.xml`
- `apps/mobile/android/app/build.gradle.kts` (core-splashscreen dependency)

---

## 2. DAILY_DEMO

| Aspecto | Antes | Después |
|---|---|---|
| Demo info | Siempre visible (defaultValue: true) | Condicional `kDailyDemo` (defaultValue: false) |
| Build flag | Hardcoded | `bool.fromEnvironment('DAILY_DEMO')` |
| Producción | Datos demo visibles | Oculto con `--dart-define=DAILY_DEMO=false` |

**Files:**
- `apps/mobile/lib/main.dart` — `const kDailyDemo = bool.fromEnvironment('DAILY_DEMO', defaultValue: false)`

---

## 3. Login Light/Dark

| Aspecto | Antes | Después |
|---|---|---|
| Colores | `AppColors.*` hardcoded | `Theme.of(context).colorScheme.*` |
| Fondo | `AppColors.primary.withAlpha(0.08)` | `theme.colorScheme.primary.withAlpha(0.08)` |
| Superficie | `AppColors.surface` | `theme.colorScheme.surface` |
| Texto | `AppColors.textPrimary` | `theme.colorScheme.onSurface` |
| Tagline | `AppColors.outlineVariant` | `theme.colorScheme.onSurfaceVariant` |

**Files:**
- `apps/mobile/lib/main.dart` — `_LoginScreen.build()` usa `Theme.of(context)`

---

## 4. Logo Semantics

| Aspecto | Antes | Después |
|---|---|---|
| Semantics | CustomPaint expone semantics | `ExcludeSemantics` wrapper |
| Accesibilidad | Duplicación con texto "Daily System" | Texto adjacent serve como label |

**Files:**
- `apps/mobile/lib/ui/components/daily_logo.dart` — `ExcludeSemantics` wrapper

---

## 5. CSS Generator

| Aspecto | Antes | Después |
|---|---|---|
| `:root` closing | Nunca cerrado | Cerrado antes de `:root[data-theme="dark"]` |
| Estructura CSS | `:root` anidado con `:root[data-theme="dark"]` | Dos selectores separados |
| Validación | Ninguna | `--check` mode + CI gate |
| Alpha colors | `Color(0x0B4654)` (alpha 00) | `Color(0xFF0B4654)` (alpha FF) |
| Shadow transparent | `Color(0x000000)` | `Color(0x14000000)` (alpha byte 0x14) |

**Files:**
- `tool/generate_design_tokens.dart` — `_generateCssTokens()` refactorizado, alpha bytes corregidos
- `apps/mobile/test/generator_test.dart` — Tests: CSS structure, color opacity, determinism

---

## 6. Gate Script

| Aspecto | Antes | Después |
|---|---|---|
| flutter analyze | `--no-fatal-infos --no-fatal-warnings` | `flutter analyze` (strict) |
| Hash comparison | Dart output vs CSS (incorrecto) | `--check` mode (deterministic) |
| Flags permisivos | 2 flags que ignoran warnings | Ningún flag — estricto |

**Files:**
- `scripts/ci/ui_gate.sh` — `flutter analyze` sin flags, `--check` mode

---

## 7. CI Workflow

| Aspecto | Antes | Después |
|---|---|---|
| checkout | `actions/checkout@v4` | `actions/checkout@b4ffde65...` (SHA pinned) |
| flutter-action | `subosito/flutter-action@v2` | `subosito/flutter-action@b611c0d...` (SHA pinned) |
| flutter analyze | `--no-fatal-infos --no-fatal-warnings` | `flutter analyze` (strict) |
| Generador | Desde `apps/mobile` (ruta incorrecta) | Desde root del repositorio |
| Grep colors | `grep -r "Color(0x0"` | `dart test` (pruebas específicas) |
| Nombre step | "Flutter analyze" | "Flutter analyze (strict)" |

**Files:**
- `.github/workflows/ui-gate.yml` — SHA pinned, strict analyze, generator desde root

---

## 8. Pantallas Refactorizadas

| Pantalla | Theme.of(context) | Daily* | Estados |
|---|---|---|---|
| Login | ✅ | ✅ | loading, error |
| Inicio | ✅ | ✅ | loading, empty, error |
| Cobros (cobros_shell) | ✅ | ✅ | loading, empty |
| Pago | ✅ | ✅ | loading, error |
| Movimientos | ✅ | ✅ | loading, empty |
| Caja | ✅ | ✅ | loading, empty |
| Cierre | ✅ | ✅ | loading, error |
| Historial | ✅ | ✅ | loading, empty, error |
| Más (mas) | ✅ | ✅ | loading |
| Ruta | ✅ | ✅ | loading, empty |
| Hoja Viva | ✅ | ✅ | loading, empty |

**Files:**
- `apps/mobile/lib/screens/inicio_screen.dart`
- `apps/mobile/lib/screens/cobros_shell.dart`
- `apps/mobile/lib/screens/pago_screen.dart`
- `apps/mobile/lib/screens/movimientos_screen.dart`
- `apps/mobile/lib/screens/caja_main_screen.dart`
- `apps/mobile/lib/screens/jornada_cierre_screen.dart`
- `apps/mobile/lib/screens/historial_screen.dart`
- `apps/mobile/lib/screens/mas_screen.dart`
- `apps/mobile/lib/screens/ruta_screen.dart`
- `apps/mobile/lib/screens/hoja_viva_screen.dart`

---

## 9. Componentes

| Componente | Estado |
|---|---|
| DailyLogo | ✅ Implementado + ExcludeSemantics |
| DailyPrimaryButton | ✅ Implementado |
| DailySecondaryButton | ✅ Implementado |
| DailyMetricCard | ✅ Implementado |
| DailyMoneyText | ✅ Implementado |
| DailyStatusBadge | ✅ Implementado |
| DailyOfflineStatus | ✅ Implementado |
| DailyEmptyState | ✅ Implementado |
| DailyErrorState | ✅ Implementado |
| DailyLoadingSkeleton | ✅ Implementado |
| DailyConfirmSheet | ✅ Implementado |
| DailySectionHeader | ✅ Implementado |

---

## 10. Icono Adaptativo

| Aspecto | Antes | Después |
|---|---|---|
| Foreground | N/A | Ruta D vector con nodos y check |
| Background | N/A | `#0B4654` |
| Monochrome | N/A | Ruta D simplificada en blanco |
| Masks | N/A | Círculo, squircle, cuadrado redondeado |
| roundIcon | N/A | `android:roundIcon="@mipmap/ic_launcher_round"` |

**Files:**
- `apps/mobile/android/app/src/main/res/mipmap-anydpi-v26/ic_launcher.xml`
- `apps/mobile/android/app/src/main/res/mipmap-anydpi-v33/ic_launcher.xml`
- `apps/mobile/android/app/src/main/res/mipmap-anydpi-v26/ic_launcher_round.xml`
- `apps/mobile/android/app/src/main/res/mipmap-anydpi-v33/ic_launcher_round.xml`
- `apps/mobile/android/app/src/main/res/drawable/ic_launcher_foreground.xml`
- `apps/mobile/android/app/src/main/res/drawable/ic_launcher_monochrome.xml`
- `apps/mobile/android/app/src/main/res/values/ic_launcher_background.xml`
- `apps/mobile/android/app/src/main/AndroidManifest.xml` (roundIcon attribute)

---

## 11. Pruebas

| Prueba | Estado | Detalle |
|---|---|---|
| flutter analyze | ✅ No issues found! | 0 errors, 0 warnings |
| flutter test | ✅ 68/68 passing | widget + golden + semantics + generator |
| Golden tests | ✅ 31 tests | 26 screens (phone/phone-dark/tablet) + 5 logo |
| Semantics tests | ✅ 21 tests | Login, CobrosShell, Pago, Cierre, Caja, Historial, MainShell |
| Navigation | ✅ 6 tests | CobrosSubNavChip (render, keys, tap) |
| Generator tests | ✅ 8 tests | CSS structure, color opacity, determinism |
| Integration Android | ✅ PASS | 17/17, emulator-5554, API 34 — PDF generado + hash corregido ([evidencia](apps/mobile/docs/ui-audit/evidence/jornada_cierre_integration_test.md)) |

---

## 12. Capturas

68 capturas reales (emulador + web) con manifest SHA-256.

| Tipo | Estado | Detalle |
|---|---|---|
| Before (base 3a1a566) | ✅ 32 | phone/tablet × light/dark × 8 screens |
| After phone-light | ✅ 8 | docs/ui-audit/screenshots/after/phone-light/ |
| After phone-dark | ✅ 8 | docs/ui-audit/screenshots/after/phone-dark/ |
| After tablet-light | ✅ 8 | docs/ui-audit/screenshots/after/tablet-light/ |
| After tablet-dark | ✅ 8 | docs/ui-audit/screenshots/after/tablet-dark/ |
| After web | ✅ 4 | docs/ui-audit/screenshots/after/web/ |
| capture_ui_evidence.sh | ✅ | Parametrizado (mode/variant/profile/theme/web/screen); verify_screen aborta si la firma no está; captura vacía o fallo web abortan |
| manifest.json | ✅ | 68 entradas con SHA-256, commit, device, API, resolución |

Cada captura fue verificada por label de firma (verify_screen) durante la navegación real;
una firma ausente o una captura vacía abortan el script (die), no producen advertencias.

> **Nota evidencia:** la captura `08-historial` muestra una sola fila (`2026-07-31 | Abierta | 0`)
> porque la jornada del día está abierta durante la captura — correcto para el estado de la app
> (la jornada se enriquece con el historial al cerrar días).
>
> **Nota before/theme:** en la versión base (3a1a566) las capturas `07-cierre` y `08-historial`
> son pixel-idénticas en claro y oscuro (mismo SHA-256) — evidencia de que el theming no existía
> en la base. Las capturas *after* difieren light/dark en las 8 pantallas.

---

## 13. README

| Aspecto | Antes | Después |
|---|---|---|
| Estado | "Alpha — Pre-APK" | "Alpha — APK Debug Construido" |
| Capturas | Comentarios HTML | Tablas con imágenes en docs/assets/readme/ (mobile + web) |
| Tests | 7/7 | 68/68 |
| Backend | `flutter pub get` (incorrecto) | `python -m venv` + `pip install -r requirements.txt` + `alembic upgrade head` + `uvicorn` |
| Badges | Inexistentes | Badge UI Gate → ui-gate.yml |
| Roadmap | 2 items completados | 11 items completados (golden, semantics, APK, emulador) |
| Verificación | "APK de prueba física" | APK construido PASS / emulador API 35 PASS / dispositivo físico PENDING |

---

## 14. Graphify

| Campo | Valor |
|---|---|
| SHA | 737371dbb89cdc49ef7961ef43347ca416edbf54d (anterior al código auditado 8cfe225) |
| AST extraction | 26/26 uncached files (100%) |
| Semantic extraction | 77/77 files (deepseek balance insufficient) |
| Status | **PARTIAL** — construido desde 737371d; el código final (8cfe225 → FINAL_HEAD) no fue reindexado por falta de balance del backend |

Graphify **no** se incluye como control PASS: es evidencia auxiliar y su estado es PARTIAL.

---

## 15. SHA History

| SHA | Descripción |
|---|---|
| 3a1a566 | BASE — inicio phase 2 |
| d25d6dd | Phase 2 partial PASS |
| 0fb1447 | Splash Android 12+ |
| 2a47bff | Splash Theme.App.Normal fix |
| 8fa308b | Phase 2 completo: DAILY_DEMO, light/dark, CSS, gate, CI |
| 205b844 | Theme.of(context) en 6 screens |
| 117215a | Semantics + golden tests (18 tests) |
| a703c1b | APK debug 180MB |
| 737371d | Theme.of en todas las pantallas + 26 tests + analyzer clean |
| c5edbd9 | Capturas profesionales, Graphify, audit final + CI/README |
| 45d9bb0 | CI pins SHA + dedupe generator tests |
| 6da01f3 | Golden tests reales + login screen extraction + FFI fixture |
| 48d0220 | Semantics tests reales + bug fixes (chip merge, historial ruta_id) |
| 8f88cfd | Snapshot hash con jornada_id real + PDF tras cierre |
| 8cfe225 | **CODE_SHA** — dark goldens (31 goldens total) |
| d8761aa | Evidencia original (76 capturas, mainshell duplicada) |
| 95b2488 | **EVIDENCE_SHA** — 68 capturas distintas + script autovalidado + manifest |
| fec6fa5 | **GATE_SHA** — fix del paso de generador (flutter test en apps/mobile) |
| 50ef9ac | README honesto (emulador PASS / físico PENDING) |
| 30b2984 | GATE dedupe — sin paso de generador duplicado |
| (AUDIT_SHA) | Este documento — se registra en el commit final |
| (FINAL_HEAD) | HEAD tras cerrar la auditoría |

---

## Veredicto Final

```
UX/UI PREMIUM PRE-APK: PASS
```

| Área | Estado |
|---|---|
| Implementación UX/UI | PASS |
| Golden tests reales | PASS |
| Semantics productivos | PASS |
| Integración Android y PDF | PASS (17/17, emulator-5554, API 34) |
| Capturas before/after | PASS (68, manifest SHA-256, verify_screen estricto) |
| CI (GATE_SHA) | PASS (analyze + test; generador sin duplicados) |
| README | PASS |
| Graphify | PARTIAL (auxiliar, no cuenta para el PASS) |
| Verificación en dispositivo físico | PENDING |

Todos los controles críticos corregidos:
- Splash nativo Android 12+ ✅
- DAILY_DEMO separable ✅
- Login light/dark Theme.of ✅
- Logo ExcludeSemantics ✅
- CSS generator con :root cerrado ✅
- Gate script estricto ✅
- CI workflow SHA-pinned ✅
- README profesional ✅
- Icono adaptativo con roundIcon ✅
- 68/68 tests passing ✅
- flutter analyze: no issues found! ✅
- Pantallas refactorizadas con Theme.of ✅
- Capturas profesionales (68, verify_screen aborta ante firma ausente/captura vacía) ✅
- HEAD == origin/master ✅
- Working tree limpio ✅
