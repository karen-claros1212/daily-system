"""W10 — Modelo LLMProviderConfig: configuración LLM tenant-scoped.

Una fila por (negocio, provider). Guarda la configuración NO secreta:
  - model, endpoint_profile (para OPENAI_COMPATIBLE_GENERIC), key_hint,
    enabled, is_default, timestamps, actor.

El material SECRETO (la API key) NO vive aquí: vive en el SecretStore,
referenciado por `secret_ref` opaco. Así una lectura normal de config nunca
devuelve la clave (contrato W10 §6/§11).
"""

import uuid

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID

from src.database import Base


class LLMProviderConfig(Base):
    """Configuración de un provider LLM para un negocio (tenant-scoped)."""

    __tablename__ = "llm_provider_config"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    negocio_id = Column(
        UUID(as_uuid=True),
        ForeignKey("negocio.id", ondelete="CASCADE"),
        nullable=False,
    )
    provider = Column(String(50), nullable=False)
    #: modelo seleccionado (nullable -> el gateway usa el default del provider)
    model = Column(String(200))
    #: endpoint profile allowlistado (solo OPENAI_COMPATIBLE_GENERIC)
    endpoint_profile = Column(String(50))
    #: referencia opaca al SecretStore (la clave cifrada vive ahí)
    secret_ref = Column(String(100))
    #: hint segura de la clave (ej. "sk-…abcd"); nunca permite reconstruirla
    key_hint = Column(String(50))
    enabled = Column(Integer, nullable=False, default=1)
    #: prioridad / provider por defecto del negocio
    is_default = Column(Integer, nullable=False, default=0)
    actualizado_por = Column(UUID(as_uuid=True))
    creado_el = Column(DateTime(timezone=True), server_default=func.now())
    actualizado_el = Column(DateTime(timezone=True), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("negocio_id", "provider", name="uq_llm_config_negocio_provider"),
        CheckConstraint(
            "provider IN ("
            "'OPENAI_NATIVE', 'MISTRAL_NATIVE', 'CEREBRAS_OPENAI_COMPATIBLE', "
            "'ANTHROPIC_NATIVE', 'GEMINI_NATIVE', 'OPENAI_COMPATIBLE_GENERIC'"
            ")",
            name="check_llm_provider_valido",
        ),
        CheckConstraint("enabled IN (0, 1)", name="check_llm_enabled"),
        CheckConstraint("is_default IN (0, 1)", name="check_llm_is_default"),
    )
