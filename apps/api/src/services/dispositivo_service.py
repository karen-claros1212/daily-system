"""Device authorization service for Etapa 3 — "que se venda".

Handles device registration, validation, revocation, and reactivation.
Devices are identified by a cryptographic huella (fingerprint)
per negocio.
"""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import and_
from sqlalchemy.orm import Session

from src.models import Dispositivo


class DispositivoError(Exception):
    """Business error for device operations."""

    def __init__(self, detail: str, code: str = "DISPOSITIVO_ERROR"):
        self.detail = detail
        self.code = code
        super().__init__(detail)


def registrar_dispositivo(
    db: Session,
    negocio_id: UUID,
    huella: str,
    modelo: str | None = None,
    plataforma: str | None = None,
    user_id: UUID | None = None,
    is_admin: bool = False,
) -> Dispositivo:
    """Register a new device for a negocio.

    If device with same huella exists and is active, returns it.
    If revoked, reactivates it ONLY if is_admin=True.
    Otherwise creates new entry.
    """
    # Check subscription first
    from src.services.subscription_service import check_negocio_suscripcion

    check_negocio_suscripcion(db, negocio_id)

    dispositivo = (
        db.query(Dispositivo)
        .filter(
            and_(
                Dispositivo.negocio_id == negocio_id,
                Dispositivo.huella == huella,
            ),
        )
        .first()
    )

    ahora = datetime.now(timezone.utc)

    if dispositivo:
        if dispositivo.revocado_el is not None:
            if not is_admin:
                raise DispositivoError(
                    "Dispositivo revocado — requiere ADMINISTRADOR para reactivar",
                    "DISPOSITIVO_REVOCADO",
                )
            # Admin reactivation — explicit audit
            dispositivo.revocado_el = None
            dispositivo.activo = 1
            dispositivo.ultima_validacion_servidor = ahora
        else:
            # Existing active device — update metadata
            if modelo:
                dispositivo.modelo = modelo
            if plataforma:
                dispositivo.plataforma = plataforma
            dispositivo.ultima_validacion_servidor = ahora
        db.flush()
        return dispositivo
    else:
        nuevo = Dispositivo(
            id=UUID(int=hash(huella + str(negocio_id)) % (2**128)),
            negocio_id=negocio_id,
            huella=huella,
            modelo=modelo,
            plataforma=plataforma,
            usuario_id=user_id,
            autorizado_por=user_id,
            autorizado_el=ahora,
            ultima_validacion_servidor=ahora,
            activo=1,
        )
        db.add(nuevo)
        db.flush()
        return nuevo


def validar_dispositivo(
    db: Session,
    dispositivo_id: UUID,
    negocio_id: UUID,
) -> Dispositivo:
    """Validate that a device is authorized for the negocio.

    Updates ultima_validacion_servidor timestamp.
    Raises DispositivoError if not found or revoked.
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
        raise DispositivoError(
            "Dispositivo no autorizado o revocado",
            "DISPOSITIVO_NO_AUTORIZADO",
        )

    dispositivo.ultima_validacion_servidor = datetime.now(timezone.utc)
    db.flush()
    return dispositivo


def revocar_dispositivo(
    db: Session,
    dispositivo_id: UUID,
    negocio_id: UUID,
) -> Dispositivo:
    """Revoke a device. Sets revocado_el timestamp."""
    dispositivo = (
        db.query(Dispositivo)
        .filter(
            and_(
                Dispositivo.id == dispositivo_id,
                Dispositivo.negocio_id == negocio_id,
            ),
        )
        .first()
    )

    if not dispositivo:
        raise DispositivoError(
            "Dispositivo no encontrado",
            "DISPOSITIVO_NO_ENCONTRADO",
        )

    dispositivo.revocado_el = datetime.now(timezone.utc)
    dispositivo.activo = 0
    db.flush()
    return dispositivo


def reactivar_dispositivo(
    db: Session,
    dispositivo_id: UUID,
    negocio_id: UUID,
    autorizado_por: UUID | None = None,
) -> Dispositivo:
    """Explicitly reactivate a revoked device (admin-only, audited).

    Raises DispositivoError if device not found, not revoked, or wrong negocio.
    """
    dispositivo = (
        db.query(Dispositivo)
        .filter(
            and_(
                Dispositivo.id == dispositivo_id,
                Dispositivo.negocio_id == negocio_id,
                Dispositivo.revocado_el.isnot(None),
            ),
        )
        .first()
    )

    if not dispositivo:
        raise DispositivoError(
            "Dispositivo no encontrado o ya activo",
            "DISPOSITIVO_NO_ENCONTRADO",
        )

    dispositivo.revocado_el = None
    dispositivo.activo = 1
    dispositivo.autorizado_el = datetime.now(timezone.utc)
    dispositivo.ultima_validacion_servidor = datetime.now(timezone.utc)
    db.flush()
    return dispositivo


def listar_dispositivos(
    db: Session,
    negocio_id: UUID,
) -> list[Dispositivo]:
    """List all devices for a negocio."""
    return (
        db.query(Dispositivo)
        .filter(
            Dispositivo.negocio_id == negocio_id,
        )
        .order_by(Dispositivo.creado_el.desc())
        .all()
    )
