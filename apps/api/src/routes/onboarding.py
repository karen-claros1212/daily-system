"""Onboarding de negocios — Alta de negocios (Etapa 3).

POST /api/onboarding/negocios (publico): frontera de registro EXPLICITA y
transaccional. Crea Negocio + Usuario ADMINISTRADOR inicial + relacion tenant
+ defaults comerciales reales del modelo + codigo de activacion bootstrap en
UNA transaccion (todo o nada, via get_db_transaction).

El body publico NO acepta negocio_id / rol / plan / estado_suscripcion: el
servidor deriva todo (aislamiento de tenancy y de reglas comerciales). El
`token` del codigo de activacion se entrega UNA vez; con el, el admin inicial
completa el login Web ya existente (desafio/canje daily-v1 -> sesion).
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.database import get_db_transaction
from src.schemas import (
    CodigoActivacionResponse,
    NegocioResponse,
    OnboardingNegocioCreate,
    OnboardingNegocioResponse,
    UsuarioResponse,
)
from src.services.onboarding_service import OnboardingError, crear_negocio_con_admin

router = APIRouter(prefix="/api/onboarding", tags=["onboarding"])

WriteSession = Annotated[
    Session,
    Depends(get_db_transaction, scope="function"),
]


@router.post(
    "/negocios",
    response_model=OnboardingNegocioResponse,
    status_code=201,
)
def crear_negocio_onboarding(
    data: OnboardingNegocioCreate,
    db: WriteSession,
):
    """Alta segura y atomica de un negocio nuevo + su ADMINISTRADOR inicial.

    Todo (negocio, usuario admin, codigo de activacion) se crea en la misma
    transaccion: un fallo en cualquier paso revierte la operacion completa.
    Conflicto de NIT -> 409 controlado dentro de la transaccion.
    """
    try:
        negocio, admin, codigo, token = crear_negocio_con_admin(
            db,
            nombre=data.nombre,
            nit=data.nit,
            admin_nombre=data.administrador.nombre,
            admin_documento=data.administrador.documento,
        )
    except OnboardingError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)

    return OnboardingNegocioResponse(
        negocio=NegocioResponse.model_validate(negocio),
        administrador=UsuarioResponse.model_validate(admin),
        codigo_activacion=CodigoActivacionResponse(
            codigo_id=codigo.id,
            token=token,
            prefijo=codigo.prefijo,
            expira_el=codigo.expira_el,
        ),
        siguiente_paso="activar_codigo",
    )
