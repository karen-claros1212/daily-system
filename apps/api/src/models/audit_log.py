"""Audit trail append-only — tabla de auditoria W1 (A1).

Cada operacion administrativa genera una fila con: negocio_id, actor (quien
hizo la accion), action (tipo de operacion), entity_type, entity_id,
metadata (JSON libre), y timestamp UTC.

Solo ADMINISTRADOR escribe. Solo ADMINISTRADOR lee. Append-only: no UPDATE
ni DELETE (solo soft-delete via activo=0 en la entidad afectada).
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from src.database import Base


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    negocio_id = Column(
        UUID(as_uuid=True),
        ForeignKey("negocio.id", ondelete="CASCADE"),
        nullable=False,
    )
    actor_id = Column(
        UUID(as_uuid=True),
        ForeignKey("usuario.id"),
        nullable=False,
    )
    action = Column(
        String(50),
        nullable=False,
    )
    entity_type = Column(
        String(50),
        nullable=False,
    )
    entity_id = Column(
        UUID(as_uuid=True),
    )
    metadata_col = Column(
        JSONB().with_variant(JSON(), "sqlite"),
        nullable=True,
    )
    ip_address = Column(String(45))
    user_agent = Column(String(500))
    creado_el = Column(DateTime(timezone=True), server_default=func.now())

    actor = relationship("Usuario")

    __table_args__ = (
        Index("ix_audit_log_negocio_creado", "negocio_id", "creado_el"),
        Index("ix_audit_log_entity", "entity_type", "entity_id"),
        Index("ix_audit_log_action", "action"),
    )
