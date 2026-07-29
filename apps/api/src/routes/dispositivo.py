"""Device authorization routes for Etapa 3 — "que se venda".

Endpoints:
- POST /api/dispositivos — register device
- GET /api/dispositivos — list devices
- POST /api/dispositivos/{dispositivo_id}/validar — validate device
- POST /api/dispositivos/{dispositivo_id}/revocar — revoke device
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from src.database import get_db, get_db_transaction
from src.models import Dispositivo
from src.schemas import DispositivoCreate, DispositivoResponse
from src.services.dispositivo_service import (
    DispositivoError,
    listar_dispositivos,
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
    negocio_id: UUID = Query(..., description="Negocio ID"),
):
    """Register a new device for the negocio."""
    try:
        dispositivo = registrar_dispositivo(
            db=db,
            negocio_id=negocio_id,
            huella=data.huella,
            modelo=data.modelo,
            plataforma=data.plataforma,
        )
        return DispositivoResponse.model_validate(dispositivo)
    except DispositivoError as e:
        raise HTTPException(status_code=409, detail=e.detail)


@router.get("", response_model=list[DispositivoResponse])
def listar(
    db: Session = Depends(get_db),
    negocio_id: UUID = Query(..., description="Negocio ID"),
):
    """List all devices for the negocio."""
    dispositivos = listar_dispositivos(db, negocio_id)
    return [DispositivoResponse.model_validate(d) for d in dispositivos]


@router.post("/{dispositivo_id}/validar", response_model=DispositivoResponse)
def validar(
    dispositivo_id: UUID,
    db: WriteSession,
    negocio_id: UUID = Query(..., description="Negocio ID"),
):
    """Validate a device — updates ultima_validacion_servidor."""
    try:
        dispositivo = validar_dispositivo(db, dispositivo_id, negocio_id)
        return DispositivoResponse.model_validate(dispositivo)
    except DispositivoError as e:
        raise HTTPException(status_code=404, detail=e.detail)


@router.post("/{dispositivo_id}/revocar", response_model=DispositivoResponse)
def revocar(
    dispositivo_id: UUID,
    db: WriteSession,
    negocio_id: UUID = Query(..., description="Negocio ID"),
):
    """Revoke a device."""
    try:
        dispositivo = revocar_dispositivo(db, dispositivo_id, negocio_id)
        return DispositivoResponse.model_validate(dispositivo)
    except DispositivoError as e:
        raise HTTPException(status_code=404, detail=e.detail)
