"""FastAPI application for Daily System."""

import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.routes.activacion import (
    device_router,
    mobile_router,
)
from src.routes.activacion import router as activacion_router
from src.routes.auth import router as auth_router
from src.routes.audit import router as audit_router
from src.routes.cliente import router as cliente_router
from src.routes.credito import router as credito_router
from src.routes.dispositivo import router as dispositivo_router
from src.routes.hoja_viva import router as hoja_viva_router
from src.routes.inversionista import router as inversionista_router
from src.routes.llm import router as llm_router
from src.routes.jornada import router as jornada_router
from src.routes.movimiento import router as movimiento_router
from src.routes.negocio import router as negocio_router
from src.routes.onboarding import router as onboarding_router
from src.routes.pago import router as pago_router
from src.routes.cobranza import router as cobranza_router
from src.routes.dashboard import router as dashboard_router
from src.routes.reportes import router as reportes_router
from src.routes.ruta import router as ruta_router
from src.routes.usuario import router as usuario_router
from src.time_utils import as_utc


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Fail-closed al arrancar (D7-H1): en staging/production se exige la
    clave ES256 privada antes de servir trafico. En dev/test el requisito se
    aplica al emitir/validar (token.py), no al arranque."""
    env = os.getenv("DAILY_ENV", "test")
    if env in ("staging", "production", "prod"):
        from src.auth.token import ensure_es256_configured

        ensure_es256_configured()
    yield


app = FastAPI(
    title="Daily System API",
    description="Plataforma local-first para crédito diario, cobranza de campo, rutas, caja y riesgo en Colombia",
    version="0.1.0",
    lifespan=lifespan,
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
           POST /api/onboarding/negocios (registration publica).
    Applies to: pagos, creditos, jornadas, movimientos, dispositivos.
    """
    # Skip subscription check for these paths
    skip_paths = {
        "/api/health",
        "/api/inversionista/suscripcion",
        "/api/onboarding/negocios",
    }

    if request.url.path in skip_paths:
        return await call_next(request)

    # Only check write endpoints (POST, PUT, DELETE) and only in production
    env = os.getenv("DAILY_ENV", "test")
    if env in ("test", "development", "dev"):
        return await call_next(request)

    if request.method not in ("POST", "PUT", "DELETE"):
        return await call_next(request)

    # negocio_id SIEMPRE de la identidad autenticada (claims del JWT), nunca de
    # query params: un cuerpo/URL no debe poder elegir el tenant a verificar.
    authorization = request.headers.get("authorization", "")
    if not authorization.lower().startswith("bearer "):
        return await call_next(request)

    from src.auth.token import TokenError, decode_token

    try:
        claims = decode_token(authorization.split(" ", 1)[1].strip())
    except TokenError:
        # Token invalido/ausente: el endpoint aplica su propio 401. Sin
        # identidad no hay tenant que verificar.
        return await call_next(request)

    negocio_id = claims.get("negocio_id")
    if not negocio_id:
        return await call_next(request)

    from uuid import UUID as _UUID

    from src.database import SessionLocal
    from src.models import Negocio

    # Reusa el engine/thread-safe sessionmaker de la app; NO crea un engine
    # nuevo por request.
    db = SessionLocal()
    try:
        negocio = db.query(Negocio).filter(Negocio.id == _UUID(negocio_id)).first()
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

        if as_utc(negocio.paid_through_at) and as_utc(negocio.paid_through_at) < datetime.now(timezone.utc):
            return JSONResponse(
                status_code=403,
                content={
                    "detail": f"Suscripcion vencida el {negocio.paid_through_at.isoformat()}",
                    "code": "SUSCRIPCION_VENCIDA",
                },
            )

        return await call_next(request)
    except Exception:
        # Fail-closed: si no se puede verificar la suscripcion, no se procesa
        # la escritura (la indisponibilidad del control no se salta).
        return JSONResponse(
            status_code=503,
            content={
                "detail": "No se pudo verificar la suscripcion",
                "code": "SUSCRIPCION_INDISPONIBLE",
            },
        )
    finally:
        db.close()


app.include_router(negocio_router)
app.include_router(onboarding_router)
app.include_router(ruta_router)
app.include_router(cliente_router)
app.include_router(credito_router)
app.include_router(pago_router)
app.include_router(cobranza_router)
app.include_router(hoja_viva_router)
app.include_router(jornada_router)
app.include_router(movimiento_router)
app.include_router(dispositivo_router)
app.include_router(activacion_router)
app.include_router(mobile_router)
app.include_router(device_router)
app.include_router(reportes_router)
app.include_router(dashboard_router)
app.include_router(auth_router)
app.include_router(inversionista_router)
app.include_router(usuario_router)
app.include_router(audit_router)
app.include_router(llm_router)


@app.get("/api/health")
def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "daily-system-api"}
