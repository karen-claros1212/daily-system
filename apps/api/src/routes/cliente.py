from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import cast, String
from uuid import UUID

from src.database import get_db
from src.models import Cliente, Negocio
from src.schemas import ClienteCreate, ClienteResponse


def _uuid_eq(column, val: str | UUID):
    if isinstance(val, str):
        return column == UUID(val)
    return column == val

router = APIRouter(prefix="/api/clientes", tags=["clientes"])


@router.post("", response_model=ClienteResponse, status_code=201)
def crear_cliente(
    data: ClienteCreate,
    negocio_id: UUID,
    db: Session = Depends(get_db),
):
    """Crear un cliente para un negocio."""
    negocio = db.query(Negocio).filter(_uuid_eq(Negocio.id, negocio_id)).first()
    if not negocio:
        raise HTTPException(status_code=404, detail="Negocio no encontrado")

    cliente = Cliente(
        negocio_id=negocio_id,
        primer_apellido=data.primer_apellido,
        nombres=data.nombres,
        tipo_documento=data.tipo_documento,
        documento_normalizado=data.documento_normalizado,
        telefono_1=data.telefono_1,
        direccion=data.direccion,
        ciudad=data.ciudad,
    )
    db.add(cliente)
    db.commit()
    db.refresh(cliente)
    return ClienteResponse.model_validate(cliente)


@router.get("", response_model=list[ClienteResponse])
def listar_clientes(negocio_id: UUID, db: Session = Depends(get_db)):
    """Listar clientes de un negocio."""
    clientes = (
        db.query(Cliente)
        .filter(_uuid_eq(Cliente.negocio_id, negocio_id))
        .all()
    )
    return [ClienteResponse.model_validate(c) for c in clientes]


@router.get("/{cliente_id}", response_model=ClienteResponse)
def obtener_cliente(cliente_id: UUID, db: Session = Depends(get_db)):
    """Obtener un cliente por ID."""
    cliente = db.query(Cliente).filter(Cliente.id == cliente_id).first()
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    return ClienteResponse.model_validate(cliente)
