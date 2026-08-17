"""m11 promesa_pago — Promise to Pay (W6).

Revision ID: m11_promesa_pago
Revises: m10_audit_documento
Create Date: 2026-08-17

Crea la tabla promesa_pago para el flujo de Promise to Pay (W6).
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "m11_promesa_pago"
down_revision = "m10_audit_documento"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "promesa_pago",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "negocio_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("negocio.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "credito_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("credito.id"),
            nullable=False,
        ),
        sa.Column(
            "cliente_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("cliente.id"),
        ),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("usuario.id"),
        ),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("promised_date", sa.Date(), nullable=False),
        sa.Column("estado", sa.String(20), nullable=False, server_default="ACTIVE"),
        sa.Column("nota", sa.Text()),
        sa.Column("fulfilled_at", sa.DateTime(timezone=True)),
        sa.Column("broken_at", sa.DateTime(timezone=True)),
        sa.Column("cancelled_at", sa.DateTime(timezone=True)),
        sa.Column("clave_idempotencia", sa.String(100)),
        sa.Column("creado_el", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("actualizado_el", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "estado IN ('ACTIVE', 'FULFILLED', 'BROKEN', 'CANCELLED')",
            name="check_promesa_estado",
        ),
        sa.UniqueConstraint(
            "negocio_id", "clave_idempotencia", name="uq_promesa_idempotencia"
        ),
    )
    op.create_index(
        "ix_promesa_credito",
        "promesa_pago",
        ["credito_id"],
    )
    op.create_index(
        "ix_promesa_negocio_estado",
        "promesa_pago",
        ["negocio_id", "estado"],
    )


def downgrade() -> None:
    op.drop_index("ix_promesa_negocio_estado", table_name="promesa_pago")
    op.drop_index("ix_promesa_credito", table_name="promesa_pago")
    op.drop_table("promesa_pago")
