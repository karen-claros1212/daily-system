from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import cast, String
from uuid import UUID

from src.database import get_db
from src.models import Negocio
from src.schemas import NegocioCreate, NegocioResponse


def _uuid_eq(column, val: str | UUID):
    if isinstance(val, str):
        return column == UUID(val)
    return column == val

router = APIRouter(prefix="/api/negocios", tags=["negocios"])


@router.post("", response_model=NegocioResponse, status_code=201)
def crear_negocio(data: NegocioCreate, db: Session = Depends(get_db)):
    """Crear un nuevo negocio (empresa cliente)."""
    negocio = Negocio(nombre=data.nombre, nit=data.nit)
    db.add(negocio)
    db.commit()
    db.refresh(negocio)
    return NegocioResponse.model_validate(negocio)


@router.get("", response_model=list[NegocioResponse])
def listar_negocios(db: Session = Depends(get_db)):
    """Listar todos los negocios."""
    negocios = db.query(Negocio).all()
    return [NegocioResponse.model_validate(n) for n in negocios]


@router.get("/{negocio_id}", response_model=NegocioResponse)
def obtener_negocio(negocio_id: UUID, db: Session = Depends(get_db)):
    """Obtener un negocio por ID."""
    negocio = db.query(Negocio).filter(_uuid_eq(Negocio.id, negocio_id)).first()
    if not negocio:
        raise HTTPException(status_code=404, detail="Negocio no encontrado")
    return NegocioResponse.model_validate(negocio)
