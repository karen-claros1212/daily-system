"""add apertura_idempotency_key to jornada

Revision ID: m2_apertura_idempotency
Revises: m2_jornada_caja
Create Date: 2026-07-29

Adds:
- jornada: apertura_idempotency_key with UNIQUE(negocio_id, apertura_idempotency_key)
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "m2_apertura_idempotency"
down_revision = "m2_jornada_caja"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "jornada",
        sa.Column("apertura_idempotency_key", sa.String(100), nullable=True),
    )
    op.create_unique_constraint(
        "uq_jornada_apertura_key",
        "jornada",
        ["negocio_id", "apertura_idempotency_key"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_jornada_apertura_key", "jornada", type_="unique")
    op.drop_column("jornada", "apertura_idempotency_key")
