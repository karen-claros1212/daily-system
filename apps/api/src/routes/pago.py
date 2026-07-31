"""Payment routes — thin router layer.

Receives schemas, gets RequestContext, calls payment_service,
converts domain errors to HTTP responses.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.auth.context import RequestContext
from src.auth.deps import get_request_context
from src.database import get_db, get_db_transaction
from src.schemas import PagoCreate, PagoResponse, PagoReversalCreate
from src.services.payment_service import (
    PaymentError,
    PaymentIdempotencyError,
    PaymentNotFoundError,
    PaymentReversalError,
    PaymentRouteError,
    get_payment,
    list_payments,
    register_payment,
    reverse_payment,
)

router = APIRouter(prefix="/api/pagos", tags=["pagos"])

WriteSession = Annotated[
    Session,
    Depends(get_db_transaction, scope="function"),
]


@router.post("", response_model=PagoResponse, status_code=201)
def registrar_pago(
    data: PagoCreate,
    db: WriteSession,
    ctx: RequestContext = Depends(get_request_context),
):
    try:
        pago = register_payment(db, data.model_dump(), ctx)
        return PagoResponse.model_validate(pago)
    except PaymentRouteError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    except PaymentIdempotencyError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except PaymentError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("/{pago_id}/reversar", response_model=PagoResponse, status_code=201)
def reversar_pago(
    pago_id: UUID,
    data: PagoReversalCreate,
    db: WriteSession,
    ctx: RequestContext = Depends(get_request_context),
):
    try:
        reversal = reverse_payment(db, pago_id, data.model_dump(), ctx)
        return PagoResponse.model_validate(reversal)
    except PaymentNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except PaymentReversalError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except PaymentIdempotencyError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except PaymentRouteError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e


@router.get("", response_model=list[PagoResponse])
def listar_pagos(
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    pagos = list_payments(db, ctx)
    return [PagoResponse.model_validate(p) for p in pagos]


@router.get("/{pago_id}", response_model=PagoResponse)
def obtener_pago(
    pago_id: UUID,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    try:
        pago = get_payment(db, pago_id, ctx)
        return PagoResponse.model_validate(pago)
    except PaymentNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
