"""m12 llm_provider_config — Provider Gateway Multi-LLM + BYOK (W10).

Revision ID: m12_llm_provider_config
Revises: m11_promesa_pago
Create Date: 2026-08-18

Crea la tabla llm_provider_config (configuración LLM tenant-scoped). La clave
secreta vive en el SecretStore (referenciada por secret_ref opaco), NO en esta
tabla.

Forward-only desde m11_promesa_pago. NO edita m11.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "m12_llm_provider_config"
down_revision = "m11_promesa_pago"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "llm_provider_config",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "negocio_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("negocio.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("model", sa.String(200)),
        sa.Column("endpoint_profile", sa.String(50)),
        sa.Column("secret_ref", sa.String(100)),
        sa.Column("key_hint", sa.String(50)),
        sa.Column("enabled", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_default", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("actualizado_por", postgresql.UUID(as_uuid=True)),
        sa.Column("creado_el", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("actualizado_el", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "provider IN ("
            "'OPENAI_NATIVE', 'MISTRAL_NATIVE', 'CEREBRAS_OPENAI_COMPATIBLE', "
            "'ANTHROPIC_NATIVE', 'GEMINI_NATIVE', 'OPENAI_COMPATIBLE_GENERIC'"
            ")",
            name="check_llm_provider_valido",
        ),
        sa.CheckConstraint("enabled IN (0, 1)", name="check_llm_enabled"),
        sa.CheckConstraint("is_default IN (0, 1)", name="check_llm_is_default"),
        sa.UniqueConstraint(
            "negocio_id", "provider", name="uq_llm_config_negocio_provider"
        ),
    )
    op.create_index(
        "ix_llm_config_negocio",
        "llm_provider_config",
        ["negocio_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_llm_config_negocio", table_name="llm_provider_config")
    op.drop_table("llm_provider_config")
