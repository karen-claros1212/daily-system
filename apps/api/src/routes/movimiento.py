"""Movimiento routes — append-only caja movements."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from uuid import UUID

from src.database import get_db, get_db_transaction
from src.schemas import MovimientoCreate, MovimientoResponse
from src.auth.deps import get_request_context
from src.auth.context import RequestContext
from src.services.movimiento_service import (
    register_movimiento,
    list_movimientos,
    get_movimiento,
    MovimientoNotFoundError,
    MovimientoIdempotencyError,
    MovimientoTipoInvalido,
    MovimientoNaturalezaInvalida,
    MovimientoJornadaError,
)

router = APIRouter(prefix="/api/movimientos", tags=["movimientos"])

WriteSession = Annotated[
    Session,
    Depends(get_db_transaction, scope="function"),
]


@router.post("", response_model=MovimientoResponse, status_code=201)
def registrar_movimiento(
    data: MovimientoCreate,
    db: WriteSession,
    ctx: RequestContext = Depends(get_request_context),
):
    try:
        movimiento = register_movimiento(db, data.model_dump(), ctx)
        return MovimientoResponse.model_validate(movimiento)
    except MovimientoJornadaError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except MovimientoIdempotencyError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except MovimientoTipoInvalido as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except MovimientoNaturalezaInvalida as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("", response_model=list[MovimientoResponse])
def listar_movimientos(
    jornada_id: UUID,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    try:
        movimientos = list_movimientos(db, jornada_id, ctx)
        return [MovimientoResponse.model_validate(m) for m in movimientos]
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.get("/{movimiento_id}", response_model=MovimientoResponse)
def obtener_movimiento(
    movimiento_id: UUID,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    try:
        movimiento = get_movimiento(db, movimiento_id, ctx)
        return MovimientoResponse.model_validate(movimiento)
    except MovimientoNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
