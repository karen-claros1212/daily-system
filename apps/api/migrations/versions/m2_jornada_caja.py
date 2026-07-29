"""add jornada cierre fields and movimiento traceability

Revision ID: m2_jornada_caja
Revises: init
Create Date: 2026-07-29

Adds:
- jornada: cierre_idempotency_key, cierre_snapshot_json, cierre_snapshot_hash,
  cierre_version, cerrada_por, actualizado_el
- movimiento_caja: clave_idempotencia, registrado_el_dispositivo,
  recibido_el_servidor, dispositivo_id, credito_id, renovacion_id,
  ajuste_de_movimiento_id
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "m2_jornada_caja"
down_revision = "init"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # === jornada new columns ===
    op.add_column(
        "jornada",
        sa.Column("actualizado_el", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "jornada",
        sa.Column("cierre_idempotency_key", sa.String(100), nullable=True),
    )
    op.add_column(
        "jornada",
        sa.Column("cierre_snapshot_json", postgresql.JSONB, nullable=True),
    )
    op.add_column(
        "jornada",
        sa.Column("cierre_snapshot_hash", sa.String(64), nullable=True),
    )
    op.add_column(
        "jornada",
        sa.Column("cierre_version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "jornada",
        sa.Column("cerrada_por", sa.UUID(), nullable=True),
    )

    # === movimiento_caja new columns ===
    op.add_column(
        "movimiento_caja",
        sa.Column("clave_idempotencia", sa.String(100), nullable=True),
    )
    op.add_column(
        "movimiento_caja",
        sa.Column(
            "registrado_el_dispositivo", sa.DateTime(timezone=True), nullable=True
        ),
    )
    op.add_column(
        "movimiento_caja",
        sa.Column("recibido_el_servidor", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "movimiento_caja",
        sa.Column("dispositivo_id", sa.UUID(), nullable=True),
    )
    op.add_column(
        "movimiento_caja",
        sa.Column("credito_id", sa.UUID(), nullable=True),
    )
    op.add_column(
        "movimiento_caja",
        sa.Column("renovacion_id", sa.UUID(), nullable=True),
    )
    op.add_column(
        "movimiento_caja",
        sa.Column(
            "ajuste_de_movimiento_id",
            sa.UUID(),
            nullable=True,
        ),
    )

    # === foreign keys ===
    op.create_foreign_key(
        "fk_movimiento_credito",
        "movimiento_caja",
        "credito",
        ["credito_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_movimiento_renovacion",
        "movimiento_caja",
        "renovacion",
        ["renovacion_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_movimiento_ajuste",
        "movimiento_caja",
        "movimiento_caja",
        ["ajuste_de_movimiento_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # === unique constraints ===
    op.create_unique_constraint(
        "uq_jornada_cierre_key",
        "jornada",
        ["negocio_id", "cierre_idempotency_key"],
    )
    op.create_unique_constraint(
        "uq_movimiento_idempotencia",
        "movimiento_caja",
        ["negocio_id", "clave_idempotencia"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_movimiento_idempotencia", "movimiento_caja", type_="unique")
    op.drop_constraint("uq_jornada_cierre_key", "jornada", type_="unique")
    op.drop_constraint("fk_movimiento_ajuste", "movimiento_caja", type_="foreignkey")
    op.drop_constraint("fk_movimiento_renovacion", "movimiento_caja", type_="foreignkey")
    op.drop_constraint("fk_movimiento_credito", "movimiento_caja", type_="foreignkey")
    op.drop_column("movimiento_caja", "ajuste_de_movimiento_id")
    op.drop_column("movimiento_caja", "renovacion_id")
    op.drop_column("movimiento_caja", "credito_id")
    op.drop_column("movimiento_caja", "dispositivo_id")
    op.drop_column("movimiento_caja", "recibido_el_servidor")
    op.drop_column("movimiento_caja", "registrado_el_dispositivo")
    op.drop_column("movimiento_caja", "clave_idempotencia")
    op.drop_column("jornada", "cerrada_por")
    op.drop_column("jornada", "cierre_version")
    op.drop_column("jornada", "cierre_snapshot_hash")
    op.drop_column("jornada", "cierre_snapshot_json")
    op.drop_column("jornada", "cierre_idempotency_key")
    op.drop_column("jornada", "actualizado_el")
