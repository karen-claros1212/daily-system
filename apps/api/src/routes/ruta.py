"""Rutas / Cobradores — W4.

Contrato:
  POST   /api/rutas                     — crear ruta (rutas:crear, SOLO ADMIN)
  GET    /api/rutas                     — read model paginado (rutas:ver|ruta:ver)
  GET    /api/rutas/resumen             — conteos por estado scoped (mismo gate)
  GET    /api/rutas/{ruta_id}           — detalle (rutas:ver|ruta:ver)
  PATCH  /api/rutas/{ruta_id}/reasignar — S4 R1→R2 mismo cobrador (rutas:reasignar,
                                         SOLO ADMIN)

Reglas:
  - ADMINISTRADOR: tenant-wide (ver + crear + reasignar).
  - COBRADOR: solo su ruta activa; fuera de scope -> 404 (no revelar existencia).
  - INVERSIONISTA: read-only (rutas:ver), PII sin ampliar; POST/PATCH -> 403.
  - Conflictos de dominio -> 409 (duplicado de nombre, única activa por cobrador).

La lógica vive en src/services/ruta_service.py (reutilizable y testeada).
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from src.auth.context import RequestContext
from src.auth.deps import get_request_context
from src.database import get_db, get_db_transaction
from src.models import Negocio
from src.rbac import tiene_capability
from src.schemas import (
    RutaCreate,
    RutaListPage,
    RutaReasignarRequest,
    RutaReasignarResponse,
    RutaResumenResponse,
    RutaResponse,
)
from src.services import ruta_service


def _uuid_eq(column, val: str | UUID):
    if isinstance(val, str):
        return column == UUID(val)
    if isinstance(val, UUID):
        return column == val
    return column == val


router = APIRouter(prefix="/api/rutas", tags=["rutas"])

WriteSession = Annotated[
    Session,
    Depends(get_db_transaction, scope="function"),
]


def _exigir_cualquiera(ctx: RequestContext, *caps: str) -> None:
    if not any(tiene_capability(ctx.role, cap) for cap in caps):
        raise HTTPException(
            status_code=403,
            detail=f"No autorizado para {' | '.join(caps)}",
        )


@router.post("", response_model=RutaResponse, status_code=201)
def crear_ruta(
    data: RutaCreate,
    db: WriteSession,
    ctx: RequestContext = Depends(get_request_context),
):
    # Creación de rutas es exclusiva del ADMINISTRADOR: el cobrador no puede
    # asignarse rutas ni crear rutas con otro cobrador a cargo.
    if not tiene_capability(ctx.role, "rutas:crear"):
        raise HTTPException(
            status_code=403,
            detail="Solo el administrador puede crear rutas",
        )

    negocio = db.query(Negocio).filter(_uuid_eq(Negocio.id, ctx.negocio_id)).first()
    if not negocio:
        raise HTTPException(status_code=404, detail="Negocio no encontrado")

    return ruta_service.crear_ruta(
        db=db,
        negocio_id=ctx.negocio_id,
        actor_id=ctx.user_id,
        data=data,
    )


@router.get("", response_model=RutaListPage)
def listar_rutas(
    q: str | None = Query(default=None, max_length=100),
    activa: int | None = Query(default=None, ge=0, le=1),
    cobrador_id: UUID | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    sort: str = Query(default="creado_el", max_length=20),
    order: str = Query(default="desc", max_length=4),
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    _exigir_cualquiera(ctx, "rutas:ver", "ruta:ver")
    return ruta_service.listar_rutas(
        db=db,
        negocio_id=ctx.negocio_id,
        role=ctx.role,
        route_id=ctx.route_id,
        search=q,
        activa=activa,
        cobrador_id=cobrador_id,
        limit=limit,
        offset=offset,
        sort=sort,
        order=order,
    )


@router.get("/resumen", response_model=RutaResumenResponse)
def resumen_rutas(
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    _exigir_cualquiera(ctx, "rutas:ver", "ruta:ver")
    return ruta_service.resumen_rutas(
        db=db,
        negocio_id=ctx.negocio_id,
        role=ctx.role,
        route_id=ctx.route_id,
    )


@router.get("/{ruta_id}", response_model=RutaResponse)
def obtener_ruta(
    ruta_id: UUID,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    _exigir_cualquiera(ctx, "rutas:ver", "ruta:ver")
    return ruta_service.obtener_ruta(
        db=db,
        negocio_id=ctx.negocio_id,
        role=ctx.role,
        route_id=ctx.route_id,
        ruta_id=ruta_id,
    )


@router.patch("/{ruta_id}/reasignar", response_model=RutaReasignarResponse, status_code=200)
def reasignar_ruta(
    ruta_id: UUID,
    data: RutaReasignarRequest,
    db: WriteSession,
    ctx: RequestContext = Depends(get_request_context),
):
    """S4 — Reasignación productiva R1→R2 (ver ruta_service.reasignar_ruta)."""
    _exigir_cualquiera(ctx, "rutas:reasignar")
    return ruta_service.reasignar_ruta(
        db=db,
        negocio_id=ctx.negocio_id,
        actor_id=ctx.user_id,
        ruta_id=ruta_id,
        data=data,
    )
