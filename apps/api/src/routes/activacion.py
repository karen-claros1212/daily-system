"""Activation routes — Contrato de activacion (Bloque 6) + sesion (Bloque 7).

Activacion:
- POST /api/activaciones/codigos   (ADMINISTRADOR)   genera codigo de un solo uso
- POST /api/activaciones/desafio   (publico, sin token de sesion)
- POST /api/activaciones/canjear   (publico, sin token de sesion)
- GET  /api/mobile/bootstrap       (Bearer JWT de sesion productivo)

Sesion daily-auth-v1 (D7-H2, sustituye a /api/mobile/auth/renovar):
- POST /api/auth/device/desafio   (Bearer JWT vigente o credencial bootstrap)
- POST /api/auth/device/canjear   (verifica firma JCS y emite access token)

Los endpoints publicos NO aceptan negocio_id/cobrador_id/ruta_id/rol/estado:
el servidor deriva todo desde el codigo (regla del body publico, seccion 4).
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from src.auth.context import RequestContext
from src.auth.deps import get_request_context, get_request_context_jwt
from src.database import get_db, get_db_transaction
from src.schemas import (
    BootstrapResponse,
    CanjearDesafioRequest,
    CanjearDesafioResponse,
    CanjearRequest,
    CanjearResponse,
    CodigoActivacionCreate,
    CodigoActivacionResponse,
    DesafioAuthResponse,
    DesafioRequest,
    DesafioResponse,
)
from src.services.activacion_service import (
    ActivacionError,
    canjear,
    desafio,
    generar_codigo,
)
from src.services.auth_service import (
    AuthError,
    bootstrap_productivo,
)
from src.services.auth_service import (
    canjear_desafio as canjear_desafio_svc,
)
from src.services.auth_service import (
    solicitar_desafio as solicitar_desafio_svc,
)

router = APIRouter(prefix="/api/activaciones", tags=["activaciones"])
mobile_router = APIRouter(prefix="/api/mobile", tags=["mobile"])
device_router = APIRouter(prefix="/api/auth", tags=["auth"])

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
    ctx: Annotated[RequestContext, Depends(get_request_context_jwt)] = None,
):
    """Bootstrap productivo del movil (Bearer JWT ES256, D7-01).

    El RequestContext revalida en CADA request el binding completo
    (dispositivo ACTIVE, version_asignacion, usuario, negocio, public_key_hash)
    y exige exactamente UNA ruta activa del cobrador (0 y >1 -> 401). El
    servidor deriva negocio, cobrador, ruta y versiones desde la base: no se
    aceptan negocio_id/route_id/rol por URL ni por body (aislamiento movil).
    La credencial bootstrap del canje ya NO autentica esta ruta: su unica
    funcion posterior al canje es obtener el primer JWT vía desafio/canje.
    """
    try:
        return bootstrap_productivo(db, ctx)
    except AuthError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)


@device_router.post("/device/desafio", response_model=DesafioAuthResponse)
def solicitar_desafio_sesion(
    db: WriteSession,
    authorization: str | None = Header(default=None),
):
    """Paso 1: crea un DesafioAuth de un solo uso (daily-auth-v1).

    Autentica el dispositivo con el JWT de sesion vigente (Bearer) o, para el
    PRIMER JWT post-activacion, con la credencial bootstrap emitida en el
    canje. El servidor emite challenge_id + nonce CSPRNG + expira_el.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=401,
            detail="Credencial de sesion (Bearer JWT o bootstrap) requerida",
        )
    credencial = authorization.split(" ", 1)[1].strip()
    try:
        return solicitar_desafio_svc(db, credencial)
    except AuthError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)


@device_router.post("/device/canjear", response_model=CanjearDesafioResponse)
def canjear_desafio_sesion(
    data: CanjearDesafioRequest,
    db: WriteSession,
):
    """Paso 2: verifica la firma JCS del desafio y consume, en una transaccion.

    Single-use: el replay del mismo challenge_id devuelve 409. Emite el access
    token ES256 con el version_asignacion ACTUAL de la base.
    """
    try:
        return canjear_desafio_svc(
            db, challenge_id=data.challenge_id, firma=data.firma
        )
    except AuthError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
