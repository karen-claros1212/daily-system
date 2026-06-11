# Auditoría Técnica: CobroPro vs Proyecto AURA
## Baseline: Código Existente + TryController APK Decompilado — Gaps — Roadmap

**Fecha:** 2026-05-26 (v2 — con hallazgos del APK)
**Fuente TryController:** `/home/jesus/TryTiendas-5-8-1.apk` (jadx decompilado, 2,227+ archivos Java/Kotlin)

---

## 0. Lo Que Aprendimos del APK de TryController

TryController NO es una app de préstamos. Es un **retail POS** (punto de venta) que también maneja crédito. Su core es inventario/ventas, no cobranza. Esto recontextualiza toda la comparación.

### Stack Real (del código decompilado)

| Capa | TryController | CobroPro |
|------|---------------|----------|
| Lenguaje | Kotlin + Java | Python + TypeScript |
| Arquitectura | MVVM + Repository + Hilt DI | FastAPI monolítico + Next.js |
| ORM | Room (nuevo) + ActiveAndroid (legacy, 71 modelos) + raw SQLite | SQLAlchemy |
| HTTP Client | OkHttp + Retrofit | httpx (frontend), SQLAlchemy (backend) |
| Sync | WorkManager CoroutineWorker (871 líneas) | ❌ No existe |
| GPS | Dual: LocationListener (20m/30s) + FusedLocation (10s HIGH_ACCURACY) | lat/lng guardados pero sin tracking |
| Push | OneSignal | ❌ No existe |
| Chat | CometChat SDK (pago) | ❌ No existe |
| Impresión | ESC/POS térmica (USB/Bluetooth/Serial) | ❌ No existe |
| Facturación | DIAN (Colombia) | ❌ No existe |
| Hosting | Azure App Services (5 ambientes) | Docker Compose local |
| Cache | No visible | Redis 7 |

### API Real (35+ endpoints, 5 ambientes)

```
PROD:     https://trycstores.azurewebsites.net/api/
DEV:      https://wstrystoredev.azurewebsites.net/api/
QA:       https://trycstores-qa.azurewebsites.net/api/
PREPROD:  https://trycstore-preprod.azurewebsites.net/api/
MS:       https://mstrytiendas.azurewebsites.net/api/   (microservicios)
DISTRI:   https://wstrydistri.azurewebsites.net/api/    (distribución)
```

**Endpoints por grupo:**
- **Auth**: Login_4_00/Login (12 campos: User, Pwd, tryControllerCode, device info...), GetTokenSession
- **Sync**: Sales/InvSalesHeaderAndDetails, InvPurchasesHeaderAndDetails, SyncMovementsDevolutionProducts, InvCreditNotes
- **Ordenes**: Generals_4_00/setOrderManagement, setUpdateOrderDataTryDomi, setUpdateOrderStage, GetListOrdesTryDomi, getCheckStoreStatusTryDomi
- **Clientes**: Generals_4_00/GetDataCustomer
- **Pagos**: Generals_4_00/GetPaymentTypes
- **Productos**: Inventory_4_00/GetInvProducts, GetProductForName, Products/GetMostSoldProducts
- **Gráficas**: Graphics_4_00/V3/GetGraphsNew
- **GPS**: Generals_4_00/GetInformationDevice
- **Portfolio**: Generals_4_00/GetCurrentPortfolio, GetQuantityOrdersInPending
- **Notificaciones**: PushNotifications/CreateUserToken
- **Logs**: Logs/v5up/saveLogs

### Lo Que TryController NO Tiene (y AURA debe tener)
- Risk scoring (tasa fija 20% para todos)
- Geo-fencing (no valida ubicación)
- WebSockets / tiempo real (solo polling)
- Pagos digitales (solo efectivo)
- Voice AI
- Multi-tenant aislado

---

## 1. Resumen Ejecutivo

| Dimensión | CobroPro | TryController | AURA (objetivo) |
|---|---|---|---|
| Core de negocio | **Préstamos** (cobranza) | **Retail POS** (ventas + inventario) | Préstamos + cobranza inteligente |
| Plataforma | Web-only (Next.js) | App Android (2,227+ clases) | Web + App móvil offline-first |
| Backend | FastAPI + PostgreSQL | Azure Functions + on-device SQLite | FastAPI + PostgreSQL |
| Offline | ❌ No existe | ✅ Full offline con WorkManager sync | Offline-first (blueprint de TC) |
| Risk Scoring | ❌ Tasa fija 20% flat | ❌ Tasa fija | ✅ RiskEngine dinámico |
| Sync Engine | ❌ No existe | ✅ SyncOrderSynchronization table + batch POST | ✅ Basado en TC |
| GPS | lat/lng en visitas | ✅ Dual system: LocationListener + FusedLocation | ✅ Dual + geo-fencing |
| Push | ❌ | ✅ OneSignal | ✅ FCM |
| Chat | ❌ | ✅ CometChat | ❌ No planeado (MVP) |
| Mapa de ruta | Route con stops JSON | ❌ No tiene ruta de cobro | ✅ Ruta inteligente del día |
| Usuarios | ~4,000 | ~400,000 | Escalable |
| Recovery Rate | N/A | 28.6% | Target >35% |

---

## 2. Backend: Lo Que YA Existe (CobroPro)

_idéntico a v1 — ver 16 routers, 57 tablas_

## 3. Frontend: Lo Que YA Existe (CobroPro)

_idéntico a v1 — ver 11 páginas Next.js + api.ts_

## 4. Infraestructura

_idéntico a v1 — Docker Compose + PostgreSQL 16 + Redis 7 + MinIO_

---

## 5. GAPS vs TryController (ACTUALIZADO con hallazgos APK)

### 🟥 GAP 1: App Móvil + Offline-First (Crítico)

TryController es **nativa Android** con **offline-first completo**. CobroPro es **web-only**.

| Aspecto | TryController | CobroPro | AURA |
|---|---|---|---|
| Plataforma | Kotlin/Java nativa + Room + ActiveAndroid | Web Next.js | Flutter/RN + Room/local DB |
| Offline | SyncOrderSynchronization + WorkManager (871 líneas) | ❌ Nada | Replicar blueprint TC |
| GPS dual | LocationListener (20m/30s) + FusedLocation (10s HIGH_ACCURACY) | lat/lng sin validar | Dual + geo-fencing |
| Cámara | Presente (OCR no implementado funcionalmente) | ❌ | OCR cédula (ML Kit) |
| Push | OneSignal | ❌ | FCM |
| Impresión | ESC/POS térmica (USB/Bluetooth/Serial) | ❌ | Opcional |
| Chat | CometChat SDK | ❌ | No MVP |
| Error logging | CatchTryTiendas + MobileLogs | AuditLog (server-side) | MobileLogs del lado cliente |

**El blueprint del sync engine de TC es el activo más valioso del APK:**
```
SyncOrderSynchronization { id, idMov, tableName, typeProjectId, dateCreate, dateSync, statusSync }
SyncAllMovementsWorkManager (CoroutineWorker)
  → query SyncOrderSynchronization WHERE statusSync=0
  → build ArrayList<SyncOrderSynchronization>
  → POST /api/Sync con HTTP 200 + internal code 200 validation
  → updateSyncStatus() marca timestamp
```

**Esfuerzo estimado: 3-4 meses** (con sync engine blueprint ya documentado)

### 🟥 GAP 2: RiskEngine (Crítico — Diferenciador principal)

| Capacidad | TryController | CobroPro | AURA necesita |
|---|---|---|---|
| Tasa de interés | 20% flat (hardcoded) | 20% flat (STANDARD_CYCLE_DAYS=20) | Dinámica por perfil de riesgo |
| Scoring | ❌ No existe | ❌ No existe | Algoritmo basado en historial de pagos |
| Límite por cliente | No tiene concepto | No tiene concepto | Dinámico por score |
| Tasas preferenciales | ❌ | ❌ | Por historial |

**Esfuerzo estimado: 2 meses**

### 🟧 GAP 3: Geo-Fencing (Alto — Diferenciador)

TryController tiene GPS (coordinates en cada SyncRequest y GPS dual), pero **nunca valida ubicación para nada**. CobroPro igual — guarda lat/lng pero no valida.

AURA puede validar que el collector esté físicamente cerca del cliente al registrar un pago o visita.

**Esfuerzo estimado: 2-3 semanas**

### 🟧 GAP 4: Tiempo Real (Alto)

| Capacidad | TryController | CobroPro | AURA |
|---|---|---|---|
| Dashboard en vivo | ❌ Polling | ❌ Polling | WebSockets |
| Tracking collectors | ❌ | ❌ | Mapa en vivo |
| Alertas inmediatas | ❌ | ❌ | Push en tiempo real |

**Esfuerzo estimado: 3-4 semanas**

### 🟨 GAP 5: OCR + Biometría (Medio)

TryController tiene Google ML Kit en dependencias pero sin integración funcional en flujos principales.

**Esfuerzo estimado: 4-6 semanas**

### 🟩 GAP 6: Voice AI "Hola AURA" (Bajo — Marca)

Ningún competidor lo tiene.

**Esfuerzo estimado: 6-8 semanas**

### 🟩 GAP 7: Métodos de Pago Digital (Bajo)

TryController: solo efectivo. CobroPro: solo efectivo. Ambos igual.

**Esfuerzo estimado: 3-4 semanas**

---

## 6. Oportunidades de Diferenciación (ACTUALIZADO)

| Área | TryController | AURA puede hacerlo mejor |
|---|---|---|
| **Arquitectura de datos** | Dual ORM (Room + ActiveAndroid) = deuda técnica | ✅ SQLAlchemy limpio desde el día 1 |
| **Seguridad** | Credenciales en APK, Azure Blob público, XApiKey sin validar, Firebase PATCH writable | ✅ Secrets en env, audit log, payload hash |
| **Risk Scoring** | Tasa fija 20% para todos | ✅ Scoring dinámico por perfil de pago |
| **Geo-fencing** | GPS recolectado pero no validado | ✅ Validar collector en sitio |
| **Dashboard** | Sin KPIs en tiempo real | ✅ WebSockets + métricas en vivo |
| **Pagos digitales** | Solo efectivo | ✅ Transferencias, QR, links |
| **Sync engine** | WorkManager pesado (871 líneas), cola genérica | ✅ Sync más ligero y específico para préstamos |
| **Multi-tenant** | No aislado (partners en misma DB) | ✅ Aislamiento completo por tenant |
| **Recovery Rate** | 28.6% | ✅ Target 35%+ con RiskEngine + alertas tempranas |
| **Voice AI** | No existe | ✅ "Hola AURA" como diferenciador de marca |
| **Mantenibilidad** | ActiveAndroid legacy sin mantenimiento | ✅ Código moderno y mantenible |
| **Monetización** | Venta de licencias POS | ✅ SaaS multi-tenant recurrente |

---

## 7. Lo Que TryController HACE Mejor (y debemos copiar)

1. **Sync engine offline-first**: `SyncOrderSynchronization` → WorkManager → batch POST → HTTP200 validation
2. **GPS dual system**: LocationListener + FusedLocationProviderClient como fallback
3. **OneSignal push notifications**: Infraestructura completa de notificaciones
4. **Error logging**: CatchTryTiendas captura errores en dispositivo y los sincroniza
5. **Múltiples ambientes**: 5 entornos (PROD, DEV, QA, PREPROD, MS) fáciles de switchear
6. **Multi-POS TCP**: Para cuando hay múltiples dispositivos en una misma tienda
7. **Gestión de stages**: Ciclo de vida de órdenes con stageId (1-4) — aplicable a préstamos
8. **Tipos de pago**: PaymentType como entidad configurable (no hardcoded como CASH en CobroPro)

---

## 8. Roadmap Recomendado (ACTUALIZADO)

### Fase 0: Hardening (2-3 semanas) 🔴
- Agregar auth middleware a todos los routers sin protección (payments, loans, visits, reconciliation)
- Reemplazar `collector = db.query(User).first()` por `get_current_user`
- Cambiar `JWT_SECRET="change_me_now"`
- Agregar rate limiting + password min length
- Mover STANDARD_CYCLE_DAYS y constantes a DB

### Fase 1: App Móvil — MVP (3-4 meses) 🥇
- App con sync engine offline-first (blueprint TC: SyncOrderSynchronization + batch)
- GPS dual system (código TC como referencia)
- Visitas con cámara + firma
- Dashboard collector con ruta del día
- Pago offline (efectivo) con confirmación posterior
- Reglas de negocio configurables por branch

### Fase 2: RiskEngine (2 meses) 🟠
- Modelo de scoring basado en historial de pagos
- Tasas dinámicas, límites por cliente
- Dashboard de riesgo

### Fase 3: Geo-Fencing + Tiempo Real (6 semanas) 🟠
- Validación de proximidad collector-cliente
- WebSockets + tracking en vivo
- Push notifications (FCM, blueprint de OneSignal de TC)

### Fase 4: Pagos Digitales + OCR (6-8 semanas) 🟡
- Transferencias, QR, links de pago
- Lectura de cédula (ML Kit)

### Fase 5: Voice AI — "Hola AURA" (8 semanas) 🟢
- STT + NLP + TTS para comandos de voz

---

## 9. Estimación de Esfuerzo Total

| Componente | Tiempo | Prioridad | Dependencia |
|---|---|---|---|
| Hardening | 2-3 sem | 🔴 | — |
| App móvil offline-first | 3-4 meses | 🟠 | Hardening |
| RiskEngine | 2 meses | 🟠 | Historial de pagos (>3 meses datos) |
| Geo-fencing | 2-3 sem | 🟡 | App móvil |
| WebSockets + Push | 3-4 sem | 🟡 | App móvil |
| OCR + Biometría | 4-6 sem | 🟢 | App móvil |
| Pagos digitales | 3-4 sem | 🟢 | RiskEngine |
| Voice AI | 6-8 sem | 🟢 | App móvil |
| **Total** | **~8-10 meses** | | |

---

## 10. Preguntas Pendientes (Decisiones Arquitectónicas)

1. **Alcance MVP:** ¿App móvil standalone (como TC) o RiskEngine primero como diferenciador?
2. **Stack Móvil:** ¿Flutter (recomendado) o React Native?
3. **Estrategia Sync:** ¿Online-first con caché Redis o offline-first con SQLite local + cola (blueprint TC)?
4. **Cobros:** ¿Solo efectivo (rápido) o incluir pagos digitales desde el MVP?
5. **Multi-tenant:** ¿Mantener modelo CobroPro (pensado para vender a empresas) o simplificar?
