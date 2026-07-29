"""Subscription checks for Etapa 3 — "que se venda".

Validates negocio subscription status and paid_through_at before
allowing operations. Returns structured error when subscription
is expired or pending.
"""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.models import Negocio


class SuscripcionError(Exception):
    """Business error when subscription blocks an operation."""

    def __init__(self, detail: str, code: str = "SUScripcion_EXPIRADA"):
        self.detail = detail
        self.code = code
        super().__init__(detail)


def check_negocio_suscripcion(db: Session, negocio_id) -> Negocio:
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
    dispositivo_id,
    negocio_id,
) -> bool:
    """Verify device exists, belongs to negocio, and is authorized.

    Returns True if device is valid. Raises SuscripcionError otherwise.
    """
    from sqlalchemy import and_

    dispositivo = (
        db.query(Negocio)
        .join(Negocio.dispositivos)
        .filter(
            and_(
                Negocio.dispositivo.id == dispositivo_id,
                Negocio.id == negocio_id,
                Negocio.dispositivo.activo == 1,
                Negocio.dispositivo.revocado_el.is_(None),
            ),
        )
        .first()
    )

    if not dispositivo:
        # Try direct dispositivo query
        from src.models import Dispositivo

        dev = (
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
        if not dev:
            raise SuscripcionError(
                "Dispositivo no autorizado o revocado",
                "DISPOSITIVO_NO_AUTORIZADO",
            )

    return True
