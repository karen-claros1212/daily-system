# Plan de Implementación — Daily System

**Proyecto:** daily-system
**Versión:** 1.3
**Fecha:** 2026-07-28
**Estado:** M0 en progreso

---

## Hito M0 — Fundación ejecutable

**Estado:** EN PROGRESO
**Archivos:** Ver sección "Archivos creados"
**Pruebas:** Pendientes (0/28)
**Dependencias:** Ninguna
**Commit de cierre:** —

### Requisitos

| # | Requisito | Estado | Archivos | Pruebas | Commit |
|---|---|---|---|---|---|
| M0.1 | Repo público creado | ✅ LISTO | `.gitignore`, `opencode.json` | — | 61c2b9a |
| M0.2 | AGENTS.md configurado | ✅ LISTO | `AGENTS.md` | — | 90493db |
| M0.3 | Protocolo Engram | ✅ LISTO | `docs/ENGRAM-PROTOCOL.md` | — | 90493db |
| M0.4 | Protocolo Graphify | ✅ LISTO | `docs/GRAPHIFY-PROTOCOL.md` | — | 61c2b9a |
| M0.5 | Infraestructura Docker | ⬜ PENDIENTE | `infra/docker-compose.yml` | — | — |
| M0.6 | Backend FastAPI skeleton | ⬜ PENDIENTE | `apps/api/src/main.py` | — | — |
| M0.7 | Database layer | ⬜ PENDIENTE | `apps/api/src/database.py` | — | — |
| M0.8 | Modelos SQLAlchemy (9 tablas) | ⬜ PENDIENTE | `apps/api/src/models/` | — | — |
| M0.9 | Schemas Pydantic | ⬜ PENDIENTE | `apps/api/src/schemas/` | — | — |
| M0.10 | Migration Alembic init | ⬜ PENDIENTE | `apps/api/alembic.ini` | — | — |
| M0.11 | Routes: negocio | ⬜ PENDIENTE | `apps/api/src/routes/negocio.py` | — | — |
| M0.12 | Routes: ruta | ⬜ PENDIENTE | `apps/api/src/routes/ruta.py` | — | — |
| M0.13 | Routes: cliente | ⬜ PENDIENTE | `apps/api/src/routes/cliente.py` | — | — |
| M0.14 | Routes: credito | ⬜ PENDIENTE | `apps/api/src/routes/credito.py` | — | — |
| M0.15 | Routes: pago | ⬜ PENDIENTE | `apps/api/src/routes/pago.py` | — | — |
| M0.16 | Routes: hoja_viva | ⬜ PENDIENTE | `apps/api/src/routes/hoja_viva.py` | — | — |
| M0.17 | Services: calculation_service | ⬜ PENDIENTE | `apps/api/src/services/calculation_service.py` | — | — |
| M0.18 | Tests: calculaciones financieras | ⬜ PENDIENTE | `apps/api/src/tests/test_calculations.py` | 12 tests | — |
| M0.19 | Tests: API integration | ⬜ PENDIENTE | `apps/api/src/tests/test_api.py` | 16 tests | — |
| M0.20 | Health endpoint | ⬜ PENDIENTE | `apps/api/src/main.py` | 1 test | — |

### Notas M0
- El grafo de Graphify se generará después de completar M0.20
- Se ejecutará `graphify . --update` como último paso de M0

---

## Hito M1 — Hoja viva y pagos

**Estado:** PENDIENTE
**Dependencias:** M0 completo
**Archivos:** `apps/api/src/routes/hoja_viva.py`, `apps/api/src/services/hoja_viva_service.py`
**Pruebas:** Pendientes
**Commit de cierre:** —

### Requisitos

| # | Requisito | Estado | Archivos | Pruebas | Commit |
|---|---|---|---|---|---|
| M1.1 | Calcular crédito (cuota × días) | ⬜ PENDIENTE | `calculation_service.py` | 5 tests | — |
| M1.2 | Calcular caja (asignar pagos) | ⬜ PENDIENTE | `calculation_service.py` | 5 tests | — |
| M1.3 | Hoja viva del día | ⬜ PENDIENTE | `hoja_viva_service.py` | 4 tests | — |
| M1.4 | Registrar pago parcial | ⬜ PENDIENTE | `pago.py` route | 3 tests | — |
| M1.5 | Reversar pago | ⬜ PENDIENTE | `pago.py` route | 2 tests | — |
| M1.6 | Historial de pagos | ⬜ PENDIENTE | `pago.py` route | 2 tests | — |
| M1.7 | Cálculo de pico y residuo | ⬜ PENDIENTE | `calculation_service.py` | 3 tests | — |
| M1.8 | Renegociación básica | ⬜ PENDIENTE | `credito.py` route | 2 tests | — |

### Notas M1
- `calcular_credito()` debe producir resultados idénticos al documento maestro
- `calcular_caja()` debe manejar múltiples abonos parciales
- Hoja viva debe generar PDF o JSON imprimible

---

## Hito M2 — Jornada, caja y TERMINAR JORNADA

**Estado:** PENDIENTE
**Dependencias:** M1 completo
**Archivos:** `apps/api/src/routes/jornada.py`, `apps/api/src/services/jornada_service.py`
**Pruebas:** Pendientes
**Commit de cierre:** —

### Requisitos

| # | Requisito | Estado | Archivos | Pruebas | Commit |
|---|---|---|---|---|---|
| M2.1 | Iniciar jornada | ⬜ PENDIENTE | `jornada.py` route | 2 tests | — |
| M2.2 | Cerrar jornada | ⬜ PENDIENTE | `jornada.py` route | 3 tests | — |
| M2.3 | Total recaudado por jornada | ⬜ PENDIENTE | `jornada.py` route | 2 tests | — |
| M2.4 | Movimientos de caja | ⬜ PENDIENTE | `movimiento_caja.py` | 3 tests | — |
| M2.5 | Reporte de jornada | ⬜ PENDIENTE | `jornada_service.py` | 2 tests | — |
| M2.6 | Anular jornada | ⬜ PENDIENTE | `jornada.py` route | 2 tests | — |

### Notas M2
- Una jornada solo puede cerrar si todas las cuotas del día están cubiertas o marcadas como impagas
- El pico (abono % cuota) se registra como abono a la siguiente cuota

---

## Hito M3 — Suscripción, Telegram e inversionista

**Estado:** PENDIENTE
**Dependencias:** M2 completo
**Archivos:** `apps/api/src/routes/suscripcion.py`, `apps/telegram-bot/`
**Pruebas:** Pendientes
**Commit de cierre:** —

### Requisitos

| # | Requisito | Estado | Archivos | Pruebas | Commit |
|---|---|---|---|---|---|
| M3.1 | Planes y suscripciones | ⬜ PENDIENTE | `suscripcion.py` | 4 tests | — |
| M3.2 | Bot Telegram (cobrador) | ⬜ PENDIENTE | `apps/telegram-bot/` | — | — |
| M3.3 | Bot Telegram (inversionista) | ⬜ PENDIENTE | `apps/telegram-bot/` | — | — |
| M3.4 | Panel inversionista (web) | ⬜ PENDIENTE | `apps/web/src/app/inversionista/` | — | — |
| M3.5 | Reporte diario automático | ⬜ PENDIENTE | `telegram_bot.py` | 2 tests | — |
| M3.6 | Límite de rutas por plan | ⬜ PENDIENTE | `negocio.py` route | 2 tests | — |

### Notas M3
- Plan free: 1 ruta, 100 clientes
- Plan básico: 5 rutas, 500 clientes
- Plan pro: rutas ilimitadas, clientes ilimitados

---

## Hito M4 — Importación OCR

**Estado:** PENDIENTE
**Dependencias:** M3 completo
**Archivos:** `apps/api/src/services/ocr_service.py`
**Pruebas:** Pendientes
**Commit de cierre:** —

### Requisitos

| # | Requisito | Estado | Archivos | Pruebas | Commit |
|---|---|---|---|---|---|
| M4.1 | OCR de comprobantes | ⬜ PENDIENTE | `ocr_service.py` | 3 tests | — |
| M4.2 | Validación automática | ⬜ PENDIENTE | `ocr_service.py` | 2 tests | — |
| M4.3 | Upload de imagen | ⬜ PENDIENTE | `pago.py` route | 2 tests | — |

---

## Hito M5 — Score, chatbot e inteligencia

**Estado:** PENDIENTE
**Dependencias:** M4 completo
**Archivos:** `apps/api/src/services/score_service.py`, `apps/api/src/services/chatbot_service.py`
**Pruebas:** Pendientes
**Commit de cierre:** —

### Requisitos

| # | Requisito | Estado | Archivos | Pruebas | Commit |
|---|---|---|---|---|---|
| M5.1 | Score de cobro por cliente | ⬜ PENDIENTE | `score_service.py` | 3 tests | — |
| M5.2 | Chatbot asistente | ⬜ PENDIENTE | `chatbot_service.py` | 2 tests | — |
| M5.3 | Predicción de pagos | ⬜ PENDIENTE | `score_service.py` | 2 tests | — |
| M5.4 | Alertas de mora | ⬜ PENDIENTE | `score_service.py` | 2 tests | — |

---

## Hito M6 — Producción y despliegue

**Estado:** PENDIENTE
**Dependencias:** M5 completo
**Archivos:** `infra/docker-compose.prod.yml`, `infra/nginx/`, `.github/workflows/`
**Pruebas:** Pendientes
**Commit de cierre:** —

### Requisitos

| # | Requisito | Estado | Archivos | Pruebas | Commit |
|---|---|---|---|---|---|
| M6.1 | Docker Compose producción | ⬜ PENDIENTE | `infra/docker-compose.prod.yml` | — | — |
| M6.2 | CI/CD pipeline | ⬜ PENDIENTE | `.github/workflows/ci.yml` | — | — |
| M6.3 | Nginx reverse proxy | ⬜ PENDIENTE | `infra/nginx/` | — | — |
| M6.4 | SSL/TLS | ⬜ PENDIENTE | `infra/nginx/` | — | — |
| M6.5 | Monitoreo | ⬜ PENDIENTE | `infra/prometheus/` | — | — |
| M6.6 | Backups automáticos | ⬜ PENDIENTE | `infra/scripts/` | — | — |
| M6.7 | Logs centralizados | ⬜ PENDIENTE | `infra/` | — | — |

---

## Resumen de Progreso

| Hito | Estado | Progreso |
|---|---|---|
| **M0** | EN PROGRESO | 4/20 (20%) |
| **M1** | PENDIENTE | 0/8 (0%) |
| **M2** | PENDIENTE | 0/6 (0%) |
| **M3** | PENDIENTE | 0/6 (0%) |
| **M4** | PENDIENTE | 0/3 (0%) |
| **M5** | PENDIENTE | 0/4 (0%) |
| **M6** | PENDIENTE | 0/7 (0%) |
| **TOTAL** | EN PROGRESO | **4/54 (7%)** |

---

## Reglas de Avance

1. **M0 primero:** No avanzar a M1 sin M0 completo (modelos + migraciones + tests)
2. **Tests antes de merge:** Cada requisito debe tener tests pasando
3. **Commit por requisito:** Un commit por requisito completado
4. **Graphify después de M0:** Actualizar grafo al cerrar M0
5. **Engram en cada hito:** Guardar `mem_session_summary` al cerrar cada hito
