# AURA — Modelo de Datos (Fusión CobroPro + TryController)

## Estrategia de Fusión

| Fuente | Rol en AURA |
|--------|-------------|
| **CobroPro** | Base — modelo de negocio de préstamos (clientes, préstamos, pagos, visitas, caja, arqueo) |
| **TryController** | Inspiración — patrones de infraestructura (sync offline, GPS dual, notificaciones, error logging, tipos de pago) |

---

## 1. Core del Negocio (de CobroPro, adaptado)

### Tenant → License → Branch → Group
```
Tenant { id, name, schema_name, status, currency, logo_url, country }
License { id, tenant_id, plan_type, expiration_date }
Branch  { id, tenant_id, name, location, max_daily_loan, max_expense_amount, days_late_yellow, days_late_red }
Group   { id, tenant_id, branch_id, name, description, parent_id }  ← Rutas jerárquicas
```
> **Añadir de TryController**: `working_hours` (Branch), `config_iva_percentage` si aplica

### User (4 roles RBAC)
```
User { id, username, password_hash, role[SUPER_ADMIN|TENANT_ROOT|ADMIN|COLLECTOR],
       tenant_id, group_id, device_id, push_token, gps_enabled }
```
> **Nuevo**: `push_token` (OneSignal/FCM), `gps_enabled` (control de GPS)

### Customer
```
Customer { id, tenant_id, group_id, doc_type, doc_num, name, phone, address,
           lat, lng, consent, consent_at, risk_score, delinquency_days,
           last_visit_at, photo_url }
```
> **Nuevo**: `risk_score` (RiskEngine), `delinquency_days` (cache), `last_visit_at`, `photo_url`

---

## 2. Módulo de Préstamos (CobroPro mejorado)

### Loan + Schedule
```
Loan { id, tenant_id, group_id, customer_id, currency, amount, term_days,
       annual_rate, rate_period[ANNUAL|MONTHLY], payment_frequency[DAILY|WEEKLY|BIWEEKLY|MONTHLY],
       disbursement_date, status[ACTIVE|PAID|WRITTEN_OFF|REFINANCED],
       stage_id, collect_method[FIELD|BANK_TRANSFER|DIGITAL_WALLET],
       risk_level, parent_loan_id }
```
> **Nuevo de TryController**: `stage_id` (1-4 ciclo de vida como TryDomi), `collect_method` (múltiples métodos de cobro), `parent_loan_id` (refinanciamiento), `risk_level`

```
Schedule { id, loan_id, n, due_date, principal, interest, total,
           status[PENDING|PAID|PARTIAL|LATE|FORECLOSURE] }
```
> **Nuevo**: `PARTIAL` status, `LATE` con alertas por días de atraso

---

## 3. Módulo de Pagos (CobroPro + TryController)

### Payment
```
Payment { id, tenant_id, schedule_id, loan_id, method[CASH|TRANSFER|DIGITAL_WALLET|CARD],
          amount, currency, collector_id, status[CONFIRMED|PENDING|REJECTED|REFUNDED],
          external_ref, evidence_url, notes, lat, lng, 
          sync_status, uuid, created_at }
```
> **Nuevo de TryController**: `method` extendido (no solo CASH), `sync_status`, `uuid` (para sync offline-idempotencia), `lat/lng` (geo-validación)

### PaymentMethod (nuevo de TryController)
```
PaymentMethod { id, tenant_id, name, code, is_active, commission_pct }
```

---

## 4. Sync Engine (de TryController — EL PATRÓN MÁS IMPORTANTE)

### SyncOrderSynchronization
```
SyncOrder { id, entity_type, entity_id, tenant_id, action[CREATE|UPDATE|DELETE],
            sync_status[0=PENDING|1=SYNCED|2=ERROR], created_at, synced_at, retries }
```
> Copiado de `com.example.trystore.database.entities.SyncOrderSynchronization`
> Funciona como cola de cambios pendientes: cada escritura offline genera un registro aquí
> WorkManager barre periódicamente, envía batch, valida HTTP 200 + code 200, marca synced

### MobileLogs (de TryController)
```
MobileLog { id, tenant_id, user_id, module, code, message, device_info, created_at }
```
> Error logging desde el móvil, igual que `CatchTryTiendas`

---

## 5. Geo & Visitas (CobroPro + GPS dual TryController)

### CollectVisit
```
CollectVisit { id, tenant_id, collector_id, customer_id, loan_id,
               ts, result[COLLECTED|NOT_FOUND|REFUSED|PROMISED],
               notes, lat, lng, photo_url, sync_status }
```
> **Nuevo**: `sync_status`, `loan_id` (asociar visita a préstamo específico)

### GPSTracking (nuevo, inspirado en TryController dual GPS)
```
GPSTracking { id, tenant_id, user_id, lat, lng, accuracy, provider[GPS|NETWORK|FUSED],
              battery_pct, ts, is_moving }
```
> Tracking continuo (10-30s intervalo) para geo-fencing y ruta del día

### GeoFence (nuevo)
```
GeoFence { id, tenant_id, customer_id, lat, lng, radius_meters, is_active }
```

---

## 6. Caja & Arqueo (CobroPro)

```
CashMovement { id, tenant_id, type[OPENING|EXPENSE|WITHDRAWAL|INCOME],
               amount, description, user_id, sync_status }

Reconciliation { id, tenant_id, collector_id, close_date, reported_total,
                 delivered_total, diff, notes, sync_status }
```

---

## 7. Dispositivos & Acceso (CobroPro)

```
Device { id, tenant_id, user_id, imei, alias, status[PENDING|APPROVED|BLOCKED],
         last_login, app_version, os_version, brand, model }  ← device info de LoginRequest TC

AccessKey { id, tenant_id, code, action_type[DELETE_PAYMENT|OVERRIDE_LIMIT|REFINANCE|OTHER],
            status[ACTIVE|USED|EXPIRED], generated_by, used_by, expires_at }
```

---

## 8. Seguridad & Auditoría (CobroPro mejorado)

```
AuditLog { id, tenant_id, actor, action, entity, entity_id,
           payload_hash, ip, user_agent, ts }
```

---

## 9. RiskEngine (NUEVO — diferenciador AURA)

```
RiskRule { id, tenant_id, name, metric[DELINQUENCY_DAYS|LOAN_AMOUNT|HISTORIC_PAYMENTS|GPS_ANOMALY],
           operator[GT|LT|EQ|BETWEEN], value, score, is_active }

RiskScore { id, customer_id, score, level[LOW|MEDIUM|HIGH|CRITICAL],
            factors JSON, computed_at }
```

---

## 10. Notificaciones (de TryController — OneSignal)

```
Notification { id, tenant_id, user_id, type[PAYMENT_REMINDER|VISIT_ALERT|RECONCILIATION|PROMOTION],
               title, body, data JSON, is_read, created_at }

PushToken { id, user_id, device_id, provider[FCM|APNS], token, is_active }
```

---

## 11. Maestros (nuevo de TryController)

```
PaymentType { id, tenant_id, name, code, is_active, commission_pct }

CollectMethod { id, tenant_id, name, code[CASH|TRANSFER|WALLET|CARD], is_active }

WorkingHours { id, branch_id, day_of_week, open_time, close_time, is_active }

Config { id, tenant_id, key, value, type, description }
```

---

## Mapa de Procedencia

### Tablas que se heredan de CobroPro (base):
`tenants`, `licenses`, `branches`, `groups`, `users`, `customers`, `loans`, `schedules`, `payments`, `collect_visits`, `routes`, `reconciliations`, `cash_movements`, `devices`, `access_keys`, `audit_logs`

### Tablas nuevas inspiradas en TryController:
`sync_orders`, `mobile_logs`, `gps_tracking`, `geo_fences`, `push_tokens`, `notifications`, `payment_types`, `collect_methods`, `working_hours`, `config`

### Tablas nuevas propias de AURA:
`risk_rules`, `risk_scores`

---

## Estrategia de Sync (blueprint de TryController)

```
1. Cada escritura offline → INSERT en sync_orders (entity, id, action, status=0)
2. WorkManager (coroutine) cada N minutos:
   a. SELECT * FROM sync_orders WHERE status=0 LIMIT batch_size
   b. POST /api/v1/sync con JSON array + token + uuid cliente
   c. Validar HTTP 200 + statusCode 200
   d. UPDATE sync_orders SET status=1, synced_at=NOW()
   e. Si error → UPDATE retries++, status=2 si retries>max
3. Conflicto: last-write-wins con timestamp UTC
4. Idempotencia: uuid único por operación
```

---

## Stack Propuesto

| Capa | Tecnología |
|------|-----------|
| Backend | FastAPI (CobroPro existente) + PostgreSQL |
| Sync | API REST + tabla `sync_orders` + batch endpoint `/api/v1/sync` |
| Móvil | Pendiente (Flutter o React Native) |
| Offline | Room (Android) o similar (flutter) |
| GPS | FusedLocationProviderClient (10s HIGH_ACCURACY) |
| Push | Firebase Cloud Messaging (FCM) |
| Mapas | Mapbox o Google Maps |
