"""FastAPI application for Daily System."""

import os
from datetime import datetime, timezone

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.routes.cliente import router as cliente_router
from src.routes.credito import router as credito_router
from src.routes.dispositivo import router as dispositivo_router
from src.routes.hoja_viva import router as hoja_viva_router
from src.routes.inversionista import router as inversionista_router
from src.routes.jornada import router as jornada_router
from src.routes.movimiento import router as movimiento_router
from src.routes.negocio import router as negocio_router
from src.routes.pago import router as pago_router
from src.routes.ruta import router as ruta_router

app = FastAPI(
    title="Daily System API",
    description="Plataforma local-first para crédito diario, cobranza de campo, rutas, caja y riesgo en Colombia",
    version="0.1.0",
)

cors_origins = os.getenv(
    "CORS_ALLOWED_ORIGINS",
    "http://localhost:7101,http://localhost:3000",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def suscripcion_middleware(request: Request, call_next):
    """Check subscription status on protected endpoints.

    Skips: GET /api/health, GET /api/inversionista/suscripcion,
           POST /api/negocios (registration).
    Applies to: pagos, creditos, jornadas, movimientos, dispositivos.
    """
    # Skip subscription check for these paths
    skip_paths = {
        "/api/health",
        "/api/inversionista/suscripcion",
        "/api/negocios",
    }

    if request.url.path in skip_paths:
        return await call_next(request)

    # Only check write endpoints (POST, PUT, DELETE) and only in production
    env = os.getenv("DAILY_ENV", "test")
    if env in ("test", "development", "dev"):
        return await call_next(request)

    if request.method not in ("POST", "PUT", "DELETE"):
        return await call_next(request)

    # Extract negocio_id from query params (from get_request_context)
    negocio_id = request.query_params.get("negocio_id")
    if not negocio_id:
        # No negocio_id in request — allow through (will be caught by endpoint)
        return await call_next(request)

    from src.models import Negocio
    from sqlalchemy import make_url

    # Use the same DB connection pattern as the app
    db_url = os.getenv("API_DATABASE_URL", "sqlite:///:memory:")

    if "sqlite" in db_url:
        # For SQLite tests, skip subscription check
        return await call_next(request)

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(db_url)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()

    try:
        negocio = db.query(Negocio).filter(Negocio.id == negocio_id).first()
        if not negocio:
            return JSONResponse(
                status_code=404,
                content={"detail": "Negocio no encontrado"},
            )

        if negocio.estado_suscripcion != "al_dia":
            return JSONResponse(
                status_code=403,
                content={
                    "detail": f"Suscripcion: {negocio.estado_suscripcion}",
                    "code": "SUSCRIPCION_INACTIVA",
                },
            )

        if negocio.paid_through_at and negocio.paid_through_at < datetime.now(timezone.utc):
            return JSONResponse(
                status_code=403,
                content={
                    "detail": f"Suscripcion vencida el {negocio.paid_through_at.isoformat()}",
                    "code": "SUSCRIPCION_VENCIDA",
                },
            )

        return await call_next(request)
    except Exception:
        # If DB query fails, allow through (endpoint will handle)
        return await call_next(request)
    finally:
        db.close()


app.include_router(negocio_router)
app.include_router(ruta_router)
app.include_router(cliente_router)
app.include_router(credito_router)
app.include_router(pago_router)
app.include_router(hoja_viva_router)
app.include_router(jornada_router)
app.include_router(movimiento_router)
app.include_router(dispositivo_router)
app.include_router(inversionista_router)


@app.get("/api/health")
def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "daily-system-api"}
