from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.auth.context import RequestContext
from src.auth.deps import get_request_context
from src.database import get_db, get_db_transaction
from src.models import Negocio
from src.schemas import NegocioCreate, NegocioResponse


def _uuid_eq(column, val: str | UUID):
    if isinstance(val, str):
        return column == UUID(val)
    return column == val


router = APIRouter(prefix="/api/negocios", tags=["negocios"])

WriteSession = Annotated[
    Session,
    Depends(get_db_transaction, scope="function"),
]


@router.post("", response_model=NegocioResponse, status_code=201)
def crear_negocio(
    data: NegocioCreate,
    db: WriteSession,
):
    negocio = Negocio(nombre=data.nombre, nit=data.nit)
    db.add(negocio)
    db.flush()
    db.refresh(negocio)
    return NegocioResponse.model_validate(negocio)


@router.get("", response_model=list[NegocioResponse])
def listar_negocios(
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_request_context),
):
    """Listar negocios scoped al tenant del contexto (G5: sin fuga cross-tenant)."""
    if ctx.negocio_id is None:
        return []
    negocio = db.query(Negocio).filter(_uuid_eq(Negocio.id, ctx.negocio_id)).first()
    return [NegocioResponse.model_validate(negocio)] if negocio else []


@router.get("/{nid}", response_model=NegocioResponse)
def obtener_negocio(
    nid: UUID,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_request_context),
):
    """Detalle de negocio scoped al tenant del contexto (G5: id ajeno = 404)."""
    if ctx.negocio_id is None or nid != ctx.negocio_id:
        raise HTTPException(status_code=404, detail="Negocio no encontrado")
    negocio = db.query(Negocio).filter(_uuid_eq(Negocio.id, nid)).first()
    if not negocio:
        raise HTTPException(status_code=404, detail="Negocio no encontrado")
    return NegocioResponse.model_validate(negocio)
