from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.auth.context import RequestContext
from src.auth.deps import get_request_context
from src.database import get_db, get_db_transaction
from src.models import Cliente, Credito
from src.schemas import ClienteCreate, ClienteResponse


def _uuid_eq(column, val: str | UUID):
    if isinstance(val, str):
        return column == UUID(val)
    return column == val


router = APIRouter(prefix="/api/clientes", tags=["clientes"])

WriteSession = Annotated[
    Session,
    Depends(get_db_transaction, scope="function"),
]


@router.post("", response_model=ClienteResponse, status_code=201)
def crear_cliente(
    data: ClienteCreate,
    db: WriteSession,
    ctx: RequestContext = Depends(get_request_context),
):
    cliente = Cliente(
        negocio_id=ctx.negocio_id,
        primer_apellido=data.primer_apellido,
        nombres=data.nombres,
        tipo_documento=data.tipo_documento,
        documento_normalizado=data.documento_normalizado,
        telefono_1=data.telefono_1,
        ciudad=data.ciudad,
        identity_status="PROVISIONAL",
    )
    db.add(cliente)
    db.flush()
    db.refresh(cliente)
    return ClienteResponse.model_validate(cliente)


@router.get("", response_model=list[ClienteResponse])
def listar_clientes(
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    q = db.query(Cliente).filter(
        _uuid_eq(Cliente.negocio_id, ctx.negocio_id)
    )
    if ctx.is_cobrador():
        q = q.join(
            Credito,
            _uuid_eq(Credito.cliente_id, Cliente.id),
        ).filter(
            _uuid_eq(Credito.ruta_id, ctx.route_id),
        ).distinct()
    clientes = q.all()
    return [ClienteResponse.model_validate(c) for c in clientes]


@router.get("/{cliente_id}", response_model=ClienteResponse)
def obtener_cliente(
    cliente_id: UUID,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    cliente = db.query(Cliente).filter(
        _uuid_eq(Cliente.id, cliente_id),
        _uuid_eq(Cliente.negocio_id, ctx.negocio_id),
    ).first()
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    return ClienteResponse.model_validate(cliente)
