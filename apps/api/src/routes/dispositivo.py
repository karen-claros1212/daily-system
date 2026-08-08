"""Device authorization routes for Etapa 3 — "que se venda".

Endpoints:
- POST /api/dispositivos — register device (ADMINISTRADOR only)
- GET /api/dispositivos — list devices (any role, scoped to ctx.negocio_id)
- POST /api/dispositivos/{dispositivo_id}/validar — validate device
- POST /api/dispositivos/{dispositivo_id}/revocar — revoke device (ADMINISTRADOR only)
- POST /api/dispositivos/{dispositivo_id}/reactivar — reactivate device (ADMINISTRADOR only)
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.auth.context import RequestContext
from src.auth.deps import get_request_context
from src.database import get_db, get_db_transaction
from src.schemas import DispositivoCreate, DispositivoResponse
from src.services.dispositivo_service import (
    DispositivoError,
    listar_dispositivos,
    reactivar_dispositivo,
    reemplazar_dispositivo,
    registrar_dispositivo,
    revocar_dispositivo,
    validar_dispositivo,
)

router = APIRouter(prefix="/api/dispositivos", tags=["dispositivos"])

WriteSession = Annotated[
    Session,
    Depends(get_db_transaction, scope="function"),
]


@router.post("", response_model=DispositivoResponse, status_code=201)
def registrar(
    data: DispositivoCreate,
    db: WriteSession,
    ctx: RequestContext = Depends(get_request_context),
):
    """Register a new device for the negocio (ADMINISTRADOR only).

    Contrato seccion 9 (riesgo "POST /api/dispositivos no exige admin"):
    la creacion de dispositivo es SOLO via canje de codigo admin-generado o
    registro administrativo; un COBRADOR nunca crea dispositivos (403).
    """
    if not ctx.is_admin():
        raise HTTPException(
            status_code=403,
            detail="Solo ADMINISTRADOR puede registrar dispositivos",
        )
    try:
        dispositivo = registrar_dispositivo(
            db=db,
            negocio_id=ctx.negocio_id,
            huella=data.huella,
            modelo=data.modelo,
            plataforma=data.plataforma,
            user_id=None,
            is_admin=True,
        )
        return DispositivoResponse.model_validate(dispositivo)
    except DispositivoError as e:
        raise HTTPException(status_code=409, detail=e.detail)


@router.get("", response_model=list[DispositivoResponse])
def listar(
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_request_context),
):
    """List all devices for the negocio (from ctx)."""
    dispositivos = listar_dispositivos(db, ctx.negocio_id)
    return [DispositivoResponse.model_validate(d) for d in dispositivos]


@router.post("/{dispositivo_id}/validar", response_model=DispositivoResponse)
def validar(
    dispositivo_id: UUID,
    db: WriteSession,
    ctx: RequestContext = Depends(get_request_context),
):
    """Validate a device — updates ultima_validacion_servidor."""
    try:
        dispositivo = validar_dispositivo(db, dispositivo_id, ctx.negocio_id)
        return DispositivoResponse.model_validate(dispositivo)
    except DispositivoError as e:
        raise HTTPException(status_code=404, detail=e.detail)


@router.post("/{dispositivo_id}/revocar", response_model=DispositivoResponse)
def revocar(
    dispositivo_id: UUID,
    db: WriteSession,
    ctx: RequestContext = Depends(get_request_context),
):
    """Revoke a device (ADMINISTRADOR only)."""
    if not ctx.is_admin():
        raise HTTPException(status_code=403, detail="Solo ADMINISTRADOR puede revocar dispositivos")
    try:
        dispositivo = revocar_dispositivo(db, dispositivo_id, ctx.negocio_id)
        return DispositivoResponse.model_validate(dispositivo)
    except DispositivoError as e:
        raise HTTPException(status_code=404, detail=e.detail)


@router.post("/{dispositivo_id}/reactivar", response_model=DispositivoResponse)
def reactivar(
    dispositivo_id: UUID,
    db: WriteSession,
    ctx: RequestContext = Depends(get_request_context),
):
    """Reactivate a revoked device (ADMINISTRADOR only, audited)."""
    if not ctx.is_admin():
        raise HTTPException(status_code=403, detail="Solo ADMINISTRADOR puede reactivar dispositivos")
    try:
        dispositivo = reactivar_dispositivo(db, dispositivo_id, ctx.negocio_id, ctx.user_id)
        return DispositivoResponse.model_validate(dispositivo)
    except DispositivoError as e:
        raise HTTPException(status_code=404, detail=e.detail)


@router.post("/{dispositivo_id}/reemplazar")
def reemplazar(
    dispositivo_id: UUID,
    db: WriteSession,
    ctx: RequestContext = Depends(get_request_context),
):
    """Mark a device REPLACED and emit a new activation code (ADMIN only)."""
    if not ctx.is_admin():
        raise HTTPException(status_code=403, detail="Solo ADMINISTRADOR puede reemplazar dispositivos")
    try:
        dispositivo, codigo, token = reemplazar_dispositivo(
            db, dispositivo_id, ctx.negocio_id, ctx.user_id
        )
        return {
            "dispositivo": DispositivoResponse.model_validate(dispositivo).model_dump(),
            "nuevo_codigo": {
                "codigo_id": codigo.id,
                "token": token,
                "prefijo": codigo.prefijo,
                "expira_el": codigo.expira_el,
            },
        }
    except DispositivoError as e:
        raise HTTPException(status_code=404, detail=e.detail)
