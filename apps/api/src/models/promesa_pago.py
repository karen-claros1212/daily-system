"""PromesaPago model — Promise to Pay (W6)."""

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from src.database import Base


class PromesaPago(Base):
    """Promise to Pay — compromiso formal de pago por el cliente."""
    __tablename__ = "promesa_pago"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    negocio_id = Column(
        UUID(as_uuid=True),
        ForeignKey("negocio.id", ondelete="CASCADE"),
        nullable=False,
    )
    credito_id = Column(
        UUID(as_uuid=True),
        ForeignKey("credito.id"),
        nullable=False,
    )
    cliente_id = Column(
        UUID(as_uuid=True),
        ForeignKey("cliente.id"),
    )
    created_by = Column(
        UUID(as_uuid=True),
        ForeignKey("usuario.id"),
    )
    amount = Column(Integer, nullable=False)
    promised_date = Column(Date, nullable=False)
    estado = Column(
        String(20),
        nullable=False,
        default="ACTIVE",
    )
    nota = Column(Text)
    fulfilled_at = Column(DateTime(timezone=True))
    broken_at = Column(DateTime(timezone=True))
    cancelled_at = Column(DateTime(timezone=True))
    clave_idempotencia = Column(String(100))
    creado_el = Column(DateTime(timezone=True), server_default=func.now())
    actualizado_el = Column(DateTime(timezone=True), onupdate=func.now())

    __table_args__ = (
        CheckConstraint(
            "estado IN ('ACTIVE', 'FULFILLED', 'BROKEN', 'CANCELLED')",
            name="check_promesa_estado",
        ),
        UniqueConstraint(
            "negocio_id", "clave_idempotencia", name="uq_promesa_idempotencia"
        ),
    )
