"""Payment service — business logic separated from HTTP concerns."""

from uuid import UUID

from sqlalchemy.orm import Session

from src.models import Pago


def find_existing_payment(
    db: Session, negocio_id: UUID, clave_idempotencia: str
) -> Pago | None:
    return (
        db.query(Pago)
        .filter(
            Pago.negocio_id == negocio_id,
            Pago.clave_idempotencia == clave_idempotencia,
        )
        .first()
    )
