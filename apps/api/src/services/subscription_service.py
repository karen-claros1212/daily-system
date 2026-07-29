"""Subscription checks for Etapa 3 — "que se venda".

Validates negocio subscription status and paid_through_at before
allowing operations. Returns structured error when subscription
is expired or pending.
"""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import and_
from sqlalchemy.orm import Session

from src.models import Dispositivo, Negocio


class SuscripcionError(Exception):
    """Business error when subscription blocks an operation."""

    def __init__(self, detail: str, code: str = "SUSCRIPCION_EXPIRADA"):
        self.detail = detail
        self.code = code
        super().__init__(detail)


def check_negocio_suscripcion(db: Session, negocio_id: UUID) -> Negocio:
    """Verify negocio exists and subscription is active.

    Raises SuscripcionError if:
    - negocio not found
    - estado_suscripcion != 'al_dia'
    - paid_through_at is in the past
    """
    negocio = (
        db.query(Negocio)
        .filter(Negocio.id == negocio_id)
        .first()
    )
    if not negocio:
        raise SuscripcionError("Negocio no encontrado", "NEGOCIO_NO_ENCONTRADO")

    if negocio.estado_suscripcion != "al_dia":
        raise SuscripcionError(
            f"Suscripcion: {negocio.estado_suscripcion}",
            "SUSCRIPCION_INACTIVA",
        )

    if negocio.paid_through_at and negocio.paid_through_at < datetime.now(timezone.utc):
        negocio.estado_suscripcion = "vencida"
        db.flush()
        raise SuscripcionError(
            f"Suscripcion vencida el {negocio.paid_through_at.isoformat()}",
            "SUSCRIPCION_VENCIDA",
        )

    return negocio


def check_dispositivo_autorizado(
    db: Session,
    dispositivo_id: UUID,
    negocio_id: UUID,
) -> Dispositivo:
    """Verify device exists, belongs to negocio, and is authorized.

    Returns the Dispositivo if valid. Raises SuscripcionError otherwise.
    """
    dispositivo = (
        db.query(Dispositivo)
        .filter(
            and_(
                Dispositivo.id == dispositivo_id,
                Dispositivo.negocio_id == negocio_id,
                Dispositivo.activo == 1,
                Dispositivo.revocado_el.is_(None),
            ),
        )
        .first()
    )

    if not dispositivo:
        raise SuscripcionError(
            "Dispositivo no autorizado o revocado",
            "DISPOSITIVO_NO_AUTORIZADO",
        )

    return dispositivo
