from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import cast, String
from uuid import UUID

from src.database import get_db
from src.models import Ruta, Negocio, Usuario
from src.schemas import RutaCreate, RutaResponse


def _uuid_eq(column, val: str | UUID):
    """Compare UUID column with string or UUID value (works in SQLite and PostgreSQL)."""
    if isinstance(val, str):
        return column == UUID(val)
    return column == val

router = APIRouter(prefix="/api/rutas", tags=["rutas"])


@router.post("", response_model=RutaResponse, status_code=201)
def crear_ruta(
    data: RutaCreate,
    negocio_id: UUID,
    db: Session = Depends(get_db),
):
    """Crear una ruta para un negocio."""
    negocio = db.query(Negocio).filter(_uuid_eq(Negocio.id, negocio_id)).first()
    if not negocio:
        raise HTTPException(status_code=404, detail="Negocio no encontrado")

    ruta = Ruta(
        negocio_id=negocio_id,
        nombre=data.nombre,
        cobrador_id=data.cobrador_id,
    )
    db.add(ruta)
    db.commit()
    db.refresh(ruta)
    return RutaResponse.model_validate(ruta)


@router.get("", response_model=list[RutaResponse])
def listar_rutas(negocio_id: UUID, db: Session = Depends(get_db)):
    """Listar rutas de un negocio."""
    rutas = (
        db.query(Ruta)
        .filter(_uuid_eq(Ruta.negocio_id, negocio_id), Ruta.activa == 1)
        .all()
    )
    return [RutaResponse.model_validate(r) for r in rutas]


@router.get("/{ruta_id}", response_model=RutaResponse)
def obtener_ruta(ruta_id: UUID, db: Session = Depends(get_db)):
    """Obtener una ruta por ID."""
    ruta = db.query(Ruta).filter(Ruta.id == ruta_id).first()
    if not ruta:
        raise HTTPException(status_code=404, detail="Ruta no encontrada")
    return RutaResponse.model_validate(ruta)
