"""Créditos / Cartera — W3.

Contrato:
  POST   /api/creditos            — crear crédito            (creditos:gestionar)
  GET    /api/creditos            — listar read model paginado (creditos:ver)
  GET    /api/creditos/resumen    — agregados de cartera scoped (creditos:ver)
  GET    /api/creditos/{id}       — detalle con financiero     (creditos:ver)

Reglas:
  - ADMINISTRADOR: tenant-wide (ver + gestionar).
  - COBRADOR: solo su ruta activa; fuera de scope -> 404 (no revelar
    existencia); nunca crea desde el panel (POST -> 403).
  - INVERSIONISTA: read-only con PII minimizada (cliente_nombre/cliente_id
    en None); sin Cliente360; POST -> 403.

El read model reutiliza hoja_viva_service.resumen_creditos (autoridad unica
de saldo/mora/pico/cuotas_pagadas, compartida con Cliente360): nunca se
duplica calculo financiero en el panel.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from src.auth.context import RequestContext
from src.auth.deps import get_request_context
from src.database import get_db, get_db_transaction
from src.models import Cliente, Negocio, Ruta
from src.rbac import tiene_capability
from src.schemas import (
    CreditoCreate,
    CreditoDetailResponse,
    CreditoListPage,
    CreditoResponse,
    CreditoResumenResponse,
)
from src.services import credito_service

router = APIRouter(prefix="/api/creditos", tags=["creditos"])

WriteSession = Annotated[
    Session,
    Depends(get_db_transaction, scope="function"),
]


def _uuid_eq(column, val: str | UUID):
    if isinstance(val, str):
        return column == UUID(val)
    return column == val


def _exigir_capability(ctx: RequestContext, capability: str) -> None:
    if not tiene_capability(ctx.role, capability):
        raise HTTPException(
            status_code=403,
            detail=f"No autorizado para {capability}",
        )


@router.post("", response_model=CreditoResponse, status_code=201)
def crear_credito(
    data: CreditoCreate,
    db: WriteSession,
    ctx: RequestContext = Depends(get_request_context),
):
    _exigir_capability(ctx, "creditos:gestionar")

    negocio = db.query(Negocio).filter(_uuid_eq(Negocio.id, ctx.negocio_id)).first()
    if not negocio:
        raise HTTPException(status_code=404, detail="Negocio no encontrado")

    ruta = db.query(Ruta).filter(
        _uuid_eq(Ruta.id, data.ruta_id),
        _uuid_eq(Ruta.negocio_id, ctx.negocio_id),
    ).first()
    if not ruta:
        raise HTTPException(status_code=404, detail="Ruta no encontrada")

    cliente = db.query(Cliente).filter(
        _uuid_eq(Cliente.id, data.cliente_id),
        _uuid_eq(Cliente.negocio_id, ctx.negocio_id),
    ).first()
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    credito = credito_service.crear_credito(
        db=db,
        negocio_id=ctx.negocio_id,
        actor_id=ctx.user_id,
        data=data,
    )
    return CreditoResponse.model_validate(credito)


@router.get("", response_model=CreditoListPage)
def listar_creditos(
    q: str | None = Query(default=None, max_length=100),
    estado: str | None = Query(default=None, max_length=20),
    ruta_id: UUID | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    sort: str = Query(default="fecha_inicio", max_length=20),
    order: str = Query(default="desc", max_length=4),
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    _exigir_capability(ctx, "creditos:ver")
    return credito_service.listar_creditos(
        db=db,
        negocio_id=ctx.negocio_id,
        role=ctx.role,
        route_id=ctx.route_id,
        search=q,
        estado=estado,
        ruta_id=ruta_id,
        limit=limit,
        offset=offset,
        sort=sort,
        order=order,
    )


@router.get("/resumen", response_model=CreditoResumenResponse)
def resumen_cartera(
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    _exigir_capability(ctx, "creditos:ver")
    return credito_service.resumen_cartera(
        db=db,
        negocio_id=ctx.negocio_id,
        role=ctx.role,
        route_id=ctx.route_id,
    )


@router.get("/{credito_id}", response_model=CreditoDetailResponse)
def obtener_credito(
    credito_id: UUID,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    _exigir_capability(ctx, "creditos:ver")
    return credito_service.obtener_credito_detalle(
        db=db,
        negocio_id=ctx.negocio_id,
        credito_id=credito_id,
        role=ctx.role,
        route_id=ctx.route_id,
    )
