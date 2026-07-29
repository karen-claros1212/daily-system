"""FastAPI application for Daily System."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.routes.negocio import router as negocio_router
from src.routes.ruta import router as ruta_router
from src.routes.cliente import router as cliente_router
from src.routes.credito import router as credito_router
from src.routes.pago import router as pago_router
from src.routes.hoja_viva import router as hoja_viva_router

app = FastAPI(
    title="Daily System API",
    description="Plataforma local-first para crédito diario, cobranza de campo, rutas, caja y riesgo en Colombia",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:7101", "http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(negocio_router)
app.include_router(ruta_router)
app.include_router(cliente_router)
app.include_router(credito_router)
app.include_router(pago_router)
app.include_router(hoja_viva_router)


@app.get("/api/health")
def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "daily-system-api"}
