"""Servicio de alta de negocios — Onboarding seguro (Etapa 3).

POST /api/onboarding/negocios crea la unidad minima de un tenant nuevo en UNA
transaccion (todo o nada, via get_db_transaction del route):

  1. Negocio          con los defaults comerciales REALES del modelo
                      (pais=CO, moneda=COP, zona_horaria=America/Bogota,
                       plan=basic, estado_suscripcion=al_dia). Sin inventar
                       planes, trials ni billing.
  2. Usuario inicial  ADMINISTRADOR, activo, perteneciente al negocio (FK
                      negocio_id): es la identidad inicial de tenancy.
  3. Codigo de        bootstrap reusando activacion_service.generar_codigo
     activacion      (digest SHA-256 del token, TTL 10 min): la UNICA primitiva
                      productiva que permite al admin inicial completar el login
                      Web existente (desafio/canje daily-v1 -> sesion).

Garantias:
  - Atomicidad: si falla el admin o el codigo, la transaccion se revierte y no
    queda ningun negocio huerfano.
  - NIT: normalizacion minima (trim) + verificacion de conflicto server-side
    dentro de la transaccion -> 409 controlado. Sin constraint migratoria
    destructiva ni algoritmos DIAN inventados.
  - El body publico no acepta negocio_id / rol / plan / estado: el servidor
    deriva todo (aislamiento de tenancy y de reglas comerciales).
"""

from sqlalchemy.orm import Session

from src.models import Negocio, Usuario
from src.services.activacion_service import (
    ActivacionError,
    generar_codigo,
)


class OnboardingError(Exception):
    """Business error del alta segura (mapeado a HTTP en el route)."""

    def __init__(self, detail: str, code: str = "ONBOARDING_ERROR", status_code: int = 400):
        self.detail = detail
        self.code = code
        self.status_code = status_code
        super().__init__(detail)


def _normalizar_nit(nit: str | None) -> str | None:
    if nit is None:
        return None
    nit = nit.strip()
    return nit or None


def verificar_nit_disponible(db: Session, nit: str | None) -> None:
    """Conflicto de NIT server-side -> 409 (comun a onboarding y al alta
    administrativa legada). Sin NIT no hay conflicto posible."""
    nit = _normalizar_nit(nit)
    if nit is None:
        return
    existente = db.query(Negocio.id).filter(Negocio.nit == nit).first()
    if existente is not None:
        raise OnboardingError(
            "El NIT ya esta registrado",
            "NIT_YA_REGISTRADO",
            409,
        )


def crear_negocio_con_admin(
    db: Session,
    *,
    nombre: str,
    nit: str | None,
    admin_nombre: str,
    admin_documento: str | None,
):
    """Crea la unidad tenant en una sola transaccion (negocio + admin + codigo).

    Devuelve (negocio, admin, codigo, token). El `token` del codigo de
    activacion se entrega UNA vez al caller; el servidor conserva solo el
    digest. Todos los objetos se insertan via flush dentro de la transaccion
    del route; un error en cualquier paso revierte el todo.
    """
    nit = _normalizar_nit(nit)
    verificar_nit_disponible(db, nit)

    negocio = Negocio(nombre=nombre, nit=nit)
    db.add(negocio)
    db.flush()
    # creado_el es server_default: refrescarlo para serializar NegocioResponse.
    db.refresh(negocio)

    admin = Usuario(
        negocio_id=negocio.id,
        rol="ADMINISTRADOR",
        nombre=admin_nombre,
        documento=admin_documento,
    )
    db.add(admin)
    db.flush()
    db.refresh(admin)

    # Bootstrap de identidad: codigo de activacion de un solo uso para el admin
    # inicial (valida el objetivo: existe, activo, rol con sesion, del negocio).
    try:
        codigo, token = generar_codigo(
            db,
            negocio_id=negocio.id,
            cobrador_id=admin.id,
            creado_por=admin.id,
        )
    except ActivacionError as e:
        raise OnboardingError(e.detail, e.code, e.status_code) from e

    return negocio, admin, codigo, token
