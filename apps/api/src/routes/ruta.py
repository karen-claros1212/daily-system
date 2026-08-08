from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.auth.context import RequestContext
from src.auth.deps import get_request_context
from src.database import get_db, get_db_transaction
from src.models import Negocio, Ruta
from src.schemas import RutaCreate, RutaResponse


def _uuid_eq(column, val: str | UUID):
    if isinstance(val, str):
        return column == UUID(val)
    return column == val


router = APIRouter(prefix="/api/rutas", tags=["rutas"])

WriteSession = Annotated[
    Session,
    Depends(get_db_transaction, scope="function"),
]


@router.post("", response_model=RutaResponse, status_code=201)
def crear_ruta(
    data: RutaCreate,
    db: WriteSession,
    ctx: RequestContext = Depends(get_request_context),
):
    negocio = db.query(Negocio).filter(_uuid_eq(Negocio.id, ctx.negocio_id)).first()
    if not negocio:
        raise HTTPException(status_code=404, detail="Negocio no encontrado")

    ruta = Ruta(
        negocio_id=ctx.negocio_id,
        nombre=data.nombre,
        cobrador_id=data.cobrador_id,
    )
    db.add(ruta)
    db.flush()
    db.refresh(ruta)
    return RutaResponse.model_validate(ruta)


@router.get("", response_model=list[RutaResponse])
def listar_rutas(
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    q = db.query(Ruta).filter(_uuid_eq(Ruta.negocio_id, ctx.negocio_id))
    if ctx.is_cobrador():
        q = q.filter(_uuid_eq(Ruta.id, ctx.route_id))
    return [RutaResponse.model_validate(r) for r in q.filter(Ruta.activa == 1).all()]


@router.get("/{ruta_id}", response_model=RutaResponse)
def obtener_ruta(
    ruta_id: UUID,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    if ctx.is_cobrador() and not ctx.has_route(ruta_id):
        raise HTTPException(status_code=404, detail="Ruta no encontrada")
    ruta = db.query(Ruta).filter(
        _uuid_eq(Ruta.id, ruta_id),
        _uuid_eq(Ruta.negocio_id, ctx.negocio_id),
    ).first()
    if not ruta:
        raise HTTPException(status_code=404, detail="Ruta no encontrada")
    return RutaResponse.model_validate(ruta)
