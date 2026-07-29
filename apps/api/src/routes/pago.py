from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import cast, String
from uuid import UUID

from src.database import get_db
from src.models import Pago, Credito, Negocio
from src.schemas import PagoCreate, PagoResponse


def _uuid_eq(column, val: str | UUID):
    if isinstance(val, str):
        return column == UUID(val)
    return column == val

router = APIRouter(prefix="/api/pagos", tags=["pagos"])


@router.post("", response_model=PagoResponse, status_code=201)
def registrar_pago(
    data: PagoCreate,
    negocio_id: UUID,
    db: Session = Depends(get_db),
):
    """
    Registrar un pago (append-only).

    La clave_idempotencia garantiza que un reenvío no duplica el pago.
    UNIQUE(negocio_id, clave_idempotencia) en la base de datos.
    """
    negocio = db.query(Negocio).filter(_uuid_eq(Negocio.id, negocio_id)).first()
    if not negocio:
        raise HTTPException(status_code=404, detail="Negocio no encontrado")

    credito = db.query(Credito).filter(
        _uuid_eq(Credito.id, data.credito_id),
        _uuid_eq(Credito.negocio_id, negocio_id),
    ).first()
    if not credito:
        raise HTTPException(status_code=404, detail="Crédito no encontrado")

    existing = db.query(Pago).filter(
        _uuid_eq(Pago.negocio_id, negocio_id),
        Pago.clave_idempotencia == data.clave_idempotencia,
    ).first()
    if existing:
        return PagoResponse.model_validate(existing)

    pago = Pago(
        negocio_id=negocio_id,
        credito_id=data.credito_id,
        jornada_id=data.jornada_id,
        tipo="PAYMENT",
        monto=data.monto,
        clave_idempotencia=data.clave_idempotencia,
        nota=data.nota,
    )
    db.add(pago)
    db.commit()
    db.refresh(pago)
    return PagoResponse.model_validate(pago)


@router.get("", response_model=list[PagoResponse])
def listar_pagos(ruta_id: UUID | None = None, db: Session = Depends(get_db)):
    """Listar pagos."""
    pagos = db.query(Pago).all()
    return [PagoResponse.model_validate(p) for p in pagos]
