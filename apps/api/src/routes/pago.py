from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from uuid import UUID

from src.database import get_db
from src.models import Pago, Credito, Negocio
from src.schemas import PagoCreate, PagoResponse
from src.auth.deps import get_request_context
from src.auth.context import RequestContext


def _uuid_eq(column, val: str | UUID):
    if isinstance(val, str):
        return column == UUID(val)
    return column == val


router = APIRouter(prefix="/api/pagos", tags=["pagos"])


@router.post("", response_model=PagoResponse, status_code=201)
def registrar_pago(
    data: PagoCreate,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    negocio_id = ctx.negocio_id

    negocio = db.query(Negocio).filter(_uuid_eq(Negocio.id, negocio_id)).first()
    if not negocio:
        raise HTTPException(status_code=404, detail="Negocio no encontrado")

    credito = db.query(Credito).filter(
        _uuid_eq(Credito.id, data.credito_id),
        _uuid_eq(Credito.negocio_id, negocio_id),
    ).first()
    if not credito:
        raise HTTPException(status_code=404, detail="Crédito no encontrado")

    if ctx.is_cobrador() and not _uuid_eq(Credito.ruta_id, ctx.route_id):
        raise HTTPException(status_code=403, detail="El crédito no pertenece a tu ruta")

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
def listar_pagos(
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    q = db.query(Pago).filter(_uuid_eq(Pago.negocio_id, ctx.negocio_id))
    if ctx.is_cobrador():
        q = q.join(Credito).filter(_uuid_eq(Credito.ruta_id, ctx.route_id))
    return [PagoResponse.model_validate(p) for p in q.all()]
