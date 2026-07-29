from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import cast, String
from uuid import UUID

from src.database import get_db
from src.models import Credito, Negocio, Ruta, Cliente
from src.schemas import CreditoCreate, CreditoResponse


def _uuid_eq(column, val: str | UUID):
    if isinstance(val, str):
        return column == UUID(val)
    return column == val

router = APIRouter(prefix="/api/creditos", tags=["creditos"])


@router.post("", response_model=CreditoResponse, status_code=201)
def crear_credito(
    data: CreditoCreate,
    negocio_id: UUID,
    db: Session = Depends(get_db),
):
    """
    Crear un crédito.

    total = cuota × n_cuotas (verificado por CheckConstraint)
    """
    negocio = db.query(Negocio).filter(_uuid_eq(Negocio.id, negocio_id)).first()
    if not negocio:
        raise HTTPException(status_code=404, detail="Negocio no encontrado")

    ruta = db.query(Ruta).filter(_uuid_eq(Ruta.id, data.ruta_id)).first()
    if not ruta:
        raise HTTPException(status_code=404, detail="Ruta no encontrada")

    cliente = db.query(Cliente).filter(_uuid_eq(Cliente.id, data.cliente_id)).first()
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    total = data.cuota * data.n_cuotas
    credito = Credito(
        negocio_id=negocio_id,
        cliente_id=data.cliente_id,
        ruta_id=data.ruta_id,
        cuota=data.cuota,
        n_cuotas=data.n_cuotas,
        monto=data.monto,
        total=total,
        periodicidad=data.periodicidad,
        fecha_inicio=data.fecha_inicio,
    )
    db.add(credito)
    db.commit()
    db.refresh(credito)
    return CreditoResponse.model_validate(credito)


@router.get("", response_model=list[CreditoResponse])
def listar_creditos(ruta_id: UUID | None = None, db: Session = Depends(get_db)):
    """Listar créditos, opcionalmente filtrados por ruta."""
    query = db.query(Credito)
    if ruta_id:
        query = query.filter(_uuid_eq(Credito.ruta_id, ruta_id))
    creditos = query.all()
    return [CreditoResponse.model_validate(c) for c in creditos]


@router.get("/{credito_id}", response_model=CreditoResponse)
def obtener_credito(credito_id: UUID, db: Session = Depends(get_db)):
    """Obtener un crédito por ID."""
    credito = db.query(Credito).filter(Credito.id == credito_id).first()
    if not credito:
        raise HTTPException(status_code=404, detail="Crédito no encontrado")
    return CreditoResponse.model_validate(credito)
