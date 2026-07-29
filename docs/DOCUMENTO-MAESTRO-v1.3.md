# Documento Maestro — Daily System v1.3 (resumen operativo)

> ⚠️ **Este es un resumen derivado.** La fuente de verdad es:
> `docs/DOCUMENTO-MAESTRO-Plataforma-Cobro-Colombia-v1.3-CERRADO.md`
> (22 partes + 3 apéndices, ~1,400 líneas).

**Proyecto:** Daily System
**Identificador:** daily-system
**Raíz:** /home/jesus/proyectos/daily-system
**Versión:** 1.3
**Fecha:** 2026-07-28
**Estado:** M0 en progreso

---

## 1. Visión

Plataforma de cobro diario para microcréditos en Colombia. Permite a cobradores registrar pagos en campo (offline-first), calcular cuotas, generar hojas de vida de clientes, cerrar jornadas y reportar al inversionista.

### Principios

- **Offline-first:** El cobrador trabaja sin conexión y sincroniza después.
- **Money = integers COP:** Cero decimales. Todo en centavos.
- **Rates = NUMERIC:** Tasas con precisión decimal.
- **UUIDs:** Todos los modelos usan `UUID(as_uuid=True)`.
- **Filtrado por negocio:** Toda query operativa filtra por `negocio_id`.
- **Simple > Completo:** M0 funcional > M0 perfecto.

---

## 2. Stack

| Capa | Tecnología |
|---|---|
| **Backend API** | Python 3.12, FastAPI, SQLAlchemy 2.0, Alembic |
| **Base de datos** | PostgreSQL 16+ (Docker), UUID primary keys |
| **Frontend Panel** | Next.js 14, TypeScript, Tailwind CSS, shadcn/ui |
| **App Móvil** | Flutter (offline-first) |
| **Sincronización** | PowerSync (PostgreSQL → SQLite en dispositivo) |
| **Infraestructura** | Docker Compose, WSL Ubuntu |
| **Testing** | pytest, Playwright (E2E) |
| **Memoria** | Engram (decisión persistente), Graphify (estructura código) |

---

## 3. Arquitectura de Directorios

```
daily-system/
├── apps/
│   ├── api/                    # Backend FastAPI
│   │   ├── src/
│   │   │   ├── main.py         # Entry point
│   │   │   ├── database.py     # Engine, session, Base
│   │   │   ├── models/         # SQLAlchemy models
│   │   │   ├── schemas/        # Pydantic schemas
│   │   │   ├── routes/         # API routers
│   │   │   ├── services/       # Business logic
│   │   │   └── tests/          # Unit + integration tests
│   │   ├── alembic/            # Migrations
│   │   └── requirements.txt
│   ├── web/                    # Panel admin (Next.js)
│   │   ├── src/
│   │   └── package.json
│   └── mobile/                 # App cobrador (Flutter)
│       ├── lib/
│       └── pubspec.yaml
├── infra/
│   ├── docker-compose.yml      # PostgreSQL + PowerSync
│   └── .env.example
├── docs/
│   ├── DOCUMENTO-MAESTRO.md    # Este documento
│   ├── IMPLEMENTATION-PLAN.md  # Plan por hitos
│   ├── STATUS.md               # Estado por sesión
│   ├── ENGRAM-PROTOCOL.md      # Protocolo Engram
│   ├── GRAPHIFY-AUDIT.md       # Auditoría Graphify
│   └── GRAPHIFY-PROTOCOL.md    # Protocolo Graphify
├── tests/                      # Tests E2E globales
├── AGENTS.md                   # Reglas del agente
├── .gitignore
├── opencode.json               # MCP configs
└── graphify-out/               # Grafo de conocimiento (regenerable)
```

---

## 4. Modelo de Datos (9 tablas)

### 4.1 negocio
```
id: UUID (PK)
nombre: VARCHAR(200)
nit: VARCHAR(50)
pais: VARCHAR(3) DEFAULT 'CO'
moneda: VARCHAR(3) DEFAULT 'COP'
zona_horaria: VARCHAR(50) DEFAULT 'America/Bogota'
plan: VARCHAR(50) DEFAULT 'basic'
estado_suscripcion: VARCHAR(50) DEFAULT 'al_dia'
paid_through_at: TIMESTAMP
creado_el: TIMESTAMP DEFAULT NOW()
```

### 4.2 usuario
```
id: UUID (PK)
negocio_id: UUID (FK → negocio)
email: VARCHAR(255) UNIQUE
password_hash: VARCHAR(255)
rol: VARCHAR(50)  # admin, cobrador, inversionista
activo: BOOLEAN DEFAULT TRUE
creado_el: TIMESTAMP DEFAULT NOW()
```

### 4.3 ruta
```
id: UUID (PK)
negocio_id: UUID (FK → negocio)
nombre: VARCHAR(200)
cobrador_id: UUID (FK → usuario, nullable)
activa: BOOLEAN DEFAULT TRUE
version: INTEGER DEFAULT 1
creado_el: TIMESTAMP DEFAULT NOW()
UNIQUE (negocio_id, nombre, activa)
```

### 4.4 cliente
```
id: UUID (PK)
negocio_id: UUID (FK → negocio)
primer_apellido: VARCHAR(100)
nombres: VARCHAR(200)
direccion: VARCHAR(300)
barrio: VARCHAR(100)
ciudad: VARCHAR(100)
telefono: VARCHAR(20)
identity_status: VARCHAR(50)  # PROVISIONAL, VERIFICADO, RECHAZADO
creado_el: TIMESTAMP DEFAULT NOW()
UNIQUE (negocio_id, telefono)
```

### 4.5 credito
```
id: UUID (PK)
ruta_id: UUID (FK → ruta)
cliente_id: UUID (FK → cliente)
total: BIGINT (COP)
cuota_diaria: BIGINT (COP)
dias: INTEGER
total_pagado: BIGINT DEFAULT 0
saldo_pendiente: BIGINT GENERATED ALWAYS AS (total - total_pagado) STORED
estado: VARCHAR(50)  # ACTIVO, PAGADO, RENOVADO, BAJA
version: INTEGER DEFAULT 1
creado_el: TIMESTAMP DEFAULT NOW()
```

### 4.6 cuota_programada
```
id: UUID (PK)
credito_id: UUID (FK → credito)
fecha: DATE
monto: BIGINT (COP)
pagada: BOOLEAN DEFAULT FALSE
pago_id: UUID (FK → pago, nullable)
creado_el: TIMESTAMP DEFAULT NOW()
UNIQUE (credito_id, fecha)
```

### 4.7 jornada
```
id: UUID (PK)
ruta_id: UUID (FK → ruta)
fecha: DATE
cobrador_id: UUID (FK → usuario)
total_recaudado: BIGINT DEFAULT 0
estado: VARCHAR(50)  # EN_PROGRESO, CERRADA, ANULADA
creado_el: TIMESTAMP DEFAULT NOW()
UNIQUE (ruta_id, fecha)
```

### 4.8 pago
```
id: UUID (PK)
credito_id: UUID (FK → credito)
jornada_id: UUID (FK → jornada, nullable)
monto: BIGINT (COP)
fecha: TIMESTAMP DEFAULT NOW()
tipo: VARCHAR(50)  # PARCIAL, TOTAL, EXTRA
observaciones: TEXT
creado_el: TIMESTAMP DEFAULT NOW()
```

### 4.9 movimiento_caja
```
id: UUID (PK)
jornada_id: UUID (FK → jornada)
tipo: VARCHAR(50)  # COBRO, DEVOLUCION, RETIRO, APOYO
monto: BIGINT (COP)
descripcion: TEXT
fecha: TIMESTAMP DEFAULT NOW()
creado_el: TIMESTAMP DEFAULT NOW()
```

---

## 5. Reglas Financieras

### 5.1 Cálculo de crédito

```
total = cuota_diaria × dias
saldo = total - total_pagado
cuotas_pagadas = total_pagado ÷ cuota_diaria  (entero)
pico = total_pagado % cuota_diaria
```

### 5.2 Cálculo de caja

```
para cada cobro del día:
  cuotas_pagadas = abono ÷ cuota
  residuos = abono % cuota
  asignar a cuotas_programadas pendientes
  actualizar credito.total_pagado
  actualizar credito.saldo_pendiente
```

### 5.3 Renovación

```
nuevo_total = saldo_pendiente × (1 + tasa_renovacion)
nueva_cuota = nuevo_total ÷ nuevos_dias
nuevo_dias = dias_originales (o los que fijen)
```

---

## 6. Endpoints API Planeados

### 6.1 Negocio
- `POST /api/negocios` — Crear negocio
- `GET /api/negocios` — Listar negocios
- `GET /api/negocios/{id}` — Obtener negocio

### 6.2 Ruta
- `POST /api/rutas?negocio_id={id}` — Crear ruta
- `GET /api/rutas?negocio_id={id}` — Listar rutas activas
- `GET /api/rutas/{id}` — Obtener ruta

### 6.3 Cliente
- `POST /api/clientes?negocio_id={id}` — Crear cliente
- `GET /api/clientes?negocio_id={id}` — Listar clientes
- `GET /api/clientes/{id}` — Obtener cliente

### 6.4 Crédito
- `POST /api/creditos` — Crear crédito
- `GET /api/creditos?ruta_id={id}` — Listar créditos
- `GET /api/creditos/{id}` — Obtener crédito
- `PUT /api/creditos/{id}` — Actualizar crédito

### 6.5 Pago
- `POST /api/pagos` — Registrar pago
- `GET /api/pagos?credito_id={id}` — Historial de pagos
- `POST /api/pagos/{id}/reversar` — Reversar pago

### 6.6 Hoja Viva
- `GET /api/rutas/{ruta_id}/hoja-viva` — Hoja viva del día

### 6.7 Jornada
- `POST /api/jornadas` — Iniciar jornada
- `PUT /api/jornadas/{id}/cerrar` — Cerrar jornada
- `GET /api/jornadas/{id}` — Detalles de jornada

### 6.8 Salud
- `GET /api/health` — Health check

---

## 7. Criterios de Éxito

### M0 (Fundación ejecutable)
- [ ] PostgreSQL corre en Docker
- [ ] Alembic migra las 9 tablas
- [ ] 28+ tests pasan (12 financieros + 16 API)
- [ ] Endpoint `/api/health` responde
- [ ] CRUD de negocio, ruta, cliente funciona

### M1 (Hoja viva y pagos)
- [ ] `calcular_credito()` correcto
- [ ] `calcular_caja()` correcto
- [ ] Hoja viva genera resumen del día
- [ ] Pagos actualizan saldos correctamente

### M2 (Jornada, caja, TERMINAR JORNADA)
- [ ] Jornada cierra correctamente
- [ ] Cálculo de pico y residuos
- [ ] Reporte de jornada

### M3 (Suscripción, Telegram, inversionista)
- [ ] Planes y suscripciones
- [ ] Bot de Telegram
- [ ] Panel de inversionista

### M4 (Importación OCR)
- [ ] OCR de comprobantes
- [ ] Validación automática

### M5 (Score, chatbot, inteligencia)
- [ ] Score de cobro
- [ ] Chatbot asistente
- [ ] Predicción de pagos

### M6 (Producción y despliegue)
- [ ] Docker Compose en producción
- [ ] CI/CD pipeline
- [ ] Monitoreo y alertas

---

## 8. Versionado

| Versión | Fecha | Cambio |
|---|---|---|
| 1.0 | 2026-07-28 | Documento inicial |
| 1.1 | 2026-07-28 | Ajuste de schema (9 tablas) |
| 1.2 | 2026-07-28 | Reglas financieras verificadas |
| 1.3 | 2026-07-28 | Estructura de directorios, stack definido |

---

## 9. Dependencias entre Hitos

```
M0 → M1 → M2 → M3 → M4 → M5 → M6
```

Cada hito depende del anterior. No se puede hacer M1 sin M0 (modelos + migraciones).
