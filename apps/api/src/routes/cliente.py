"""Cliente 360 — W2.

Contrato:
  POST   /api/clientes           — crear cliente            (clientes:gestionar)
  GET    /api/clientes           — listar con busqueda/filtros/paginacion
                                                           (clientes:ver)
  GET    /api/clientes/{id}      — detalle Cliente 360 con creditos/saldo/mora
                                                           (clientes:ver)
  PATCH  /api/clientes/{id}      — editar campos editables  (clientes:gestionar)

COBRADOR: clientes:ver scoped a su ruta via Credito (aislamiento derivado).
INVERSIONISTA: sin clientes:* -> 403 (no expone PII de clientes).
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from src.auth.context import RequestContext
from src.auth.deps import get_request_context
from src.database import get_db, get_db_transaction
from src.models import Cliente
from src.rbac import tiene_capability
from src.schemas import (
    Cliente360Response,
    ClienteCreate,
    ClienteListPage,
    ClienteResponse,
    ClienteUpdate,
)
from src.services import cliente_service

router = APIRouter(prefix="/api/clientes", tags=["clientes"])

WriteSession = Annotated[
    Session,
    Depends(get_db_transaction, scope="function"),
]


def _exigir_capability(ctx: RequestContext, capability: str) -> None:
    if not tiene_capability(ctx.role, capability):
        raise HTTPException(
            status_code=403,
            detail=f"No autorizado para {capability}",
        )


@router.post("", response_model=ClienteResponse, status_code=201)
def crear_cliente(
    data: ClienteCreate,
    db: WriteSession,
    ctx: RequestContext = Depends(get_request_context),
):
    _exigir_capability(ctx, "clientes:gestionar")
    cliente = cliente_service.crear_cliente(
        db=db,
        negocio_id=ctx.negocio_id,
        actor_id=ctx.user_id,
        data=data,
    )
    return ClienteResponse.model_validate(cliente)


@router.get("", response_model=ClienteListPage)
def listar_clientes(
    q: str | None = Query(default=None, max_length=100),
    tipo_documento: str | None = Query(default=None, max_length=20),
    identity_status: str | None = Query(default=None, max_length=20),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    _exigir_capability(ctx, "clientes:ver")
    return cliente_service.listar_clientes(
        db=db,
        negocio_id=ctx.negocio_id,
        role=ctx.role,
        route_id=ctx.route_id,
        search=q,
        tipo_documento=tipo_documento,
        identity_status=identity_status,
        limit=limit,
        offset=offset,
    )


@router.get("/{cliente_id}", response_model=Cliente360Response)
def obtener_cliente(
    cliente_id: UUID,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    _exigir_capability(ctx, "clientes:ver")
    return cliente_service.obtener_cliente_360(
        db=db,
        negocio_id=ctx.negocio_id,
        cliente_id=cliente_id,
        role=ctx.role,
        route_id=ctx.route_id,
    )


@router.patch("/{cliente_id}", response_model=ClienteResponse)
def editar_cliente(
    cliente_id: UUID,
    data: ClienteUpdate,
    db: WriteSession,
    ctx: RequestContext = Depends(get_request_context),
):
    _exigir_capability(ctx, "clientes:gestionar")

    cliente = db.query(Cliente).filter(
        Cliente.id == cliente_id,
        Cliente.negocio_id == ctx.negocio_id,
    ).first()
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    cliente = cliente_service.editar_cliente(
        db=db,
        negocio_id=ctx.negocio_id,
        cliente=cliente,
        actor_id=ctx.user_id,
        data=data,
    )
    return ClienteResponse.model_validate(cliente)
