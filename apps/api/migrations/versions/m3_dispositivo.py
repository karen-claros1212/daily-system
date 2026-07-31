"""m3 add dispositivo table

Revision ID: m3_dispositivo
Revises: m2_apertura_idempotency
Create Date: 2026-07-29

Device authorization table for Etapa 3 — "que se venda".
Tracks authorized devices per negocio with huella fingerprint,
authorization timestamps, and revocation support.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "m3_dispositivo"
down_revision = "m2_apertura_idempotency"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "dispositivo",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("negocio_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("usuario_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("huella", sa.String(64), nullable=False),
        sa.Column("modelo", sa.String(200), nullable=True),
        sa.Column("plataforma", sa.String(20), nullable=True),
        sa.Column("autorizado_por", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("autorizado_el", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revocado_el", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ultima_validacion_servidor", sa.DateTime(timezone=True), nullable=True),
        sa.Column("activo", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("creado_el", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint(
            "plataforma IN ('android', 'ios', 'web', 'linux', 'windows', 'macos', 'other')",
            name="check_dispositivo_plataforma",
        ),
        sa.UniqueConstraint("negocio_id", "huella", name="uq_dispositivo_huella"),
        sa.ForeignKeyConstraint(
            ["negocio_id"],
            ["negocio.id"],
            ondelete="CASCADE",
            name="fk_dispositivo_negocio",
        ),
        sa.ForeignKeyConstraint(
            ["usuario_id"],
            ["usuario.id"],
            name="fk_dispositivo_usuario",
        ),
    )


def downgrade() -> None:
    op.drop_table("dispositivo")
