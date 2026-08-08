# DAILY-SYSTEM-CONTEXT-HANDOFF

**Fecha de auditoría:** 2026-08-05
**Auditor:** opencode (big-pickle) — reconstrucción desde copia local
**Método:** lectura de repositorio + evidencia local. Ningún dato asumido de `origin/master` sin verificar en disco.

---

## 1. Identidad y estado Git

| Campo | Valor |
|---|---|
| **Repositorio local** | `/home/jesus/proyectos/daily-system` |
| **Remote** | `https://github.com/karen-claros1212/daily-system.git` |
| **Rama** | `master` |
| **HEAD local** | `486d08b1584684a4328825142209776fce477670` |
| **HEAD remote** | `486d08b` (idéntico) |
| **Ahead / Behind** | `0 / 0` |
| **Estado del árbol** | Limpio (`git status --porcelain` vacío) |
| **Untracked** | Ninguno |

> **Conclusión:** no existe trabajo local sin publicar. `origin/master` está completamente al día.

### Cadena de cierre de la auditoría UX/UI

```
BASE_SHA        3a1a566  (punto de comparación "antes")
CODE_SHA        8cfe225  (código auditado — UI, tests, goldens)
EVIDENCE_SHA    95b2488  (68 capturas + script autovalidado + manifest)
GATE_SHA        fec6fa5 + 30b2984  (corrección y dedupe del paso generador)
AUDIT_CONTENT   10ea745  (contenido sustantivo del audit)
FINAL_HEAD      72f6ac2  (último commit auditado)
486d08b         (commits posteriores documentales, no alteran el contenido auditado)
```

---

## 2. ⚠️ Documentación desactualizada — verificar, no confiar

| Documento | Dice | Realidad verificada |
|---|---|---|
| `docs/STATUS.md` | HEAD `b6d48bb`, 37 commits, M3.6.6-F, 138/138 tests | HEAD real `486d08b` con toda la cadena de auditoría UI posterior. **STALE** |
| `docs/GRAPHIFY-CURRENT.md` | Grafo PARTIAL, built de `737371d`, deepseek sin saldo | `graphify-out/GRAPH_REPORT.md` reporta built de `ff889a80`, 63 nodos / 49 aristas / 92% EXTRACTED. **STALE** (dos SHAs distintos, ninguno = HEAD) |
| `docs/IMPLEMENTATION-PLAN.md` | M0-M3 ✅ (42/54, 78%), M4-M6 ⬜ | Coherente con el código. Vigente en contenido |
| `README.md` | Alpha, APK debug, emulador PASS, físico PENDING | Coherente. Verifica APKs en disco (sección 4) |

---

## 3. Arquitectura real

```
daily-system/
├── apps/
│   ├── api/                # Backend FastAPI (Python)
│   │   ├── src/
│   │   │   ├── main.py         # FastAPI app, CORS, 11 routers incluidos
│   │   │   ├── auth/           # Autenticación por sesión
│   │   │   ├── models/         # SQLAlchemy (9 tablas)
│   │   │   ├── schemas/        # Pydantic
│   │   │   ├── routes/         # cliente, credito, dispositivo, hoja_viva,
│   │   │   │                   #   inversionista, jornada, movimiento, negocio,
│   │   │   │                   #   pago, ruta
│   │   │   ├── services/       # calculation, hoja_viva, jornada, movimiento, payment
│   │   │   └── tests/          # 8 archivos: test_api, test_calculations, test_m1,
│   │   │                       #   test_m1_advanced, test_m1_gate, test_m2, test_m3
│   │   ├── migrations/         # Alembic: init, m2_apertura_idempotency,
│   │   │                       #   m2_jornada_caja, m3_dispositivo
│   │   ├── alembic.ini
│   │   └── requirements.txt
│   ├── mobile/             # Flutter Offline Alpha
│   │   ├── lib/
│   │   │   ├── main.dart       # DAILY_DEMO flag, Theme.of(context)
│   │   │   ├── database/       # SQLite: tables, migrations v2/v3/v4, seed
│   │   │   ├── domain/         # Tipos financieros, excepciones (JornadaGuard, etc.)
│   │   │   ├── models/  navigation.dart  config.dart
│   │   │   ├── screens/        # 13 pantallas (login, inicio, cobros, pago, caja,
│   │   │   │                   #   cierre, movimientos, historial, ruta, mas, ...)
│   │   │   ├── services/  shell/  theme/  ui/  utils/  widgets/
│   │   ├── test/              # 10 archivos + goldens/ + helpers/fixture.dart
│   │   ├── integration_test/jornada_cierre_test.dart
│   │   └── android/  ios/  web/  linux/  macos/  windows/  build/
│   └── web/                # ⚠️ DIRECTORIO VACÍO (solo src/ sin archivos trackeados)
├── design/
│   ├── brand/BRAND-RATIONALE.md
│   ├── tokens/daily-system.tokens.json   # fuente única → Dart + CSS
│   └── prototypes/web/     # Prototipo estático: index, cartera, caja, reportes, styles.css
├── docs/                  # maestro v1.3, protocolos, ui-audit, web blueprint, assets
├── scripts/
│   ├── ci/ui_gate.sh
│   └── android/           # capture_ui_evidence.sh, ensure-emulator-awake.sh
├── tool/generate_design_tokens.dart
├── infra/                # docker-compose.yml, .env.example, init.sql, docs/
├── .github/workflows/    # SOLO ui-gate.yml
├── graphify-out/         # grafo 5.6MB (gitignored)
└── tests/                # VACÍO (sin archivos)
```

### Notas de arquitectura

- **Backend:** FastAPI + SQLAlchemy + Alembic, CORS configurable vía `CORS_ALLOWED_ORIGINS`, autenticación por sesión, idempotencia en pagos y apertura de jornada, snapshot de jornada con hash SHA-256 reproducible, PDF recuperable.
- **Mobile:** offline-first con SQLite versionado (migraciones v2/v3/v4), dominio financiero tipado con excepciones, Material 3 Expressive, tokens de diseño generados determinísticamente.
- **Web productivo:** `apps/web/` está **vacío** — contradice lo que sugiere `docs/IMPLEMENTATION-PLAN.md` (M3.4 "Panel inversionista web" → `apps/web/src/app/inversionista/`) y `inversionista.py` en el backend. Solo existe el prototipo estático en `design/prototypes/web/`. El panel productivo está **planificado, no implementado**.
- **CI:** únicamente `.github/workflows/ui-gate.yml` (checkout → flutter-action 3.44.0 → pub get → token check → flutter analyze → flutter test). **No hay CI de backend** (ni pytest ni alembic check en GitHub Actions).
- **`tests/` (raíz):** vacío. Los tests viven en `apps/api/src/tests/` y `apps/mobile/test/`.

---

## 4. Evidencia de UI/UX y builds

### APKs (ignorados por git — no versionados)

| Artefacto | Tamaño | Nota |
|---|---|---|
| `app-debug.apk` | 227,558,643 B | Build principal; sha1 `e01607dc4baf65a3c46cd0e70c719312b2eebf84` |
| `app-default-debug.apk` | 227,558,643 B | Idéntico a app-debug |
| `app-daily-demo-debug.apk` | 227,558,697 B | Variante demo |
| `app-before-debug.apk` | 162,114,254 B | Build "antes" (pre-refactor) |

Todos en `apps/mobile/build/app/outputs/flutter-apk/`, generados 2026-07-31 21:07.

### Capturas (manifest SHA-256)

- `docs/ui-audit/screenshots/manifest.json` — 68 capturas `after`/`before`
- Emulador `sdk_gphone64_x86_64`, **API 35**, resoluciones 412×915 (phone) y 840×900 (tablet), temas light/dark + prototipo web
- Commits referenciados: after `dbb5ae2`, before `3a1a566`
- Despliegue en `after/` y `before/` con subcarpetas `phone-dark`, `phone-light`, `tablet-dark`, `tablet-light`, `web`

### Estado de verificación (según README/audit)

| Verificación | Estado |
|---|---|
| APK debug construido | ✅ PASS |
| Verificado en emulador API 35 | ✅ PASS |
| Verificado en dispositivo físico | ⏳ PENDING |
| Tests móviles | README/audit: 68/68 — **no re-ejecutados por este auditor** |
| Analyzer | README/audit: "No issues found!" — **no re-ejecutado** |
| Backend pytest | audit M2: 138/138 (STATUS.md, stale) — **no re-ejecutado** |

---

## 5. Herramientas y configuración local

- **Graphify:** CLI `graphify` 0.9.26 (uv tool `graphifyy`), MCP configurado en `opencode.json` de Daily System → `graphify.serve graphify-out/graph.json`, habilitado. Grafo actual: 63 nodos / 49 aristas / 22 comunidades / PARTIAL (deepseek sin saldo; 3 archivos Contents.json sin nodos; falta `tree_sitter_sql`).
- **Engram:** protocolo obligatorio `project: "daily-system"` (no auto-detect), topic_keys estables definidos en `docs/ENGRAM-PROTOCOL.md`.
- **Skills (fuera del repo):** `hallmark` (nutlope) + 9 skills de Emil Kowalski instalados en `~/.openclaw/workspace/.agents/skills/` con symlinks en `~/.config/opencode/skills/`. No están versionados en el repo.

---

## 6. Estado del producto (funcional)

**Implementado:** autenticación de cobrador, negocios/ rutas/ clientes, crédito (cuota, mora, recargo), hoja viva del día, pagos parciales y reversión, jornada de caja (apertura, movimientos, cierre, anulación), snapshot con hash reproducible, PDF de cierre, colas de sincronización, suscripciones por plan (free 1 ruta/100 clientes, básico 5/500, pro ilimitado), Flutter offline con SQLite, Material 3 Expressive, splash nativo Android 12+, icono adaptable, tema claro/oscuro, tokens JSON → Dart + CSS, UI Gate CI estricto. **Paridad financiera backend–móvil (Bloque 5): PASS.**

**Desactualizado (reconciliado 2026-08-06):** la afirmación histórica de "bot Telegram cobrador + inversionista" **NO corresponde a artefactos existentes** en el árbol real (`apps/telegram-bot/` no existe). Un bot futuro es **exclusivamente administrativo**; bot en móvil: **PROHIBIDO**. Ver nota de reconciliación en `docs/IMPLEMENTATION-PLAN.md` y `docs/STATUS.md`.

**Pendiente:** M4 OCR, M5 score/chatbot/predicción/alertas, M6 producción (compose prod, nginx, SSL, monitoreo, backups, logs), verificación en dispositivo físico, **web productiva** (`apps/web` vacía — solo prototipo estático `design/prototypes/web/`), activación/sincronización móvil productivas.

### ESTADO WEB OFICIAL (2026-08-06)

| Componente | Estado |
|---|---|
| Web productiva (`apps/web`) | **PENDIENTE** (carpeta vacía) |
| Prototipo web HTML/CSS | MOCK visual (`design/prototypes/web/`) |
| Blueprint web (`docs/web/WEB-UI-BLUEPRINT.md`) | IMPLEMENTADO |
| Stack web | **APROBADO**: Next.js 14 + TypeScript + Tailwind CSS + shadcn/ui + Playwright E2E |
| Autenticación web | PENDIENTE |
| Integración API web | PENDIENTE |
| Bot administrativo | FUTURO |
| Bot en móvil | PROHIBIDO |

---

## 7. Próximos pasos para el agente receptor

1. **Re-ejecutar gates reales** antes de declarar estado:
   - `scripts/ci/ui_gate.sh` (tokens + analyze + flutter test)
   - `cd apps/api && pytest src/tests/` y `alembic check` (con PostgreSQL de `infra/docker-compose.yml` si aplica)
   - Reportar números reales (README/audit declaran 68/68 mobile, 138/138 backend, pero son afirmaciones documentales).
2. **Actualizar documentación stale** cuando corresponda: `docs/STATUS.md`, `docs/GRAPHIFY-CURRENT.md`.
3. **Web (decidido 2026-08-06):** la web productiva **SÍ entra en alcance** y se creará en `apps/web` con el stack aprobado (Next.js 14 + TypeScript + Tailwind CSS + shadcn/ui + Playwright). El prototipo estático queda como especificación visual (tokens, disposición, componentes, WCAG). Reutilizar sus tokens, no su arquitectura.
4. **M4-M6** son los hitos abiertos; M4 OCR depende de `ocr_service.py` (no existe en `services/`).

---

## 8. Notas de seguridad

- No se expusieron credenciales, tokens ni claves durante la auditoría.
- `infra/.env.example` es solo plantilla; `.env*` está gitignored.
- El contenido de este documento es una fotografía del estado al 2026-08-05 y no sustituye la ejecución de los gates reales.

---

## 9. LÍNEA BASE VERIFICADA — ejecución real (2026-08-05)

Fase exclusivamente de verificación, no destructiva, sobre HEAD `486d08b1`.
Protocolo de 12 pasos aplicado. Sin correcciones, sin refactor, sin commits, sin push.
Solo `graphify-out/` (ignorado) y este archivo (untracked) fueron tocados.

### Fase A — Git

| Comando | Resultado |
|---|---|
| `git fetch origin --prune` | OK |
| `git status --short` | `?? DAILY-SYSTEM-CONTEXT-HANDOFF.md` |
| `git status --branch --short` | `## master...origin/master` |
| `git rev-parse HEAD` | `486d08b1584684a4328825142209776fce477670` |
| `git rev-parse origin/master` | idéntico |
| `git rev-list --left-right --count HEAD...origin/master` | `0	0` |
| `git log -1 --format=fuller` | author vanessaclaros553-ui, 2026-07-31 23:13 -0500 |

**Veredicto:** sincronizado, sin divergencia, sin código modificado. PASS.

### Fase B — Móvil (verificado, no documental)

| Comando | Resultado | Exit | Tiempo |
|---|---|---|---|
| `flutter --version` | 3.44.0 stable, Dart 3.12.0 | 0 | 4s |
| `flutter pub deps --style=compact` | Sin PowerSync (sqflite/shared_preferences/pdf/printing/share_plus/uuid/crypto) | 0 | <1s |
| `flutter analyze` | No issues found! | 0 | 2s |
| `flutter test` | **68/68 passing**, 0 skipped, 0 fail | 0 | 6s |
| `scripts/ci/ui_gate.sh` | ALL PASSED (tokens OK + analyze + 68/68) | 0 | 10s |

**Advertencia única (no bloqueante):** faltan herramientas GTK para build Linux desktop (irrelevante para tests).
**Confirmación clave:** `flutter pub deps` confirma que PowerSync NO está en el árbol de dependencias real.

### Fase C — Backend (verificado)

| Comando | Resultado | Exit |
|---|---|---|
| `pytest src/tests/ -q` | **137 passed, 1 failed** | 1 |
| `alembic heads` | `m3_dispositivo (head)` | 0 |
| `alembic current` (contra PG real) | `m3_dispositivo (head)` | 0 |
| `alembic check` | **FAILED** — drift modelos vs migraciones | 255 |

**Cifra documental "138/138" NO se reproduce → 137/138.**

Fallo único (`test_m3.py::TestDispositivo::test_registrar_revocado_se_reactiva_con_admin`):
- Causa inmediata: `AttributeError: 'float' object has no attribute 'replace'` en `_python_UUID` al leer una fila de `dispositivo` en `revocar_dispositivo` (`dispositivo_service.py:145`) — valor UUID devuelto como `float` por SQLite.
- **Depende del orden de la suite:** pasa 3/3 en aislamiento; falla solo en ejecución completa → sospecha de aislamiento/estado compartido de sesión en conftest (rollback de transacción anidado sobre SQLite in-memory) o interacción con modelos `UUID` de dialecto PostgreSQL sobre SQLite.
- NO corregido (fase de verificación).

`alembic check` (drift, NO corregido):
- `jornada.cierre_snapshot_json`: modelos piden `JSON()`, BD tiene `JSONB`.
- FKs `movimiento_caja.{credito_id,ajuste_de_movimiento_id,renovacion_id}` y `ruta.cobrador_id`: modelos y migraciones difieren en nombre/ondelete.

Infraestructura usada:
- Contenedor `cobro-postgres` (postgres:18.4) ya existía (Exited); se arrancó con `docker start` (sin recrear, sin `down -v`, sin tocar volúmenes).
- Credenciales reales leídas del contenedor: `POSTGRES_USER=cobro POSTGRES_PASSWORD=cobro_secret POSTGRES_DB=cobro` (puerto 7103). **Divergencia documentada:** `.env.example`/compose usan `daily/daily_dev/daily`; el contenedor real usa `cobro/*`.
- El compose marca `version: "3.9"` (obsoleto, warning) y su healthcheck usa `pg_isready -U cobro -d cobro` — no coincide con sus propios defaults de env.

### Fase D — Graphify (reconstruido en HEAD)

| ítem | Antes | Después |
|---|---|---|
| SHA de construcción | `ff889a80` (stale) | `486d08b1` (HEAD) |
| Nodos / aristas / comunidades | 63 / 49 / 22 | **2504 / 4062 / 173** |
| Extracción | 92% EXTRACTED | 95% EXTRACTED · 5% INFERRED (191 aristas, conf 0.53) |
| Costo LLM | — | **0 tokens** (AST local) |
| `tree_sitter_sql` | ausente | instalado SOLO en env aislado `graphifyy` (uv tool, no global) |
| Archivos de corpus | — | 174 files · ~201,365 words |

Comandos usados: `graphify update .` (re-extract local, sin LLM). Solo escribió en `graphify-out/` (gitignored). Respaldo del grafo anterior en `/tmp/opencode/graphify-out-backup-486d08b`.

### Estado final tras línea base

- `git status --short` → solo `?? DAILY-SYSTEM-CONTEXT-HANDOFF.md` (untracked, preservado).
- Cero archivos trackeados modificados.
- Contenedor `cobro-postgres` quedó **activo** (se arrancó para Alembic; decidir si detener en siguiente sesión).

### Deuda técnica confirmada (candidatos a corregir en fase posterior, con permiso)

1. `alembic check` FAIL → drift `JSON vs JSONB` + FKs (requiere nueva migración o ajuste de modelos).
2. Test backend 1/138 orden-dependiente → revisar aislamiento en `conftest.py`.
3. Credenciales divergentes contenedor vs `.env.example`.
4. `docs/STATUS.md`, `docs/GRAPHIFY-CURRENT.md` stale.
5. `apps/web/` vacío vs doc M3.4.

---

## 3. Sesión 2026-08-06 — Bloques 1-3 del Archivo Maestro

> Ejecución según `DAILY-SYSTEM-ARCHIVO-MAESTRO-CONTINUIDAD-OPENCODE.md` (untracked, raíz). Estado completo en la sección 8 de ese archivo.

### Bloque 1 — Baseline → PASS

- HEAD local = remoto = `486d08b1584684a4328825142209776fce477670`; divergencia 0/0.
- Backend: `python3 -m pytest src/tests/ -q` → **138 passed, 1 warning**.
- Alembic contra PG real (puerto 7103): `current` = `m3_dispositivo (head)`, una cabeza, `check` FAIL (drift documentado).
- Móvil: `flutter analyze` No issues; `flutter test` 68/68 PASS (goldens incluidos).

### Bloque 2 — Flake UUID → PASS (opción A autorizada)

- Causa raíz: `dispositivo_service.py:81` → `UUID(int=hash(huella + str(negocio_id)) % 2**128)`. `hash()` aleatorio por proceso; hex solo-dígitos (p≈0.045%) → SQLite afinidad NUMERIC → int/float → `uuid.UUID(float)` → `AttributeError: 'float' object has no attribute 'replace'` (reproducido empíricamente).
- Fix A: `apps/api/src/tests/conftest.py` — `@compiles(UUID, "sqlite")` → `CHAR(32)` (solo dialecto sqlite; PostgreSQL sigue `UUID`). No se tocaron modelos productivos, ni `sqlalchemy.Uuid`, ni `hash()`→`uuid5`.
- Test determinista: `test_m3.py::test_dispositivo_id_hex_solo_digitos_sobrevive_sqlite` (monkeypatch `builtins.hash` → `0x00000000000000009999999999999999`). Sin el fix falla con el `AttributeError` exacto; con el fix, round-trip devuelve `UUID`.
- Suite: **139/139 en 5 procesos limpios**.

### Bloque 3 — Drift Alembic → PASS

- Clasificación: `cierre_snapshot_json` JSONB vs JSON → bug del modelo (BD autoridad); FKs `movimiento_caja` nombradas `SET NULL` vs anónimas → bug del modelo; `ruta.cobrador_id` columna sin FK → bug de migración.
- Cambios: `models/__init__.py` (`JSONB().with_variant(JSON(), "sqlite")`, FKs con `name=`+`SET NULL`, `name="fk_ruta_cobrador"`); nueva migración `m4_ruta_cobrador_fk.py` (reversible, no reescribió init).
- Evidencia: `alembic check` limpio; upgrade m3→m4; downgrade→m3 (drift esperado); upgrade; BD scratch base vacía→head→downgrade→base→upgrade→head; pytest 139/139; 0 huérfanos en cobrador_id.
- Política de borrado confirmada: sin `ON DELETE` en `ruta.cobrador_id` → los cobradores se desactivan (`activo=0`) o se reasignan, no se borran físicamente.

### Estado Git al cierre (sin commit/push)

```
 M apps/api/src/models/__init__.py
 M apps/api/src/tests/conftest.py
 M apps/api/src/tests/test_m3.py
?? DAILY-SYSTEM-ARCHIVO-MAESTRO-CONTINUIDAD-OPENCODE.md
?? DAILY-SYSTEM-CONTEXT-HANDOFF.md
?? DAILY-SYSTEM-CONTEXTO-MAESTRO-CONSOLIDADO-2026-08-06.md
?? apps/api/migrations/versions/m4_ruta_cobrador_fk.py
```

### Siguiente paso

→ **Bloque 4 — Sellar aislamiento multirruta.** Cerrar huecos backend: `GET /api/jornadas/active` (`jornada.py:89-104`), `GET /api/movimientos/{id}` (`movimiento_service.py:317-329`), `GET /api/rutas/{ruta_id}` (`ruta.py:60-72`), `POST /api/pagos` validar `jornada_id` (`payment_service.py:162`), `Cliente` con `ruta_id` (`cliente.py:50-58`). Documentar 1/7/8 como dependientes de auth real (Bloque 7). Fixture dinámico R1-R4 + 5ª ruta; verificar alcance por ruta en móvil.

### Bloque 4 — Sellado de aislamiento multirruta → PARCIAL (backend PASS; móvil productivo PENDIENTE; activación PENDIENTE)

> **Dictamen de auditoría externa (2026-08-06):** Aislamiento backend PASS (no deshacer); aislamiento móvil productivo PENDIENTE; activación administrativa PENDIENTE. Autoridades separadas: `ruta.cobrador_id` (asignación) + `dispositivo.usuario_id` (celular del cobrador); el servidor deriva el alcance; el celular NO escoge ni descarga todas las rutas. Prohibido IMEI/Android ID/huella cliente/SharedPreferences como autenticador. Orden: paridad financiera → contrato activación → auth+vinculación → bootstrap ruta única → sync offline → panel admin → resto panel → bot. Sin commit/push/deploy/reinicio.

**Huecos backend cerrados (5):**
- `payment_service.py` — `register_payment` valida `jornada_id` del body (404 jornada inexistente del negocio), `jornada.ruta_id == credito.ruta_id` (403 `PaymentRouteError`) y `ctx.has_route` si cobrador (403).
- `movimiento_service.py` — `get_movimiento` filtra `negocio_id` y, si cobrador, `join(Jornada)` filtrando `Jornada.ruta_id == ctx.route_id`.
- `routes/jornada.py` — jornada activa de otra ruta → 404 "No hay jornada activa para esta ruta" (no revela existencia).
- `routes/ruta.py` — ruta de otra ruta → 404 "Ruta no encontrada".
- `routes/cliente.py` — `listar_clientes` cobrador → `join(Credito)` filtrando `ruta_id` + `.distinct()` (Cliente no tiene `ruta_id`; alcance derivado de créditos).
- `test_m1_gate.py::test_payment_saves_traceability_fields` — ahora crea `Jornada` real (el pago con `jornada_id` ficticio ya no pasa).

**Prueba multirruta nueva — `apps/api/src/tests/test_m4.py` (PASS, 528 líneas, 9 tests):**
`test_r1_r2_jornadas_simultaneas`, `test_operar_r2_no_altera_r1`, `test_cobrador_r1_no_lee_r2`, `test_cobrador_r1_no_modifica_r2`, `test_admin_accede_a_todas`, `test_snapshot_por_ruta_no_se_cruzan`, `test_opening_carry_solo_misma_ruta`, `test_opening_carry_sin_jornada_previa_misma_ruta`, `test_quinta_ruta_sin_cambio_de_codigo`. Fixture: 1 negocio, 1 admin, varios cobradores, R1–R4 + R5/R6 dinámicas, jornadas simultáneas, pagos/movimientos/caja/cierre por ruta. Política 403/404 sin revelar existencia de otra ruta.

**Revisión móvil (documental, código móvil NO modificado):**
- Scoped OK: HojaVivaService (ruta_id), JornadaService (abrir/getAbierta/historial por ruta), CajaService/Movimientos/Caja/JornadaCierre (por jornada), PdfService (snapshot por jornada con hash), PagoService (transacciones + JornadaGuard).
- Huecos client-side documentados (pendiente Bloque 7, no resueltos): `pago_screen.dart:37-45` créditos ACTIVO sin `ruta_id` (PagoScreen no recibe rutaId); `caja_main_screen.dart:34-36` e `inicio_screen.dart:59-66` jornada abierta sin filtro de ruta (jornadas simultáneas pueden cruzar); `cobros_shell.dart:207-211` y legado `ruta_screen.dart:50` listan rutas activas sin `cobrador_id`; `pago_service.dart` no valida localmente `credito.ruta_id == jornada.ruta_id`. Legado huérfano `home_screen.dart`/`ruta_screen.dart` no referenciados por `main.dart` (flujo real: MainShell → InicioScreen/CobrosShell).

**Documentado, no resuelto (depende de auth real Bloque 7):** `routes/negocio.py` GETs sin auth; hoja_viva sin restricción de rol (cualquier rol lee); creación/edición de rutas/clientes/dispositivos sin gate explícito de rol admin en todos los caminos; inversión: ya valida rol+suscripción, sin PII.

**Evidencia:** `python3 -m pytest src/tests/ -q` → **148 passed, 1 warning** (estable en repeticiones); alembic `current`/`heads` = `m4_ruta_cobrador_fk`, `alembic check` → No new upgrade operations detected. Gates móviles: `flutter analyze` → No issues found!; `flutter test` → 68/68 PASS; `scripts/ci/ui_gate.sh` → UI Gate: ALL PASSED.

**Estado Git (sin commit/push):**
```
 M apps/api/src/models/__init__.py
 M apps/api/src/routes/cliente.py
 M apps/api/src/routes/jornada.py
 M apps/api/src/routes/ruta.py
 M apps/api/src/services/movimiento_service.py
 M apps/api/src/services/payment_service.py
 M apps/api/src/tests/conftest.py
 M apps/api/src/tests/test_m1_gate.py
 M apps/api/src/tests/test_m3.py
?? DAILY-SYSTEM-ARCHIVO-MAESTRO-CONTINUIDAD-OPENCODE.md
?? DAILY-SYSTEM-CONTEXT-HANDOFF.md
?? DAILY-SYSTEM-CONTEXTO-MAESTRO-CONSOLIDADO-2026-08-06.md
?? apps/api/migrations/versions/m4_ruta_cobrador_fk.py
?? apps/api/src/tests/test_m4.py
```

### Siguiente paso

→ **Bloque 5 — Paridad financiera backend-móvil.** Construir la matriz de casos sintéticos (pago exacto/parcial/varias cuotas/pico, reversión, créditos diario/semanal/quincenal/cuota única, jornada con todos los flujos, cierre con diferencia, carry al día siguiente, dos rutas) y comparar `resultado backend == resultado móvil` para cada regla. Corregir solo divergencias demostradas; una única definición por regla. Los huecos client-side del Bloque 4 quedan como dependientes de Bloque 7 salvo que la matriz demuestre una divergencia financiera. **Límite del dictamen:** en Bloque 5 NO tocar selección de rutas, login demo, SharedPreferences de alcance, descarga de datos, activación ni revocación (esperan el contrato de activación).

→ **Entregable previo a código (obligatorio, pendiente):** auditar el sistema Dispositivo existente (`models/__init__.py` L488-519, `migrations/versions/m3_dispositivo.py`, `services/dispositivo_service.py`, `routes/dispositivo.py`, `schemas/__init__.py` L349-371, auth query-param dev-only) y entregar: inventario real, matriz campo/función/requisito cubierto/ausente/cambio mínimo/impacto de migración, diagrama de estados (PENDING_ACTIVATION→ACTIVE→REVOKED|REPLACED|EXPIRED), contrato de endpoints, propuesta de migración reversible, política de revocación/reemplazo/reasignación (sin borrar historia; bloqueo con jornada abierta/cola pendiente; un cobrador = un dispositivo ACTIVE; una ruta = un cobrador activo), tratamiento de eventos offline, 15 pruebas obligatorias, riesgos de compatibilidad, archivos exactos a cambiar, confirmación de que NO se modifica la UI aprobada. Sin tocar modelos/migraciones hasta aprobación.

---

## 4. Dictamen 2026-08-06 (revisión de desbloqueo) — Bloque 5 AUTORIZADO

> Decisión del auditor: **continuar inmediatamente con el Bloque 5 (paridad financiera backend–móvil)**. No esperar otra revisión del contrato de activación. La revisión 4 del contrato queda como **diseño documental en curso, sin autorización para convertirla en código**. **[SUPERADA parcialmente 2026-08-06:** la revisión 4 quedó **cerrada como PASS DOCUMENTAL** (especificación congelada; serialización resuelta: **JCS RFC 8785**, CBOR canónico descartado, sección 13 del documento). La "sin autorización para convertirla en código" sigue vigente: no hay implementación ni Bloque 6.]

### Estado consolidado vigente

| Área | Estado |
|---|---|
| Bloque 1 — baseline | PASS reportado |
| Bloque 2 — flake UUID | PASS reportado |
| Bloque 3 — Alembic | PASS reportado |
| Bloque 4 — aislamiento backend | PASS reportado |
| Bloque 4 — aislamiento móvil productivo | PENDIENTE |
| Contrato de activación | Revisión 4 documental, **no implementable aún** |
| **Bloque 5 — paridad financiera** | **AUTORIZADO AHORA** |
| Web administrativa | Puede continuar sobre la aplicación local existente |
| Autenticación, bootstrap y sincronización | **No implementar todavía** |

### Corrección sobre propuestas anteriores

EC P-256, SPKI, JCS/CBOR, MethodChannel, librerías Flutter candidatas, estructura final de tokens, nombres exactos de migraciones y numeración nueva de bloques quedan como **propuestas, no decisiones definitivas**. Nada se implementará solo por aparecer en la auditoría; primero se compara con el código local, la web existente y la arquitectura ya construida.

**[SUPERADA parcialmente 2026-08-06 (revisión 4 → PASS DOCUMENTAL):** la serialización determinista dejó de ser propuesta y quedó **resuelta y congelada**: **JCS (RFC 8785)** único y obligatorio, **CBOR canónico descartado**, perfil canónico mínimo y vector de prueba en §13 del documento de auditoría. Siguen como propuestas/decisiones de su fase: EC P-256 y SPKI (formato de clave de identidad), MethodChannel vs librerías Flutter, estructura de tokens, nombres de migraciones y numeración de bloques.]

### Alcance exclusivo del Bloque 5

Matriz determinística backend vs móvil sobre los mismos casos y datos:
pago normal, pago parcial, pago mayor que una cuota, pago de varias cuotas, pico, reverso parcial, reverso total, mora, vence hoy, cuotas pagadas, saldo contractual, saldo neto, renovación, opening_carry, cierre, snapshot financiero.

- Backend = **autoridad financiera**.
- Corregir únicamente divergencias demostradas. No reescribir lógica completa. No introducir otra calculadora financiera paralela. No cambiar contratos ya correctos. No debilitar pruebas. No regenerar goldens sin autorización separada. No modificar la UI salvo que una cifra legítimamente corregida lo exija → en ese caso detenerse y reportar.
- Mantener compatibilidad con Bloques 2, 3 y 4.
- Clasificar cada diferencia como: **BUG BACKEND / BUG MÓVIL / DIFERENCIA DE REPRESENTACIÓN / REGLA NO DEFINIDA / SIN DIVERGENCIA**.
- No alterar una regla cuando la matriz muestre que ambos lados ya coinciden.

### Congelado durante Bloque 5

activación de dispositivos, challenge-response, Keystore, huella/public_key, tokens, JWT/OAuth/PKCE, bootstrap, sincronización HTTP, sync_queue, jsonEncode, selección de ruta, login demo, revocación, reasignación, dependencias Flutter de seguridad o red.

### Web administrativa (paralelo permitido, módulos independientes)

rutas, cobradores, clientes, créditos, cartera, jornadas, caja, reportes, estructura UI, accesibilidad, tests, build. **No** crear otra aplicación web, otro cliente API, otro sistema de estado ni otro modelo de rutas. **No implementar todavía en la web:** generación real de activaciones, QR productivo, canje, revocación efectiva, reemplazo, bootstrap móvil.

### Evidencia del Bloque 5 (entregables)

1. matriz de casos con entradas y resultados esperados;
2. resultado backend;
3. resultado móvil;
4. divergencias iniciales;
5. cambios mínimos realizados;
6. pruebas nuevas;
7. suite backend completa;
8. `flutter analyze`;
9. `flutter test`;
10. UI Gate;
11. `git status --short`;
12. `git diff --check`;
13. riesgos pendientes.

> **BLOQUE 5: PASS (2026-08-06).** Cierre en `DAILY-SYSTEM-BLOQUE5-MATRIZ-PARIDAD.md` §10:
> paridad móvil 14/14 · móvil completo 82/82 · backend 166/166 · `flutter analyze` limpio · UI Gate PASS · `git diff --check` OK.
> Goldens regenerados (autorizados, solo CobrosShell/Hoja Viva): `screen_cobros.png`, `screen_cobros_dark.png`, `screen_cobros_tablet.png`.
> Decisión de UI: resumen de hoja viva con chip único `GRIS: N` (semáforo GRIS temporal hasta `score_snapshot` real; sin clasificación VERDE/AMARILLO/ROJO, sin score ni reglas de riesgo en este bloque).
> Fixes aplicados: `reverse_payment` hereda `jornada_id`; `calcular_caja` acepta `entregas`/`recibidos`; móvil `hoja_viva_service.dart` (pico/cuotas_pagadas/mora_legacy/semáforo GRIS/reportDate) y `jornada_service.dart` (carry de apertura + `sobrante_manana`).
> Riesgos pendientes: 3 goldens más no tocados; C-13 (renovación móvil), C-15 (DC/vence hoy), C-16 (hash snapshot) son REGLA NO DEFINIDA/DIFERENCIA DE REPRESENTACIÓN → dependen de bloques futuros (sincronización/renovación). Sin commit/push/deploy/reinicio.

## 5. Sesión 2026-08-06 — Bloque 6: Contrato de activación (backend)

> **BLOQUE 6: PASS (2026-08-06).** Contrato de activación Revisión 4 implementado y verificado en backend.
> Backend completo: **181 passed / 1 skipped** (skip = concurrencia PG en suite SQLite; evidencia PG real por script). `alembic check` limpio. `git diff --check` OK. Sin commit/push/deploy.

**Entregables §17:**

1. **Migración `m5_dispositivo_activacion`** (reversible, down_revision `m4_ruta_cobrador_fk`): columnas `estado`, `public_key`, `public_key_hash`, `algoritmo_clave` en `dispositivo`; `huella`→nullable; backfill `estado`; índices parciales únicos `uq_dispositivo_public_key_hash`, `uq_dispositivo_activo_cobrador`, `uq_ruta_activa_cobrador`; tablas `codigo_activacion` e `intento_activacion`; checks `check_dispositivo_estado`, `check_codigo_activacion_estado`. Aplicada a dev (`cobro`@localhost:7103, current=m5) y verificada en scratch `cobro_scratch_b6` (upgrade→downgrade→re-upgrade→drop) y en scratch PG nuevo `cobro_scratch_b6_pg` (cadena m2→m5 desde cero, drop final).
2. **Modelos alineados** (`src/models/__init__.py`): `Index` parciales declarados con `postgresql_where` + `sqlite_where` → `alembic check` = "No new upgrade operations detected".
3. **JCS §13.4** (`src/services/jcs.py`): vector exacto 285 bytes verificado byte a byte; `format_rfc3339_seconds` maneja datetimes naive (SQLite).
4. **Servicio activación** (`src/services/activacion_service.py`): `generar_codigo`, `desafio` (no consume), `canjear` (SELECT FOR UPDATE, idempotente, `MAX_INTENTOS_FALLIDOS=5`→EXPIRED), `bootstrappear` (solo dispositivo ACTIVE, 401 `BOOTSTRAP_INVALIDA`). Helper `_aware_utc()` para SQLite.
5. **Reemplazo de dispositivo** (contrato §4): `reemplazar_dispositivo` + `POST /api/dispositivos/{id}/reemplazar` (solo ADMINISTRADOR, 403 para cobrador). D1→REPLACED, nuevo código emitido para el cobrador.
6. **Rutas** (`src/routes/activacion.py`): `POST /api/activaciones/codigos` (admin), `POST /api/activaciones/desafios`, `POST /api/activaciones/canje`, `GET /api/mobile/bootstrap`. Registradas en `main.py`.
7. **Pruebas nuevas** `src/tests/test_m5_activacion.py` (19 passed + 1 skip): vector JCS; flujo completo R1 (bootstrap solo R1, no ve R2, `usuario_id`=cobrador); prueba de posesión; desafío no consume; vencido/usado/agotado; revocar invalida bootstrap; reemplazo D1→D2 conserva historia; body público prohíbe campos privados; gates admin (codigos/reemplazar 403, cobrador no registra dispositivo); **casos A-D de idempotencia/no-herencia** (replay exacto idempotente; firma distinta rechazada sin herencia; dos intentos mismo código → el 2º NO idempotente; un ACTIVE por cobrador); canje concurrente (skip SQLite, semántica idempotente: 1 consumo real + 1 idempotente → 1 dispositivo).
8. **Defectos §10 corregidos**: registro de dispositivo admin-only (403); device id = uuid4 (no hash); aislación multirruta (bootstrap devuelve solo ruta activa del cobrador).
9. **Evidencia PG real**: scripts contra `cobro_scratch_b6_pg` (creada→probada→drop): concurrencia 2 threads con barrera → 1 dispositivo, 2º canje idempotente con el mismo `dispositivo_id`; **casos A-D verificados** (replay idempotente; firma distinta→`FIRMA_INVALIDA` sin herencia; 2º intento mismo código→`CODIGO_NO_CANJEABLE`; 2º código mismo cobrador→`COBRADOR_YA_ACTIVO`, hash de la clave firmante correcta).
10. **Lint**: `ruff` limpio en archivos nuevos (2 `B008` restantes por idiomática FastAPI existente del repo; `BLE001` marcados `noqa` por entrada arbitraria del atacante).
11. `git status --short` y `git diff --check` OK (sin cambios fuera del alcance).
12. **Riesgos pendientes**: consumo idempotente si el TTL de credencial bootstrap expira (reintento tardío → 409 `INTENTO_AGOTADO`, correcto); mapeo de rol de negocio `INVERSIONISTA` vs `ADMINISTRADOR` ya normalizado a mayúsculas en evidencias; mover `TestCanjeConcurrente` a conftest PG compartido queda para CI futura.

> **AÑADIDO VERIFICACIÓN PUNTUAL (2026-08-06, previa a Bloque 7):** cierre del caso B de seguridad. La rama idempotente de `canjear` re-verifica ahora la firma contra el intento almacenado antes de devolver la credencial: un segundo actor con `intento_id` pero **firma distinta** ya NO hereda por idempotencia el dispositivo/credencial del primero (`FIRMA_INVALIDA`, 401). Nuevos tests `TestIdempotenciaCasosABCD` (casos A–D) en `test_m5_activacion.py` (19 passed + 1 skip; suite completa **185 passed + 1 skip**). Evidencia A–D confirmada en PostgreSQL real (scratch `cobro_scratch_b6_pg`, drop final). Ruff limpio, `alembic check` limpio, `git diff --check` OK. **BLOQUE 6 = PASS DEFINITIVO.**
