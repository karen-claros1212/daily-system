"""Reportes Premium — endpoints de reporte explícitos y typed."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from src.database import get_db
from src.auth.deps import get_request_context
from src.auth.context import RequestContext
from src.rbac import tiene_capability
from src.services.reportes_service import (
    aging_reporte,
    movimientos_reporte,
    recaudo_diario,
    resumen_reporte,
    rutas_reporte,
)

router = APIRouter(prefix="/api/reportes", tags=["reportes"])


def _check_reportes(ctx: RequestContext):
    if not tiene_capability(ctx.role, "reportes:ver"):
        raise HTTPException(status_code=403, detail="Forbidden: sin capability de reportes")


@router.get("/resumen")
def resumen_endpoint(
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
    periodo: str = Query("hoy", description="hoy|7d|30d|custom"),
    fecha_inicio: str | None = Query(None, description="YYYY-MM-DD (custom)"),
    fecha_fin: str | None = Query(None, description="YYYY-MM-DD (custom)"),
):
    """Resumen financiero del periodo."""
    _check_reportes(ctx)
    return resumen_reporte(
        db,
        negocio_id=ctx.negocio_id,
        role=ctx.role,
        periodo=periodo,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
    )


@router.get("/recaudo")
def recaudo_endpoint(
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
    periodo: str = Query("7d", description="hoy|7d|30d|custom"),
    fecha_inicio: str | None = Query(None, description="YYYY-MM-DD (custom)"),
    fecha_fin: str | None = Query(None, description="YYYY-MM-DD (custom)"),
):
    """Serie diaria de recaudo (PAYMENT - REVERSAL)."""
    _check_reportes(ctx)
    return recaudo_diario(
        db,
        negocio_id=ctx.negocio_id,
        role=ctx.role,
        periodo=periodo,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
    )


@router.get("/aging")
def aging_endpoint(
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    """Distribución de aging por bucket."""
    _check_reportes(ctx)
    return aging_reporte(
        db,
        negocio_id=ctx.negocio_id,
        role=ctx.role,
    )


@router.get("/rutas")
def rutas_endpoint(
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
    periodo: str = Query("hoy", description="hoy|7d|30d|custom"),
    fecha_inicio: str | None = Query(None, description="YYYY-MM-DD (custom)"),
    fecha_fin: str | None = Query(None, description="YYYY-MM-DD (custom)"),
):
    """Rendimiento agregado por ruta."""
    _check_reportes(ctx)
    return rutas_reporte(
        db,
        negocio_id=ctx.negocio_id,
        role=ctx.role,
        periodo=periodo,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
    )


@router.get("/movimientos")
def movimientos_endpoint(
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
    periodo: str = Query("hoy", description="hoy|7d|30d|custom"),
    fecha_inicio: str | None = Query(None, description="YYYY-MM-DD (custom)"),
    fecha_fin: str | None = Query(None, description="YYYY-MM-DD (custom)"),
):
    """Breakdown de gastos/movimientos por tipo y naturaleza."""
    _check_reportes(ctx)
    return movimientos_reporte(
        db,
        negocio_id=ctx.negocio_id,
        role=ctx.role,
        periodo=periodo,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
    )
