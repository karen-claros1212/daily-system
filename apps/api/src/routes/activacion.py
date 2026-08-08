"""Activation routes — Contrato de activacion (Bloque 6).

- POST /api/activaciones/codigos   (ADMINISTRADOR)   genera codigo de un solo uso
- POST /api/activaciones/desafio   (publico, sin token de sesion)
- POST /api/activaciones/canjear   (publico, sin token de sesion)
- GET  /api/mobile/bootstrap       (credencial bootstrap emitida en el canje)

Los endpoints publicos NO aceptan negocio_id/cobrador_id/ruta_id/rol/estado:
el servidor deriva todo desde el codigo (regla del body publico, seccion 4).
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from src.auth.context import RequestContext
from src.auth.deps import get_request_context
from src.database import get_db, get_db_transaction
from src.schemas import (
    BootstrapResponse,
    CanjearRequest,
    CanjearResponse,
    CodigoActivacionCreate,
    CodigoActivacionResponse,
    DesafioRequest,
    DesafioResponse,
    RenovarRequest,
    RenovarResponse,
)
from src.services.activacion_service import (
    ActivacionError,
    bootstrappear,
    canjear,
    desafio,
    generar_codigo,
)
from src.services.auth_service import AuthError, renovar_sesion

router = APIRouter(prefix="/api/activaciones", tags=["activaciones"])
mobile_router = APIRouter(prefix="/api/mobile", tags=["mobile"])

WriteSession = Annotated[
    Session,
    Depends(get_db_transaction, scope="function"),
]


@router.post(
    "/codigos",
    response_model=CodigoActivacionResponse,
    status_code=201,
)
def crear_codigo(
    data: CodigoActivacionCreate,
    db: WriteSession,
    ctx: RequestContext = Depends(get_request_context),
):
    """Genera codigo de activacion de un solo uso para un cobrador (ADMIN)."""
    if not ctx.is_admin():
        raise HTTPException(
            status_code=403,
            detail="Solo ADMINISTRADOR puede generar codigos de activacion",
        )
    try:
        codigo, token = generar_codigo(
            db,
            negocio_id=ctx.negocio_id,
            cobrador_id=data.cobrador_id,
            creado_por=ctx.user_id,
            expira_minutos=data.expira_minutos,
        )
        return CodigoActivacionResponse(
            codigo_id=codigo.id,
            token=token,
            prefijo=codigo.prefijo,
            expira_el=codigo.expira_el,
        )
    except ActivacionError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)


@router.post("/desafio", response_model=DesafioResponse)
def solicitar_desafio(
    data: DesafioRequest,
    db: WriteSession,
):
    """Paso 1: crea un IntentoActivacion con nonce CSPRNG. No consume el codigo."""
    try:
        return desafio(
            db,
            token=data.token,
            clave_publica=data.clave_publica,
            modelo=data.modelo,
            plataforma=data.plataforma,
        )
    except ActivacionError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)


@router.post("/canjear", response_model=CanjearResponse)
def canjear_codigo(
    data: CanjearRequest,
    db: WriteSession,
):
    """Paso 2: verifica la firma JCS del nonce y consume, en una transaccion."""
    try:
        return canjear(db, intento_id=data.intento_id, firma=data.firma)
    except ActivacionError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)


@mobile_router.get("/bootstrap", response_model=BootstrapResponse)
def mobile_bootstrap(
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
):
    """Devuelve la ruta UNICA autorizada + negocio + cobrador.

    La credencial (Bearer) es la emitida en el canje; el servidor deriva todo,
    sin parametros en la URL. Aqui nace el aislamiento movil.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Credencial bootstrap requerida")
    credencial = authorization.split(" ", 1)[1].strip()
    try:
        return bootstrappear(db, credencial)
    except ActivacionError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)


@mobile_router.post("/auth/renovar", response_model=RenovarResponse)
def renovar_token(
    data: RenovarRequest,
    db: WriteSession,
):
    """Renueva el JWT de sesion por challenge-response (daily-auth-v1).

    Requiere el JWT vigente + firma JCS del payload firmada con la clave
    privada del dispositivo (Android Keystore). Sin refresh token.
    """
    try:
        return renovar_sesion(
            db,
            token=data.token,
            firma=data.firma,
            expires_at=data.expires_at,
        )
    except AuthError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
