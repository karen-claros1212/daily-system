"""Payment routes — thin router layer.

Receives schemas, gets RequestContext, calls payment_service,
converts domain errors to HTTP responses.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from uuid import UUID

from src.database import get_db
from src.schemas import PagoCreate, PagoReversalCreate, PagoResponse
from src.auth.deps import get_request_context
from src.auth.context import RequestContext
from src.services.payment_service import (
    PaymentError,
    PaymentNotFoundError,
    PaymentRouteError,
    PaymentIdempotencyError,
    PaymentReversalError,
    register_payment,
    get_payment,
    list_payments,
    reverse_payment,
)

router = APIRouter(prefix="/api/pagos", tags=["pagos"])


@router.post("", response_model=PagoResponse, status_code=201)
def registrar_pago(
    data: PagoCreate,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    try:
        pago = register_payment(db, data.model_dump(), ctx)
        return PagoResponse.model_validate(pago)
    except PaymentRouteError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except PaymentIdempotencyError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except PaymentError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{pago_id}/reversar", response_model=PagoResponse, status_code=201)
def reversar_pago(
    pago_id: UUID,
    data: PagoReversalCreate,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    try:
        reversal = reverse_payment(db, pago_id, data.model_dump(), ctx)
        return PagoResponse.model_validate(reversal)
    except PaymentNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PaymentReversalError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PaymentIdempotencyError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except PaymentRouteError as e:
        raise HTTPException(status_code=403, detail=str(e))


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
        raise HTTPException(status_code=404, detail=str(e))
