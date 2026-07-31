"""Jornada routes — open, close, sync, caja calculation."""

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.auth.context import RequestContext
from src.auth.deps import get_request_context
from src.database import get_db, get_db_transaction
from src.schemas import (
    CadenaCajaResponse,
    JornadaCierreCreate,
    JornadaCierreResponse,
    JornadaCreate,
    JornadaResponse,
    JornadaSyncResponse,
)
from src.services.caja_service import calcular_cadena_caja
from src.services.jornada_service import (
    JornadaAlreadyClosed,
    JornadaClosedError,
    JornadaError,
    JornadaInvalidBase,
    JornadaNotFoundError,
    JornadaRoleError,
    JornadaRouteError,
    cerrar_jornada,
    get_active_jornada,
    get_jornada,
    open_jornada,
    preparar_siguiente_jornada,
    sincronizar_cierre,
)

router = APIRouter(prefix="/api/jornadas", tags=["jornadas"])

WriteSession = Annotated[
    Session,
    Depends(get_db_transaction, scope="function"),
]


@router.post("", response_model=JornadaResponse, status_code=201)
def abrir_jornada(
    data: JornadaCreate,
    db: WriteSession,
    ctx: RequestContext = Depends(get_request_context),
):
    try:
        jornada = open_jornada(
            db,
            ruta_id=data.ruta_id,
            negocio_id=ctx.negocio_id,
            opening_base=data.opening_base,
            ctx=ctx,
            clave_idempotencia=data.clave_idempotencia,
        )
        return JornadaResponse.model_validate(jornada)
    except JornadaRouteError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except JornadaRoleError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    except JornadaInvalidBase as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except (JornadaClosedError, JornadaAlreadyClosed) as e:
        raise HTTPException(status_code=409, detail=str(e)) from e


@router.get("", response_model=list[JornadaResponse])
def listar_jornadas(
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    from src.models import Jornada
    from src.services.jornada_service import _uuid_eq

    q = db.query(Jornada).filter(
        _uuid_eq(Jornada.negocio_id, ctx.negocio_id),
    )
    if ctx.is_cobrador():
        q = q.filter(_uuid_eq(Jornada.ruta_id, ctx.route_id))

    return [JornadaResponse.model_validate(j) for j in q.all()]


@router.get("/active", response_model=JornadaResponse)
def obtener_jornada_activa(
    ruta_id: UUID,
    fecha: date | None = None,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    jornada = get_active_jornada(
        db,
        ruta_id=ruta_id,
        negocio_id=ctx.negocio_id,
        fecha=fecha,
    )
    if not jornada:
        raise HTTPException(status_code=404, detail="No hay jornada activa para esta ruta")
    return JornadaResponse.model_validate(jornada)


@router.get("/{jornada_id}", response_model=JornadaResponse)
def obtener_jornada(
    jornada_id: UUID,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    try:
        jornada = get_jornada(db, jornada_id, ctx)
        return JornadaResponse.model_validate(jornada)
    except JornadaNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("/{jornada_id}/cerrar", response_model=JornadaCierreResponse)
def cerrar_jornada_endpoint(
    jornada_id: UUID,
    data: JornadaCierreCreate,
    db: WriteSession,
    ctx: RequestContext = Depends(get_request_context),
):
    try:
        result = cerrar_jornada(db, jornada_id, data.model_dump(), ctx)
        return result
    except JornadaNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except (JornadaClosedError, JornadaAlreadyClosed) as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except JornadaError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/{jornada_id}/sincronizar", response_model=JornadaSyncResponse)
def sincronizar_cierre_endpoint(
    jornada_id: UUID,
    db: WriteSession,
    snapshot: dict,
    snapshot_hash: str,
    ctx: RequestContext = Depends(get_request_context),
):
    try:
        result = sincronizar_cierre(db, jornada_id, snapshot, snapshot_hash, ctx)
        return result
    except JornadaNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except JornadaError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/{jornada_id}/caja", response_model=CadenaCajaResponse)
def obtener_caja(
    jornada_id: UUID,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    try:
        jornada = get_jornada(db, jornada_id, ctx)
    except JornadaNotFoundError as e:
        raise HTTPException(status_code=404, detail="Jornada no encontrada") from e

    caja = calcular_cadena_caja(db, jornada_id)
    return CadenaCajaResponse(**caja)


@router.post("/{jornada_id}/preparar-siguiente", response_model=dict)
def preparar_siguiente(
    jornada_id: UUID,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    try:
        jornada = get_jornada(db, jornada_id, ctx)
    except JornadaNotFoundError as e:
        raise HTTPException(status_code=404, detail="Jornada no encontrada") from e

    result = preparar_siguiente_jornada(
        db,
        ruta_id=jornada.ruta_id,
        negocio_id=ctx.negocio_id,
    )
    return result
