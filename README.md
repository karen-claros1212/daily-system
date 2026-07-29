# Plataforma de Cobro Diario — Colombia

SaaS de arriendo mensual para operadores de crédito de paga diario.

## Arquitectura

```
apps/api/        FastAPI · SQLAlchemy · Alembic · WeasyPrint
apps/mobile/     Flutter · PowerSync Dart SDK
apps/web/        Next.js · TypeScript (panel admin + Telegram Mini App)
infra/           Docker Compose
```

## HITO M0 — FUNDACIÓN EJECUTABLE

- Base de datos con RLS por negocio
- Modelos: negocio, usuario, ruta, cliente, credito, cuota_programada, jornada, pago, movimiento_caja
- Cálculos probados: total=cuota×n, saldo=total-abo, cuotas_pagadas=abo//cuota, pico=abo%cuota
- API REST mínima CRUD
- Docker Compose con PostgreSQL exclusivo
- Pruebas unitarias de cálculos financieros

## Ejecución

```bash
cd infra
docker compose up -d postgres
cd ../apps/api
pip install -r requirements.txt
alembic upgrade head
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

## Documento maestro

Ver `docs/DOCUMENTO-MAESTRO-Plataforma-Cobro-Colombia-v1.3-CERRADO.md`
