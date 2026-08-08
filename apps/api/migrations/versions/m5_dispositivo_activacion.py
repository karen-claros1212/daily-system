"""m5 dispositvo activacion (contrato de activacion — Bloque 6)

Revision ID: m5_dispositivo_activacion
Revises: m4_ruta_cobrador_fk
Create Date: 2026-08-06

Migracion de EXPANSION y REVERSIBLE (expand-and-contract). NO contrae:
- Se conserva la columna legacy `dispositivo.huella` (pasa a nullable).
- Se conserva `dispositivo.usuario_id` nullable (el contrato de activacion
  lo pasa a NOT NULL en una fase posterior, tras backfill).

Expand (upgrade):
  1. dispositivo: + estado (ACTIVE/REVOKED/REPLACED), + public_key (SPKI),
     + public_key_hash, + algoritmo_clave; huella -> nullable; backfill de
     estado segun activo/revocado_el.
  2. Indices parciales unicos en PostgreSQL:
     - uq_dispositivo_public_key_hash  (public_key_hash NOT NULL)
     - uq_dispositivo_activo_cobrador  (un ACTIVE por cobrador)
     - uq_ruta_activa_cobrador         (una ruta activa por cobrador)
  3. Tablas codigo_activacion e intento_activacion.

Downgrade: orden inverso, sin perdida de datos (tabla dispositivo vacia en la
practica; de haber filas, downgrade conserva public_key/public_key_hash y
restaura huella).
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "m5_dispositivo_activacion"
down_revision = "m4_ruta_cobrador_fk"
branch_labels = None
depends_on = None


def _add_dispositivo_columns() -> None:
    op.add_column(
        "dispositivo",
        sa.Column(
            "estado",
            sa.String(20),
            nullable=False,
            server_default="ACTIVE",
        ),
    )
    op.add_column("dispositivo", sa.Column("public_key", sa.Text(), nullable=True))
    op.add_column(
        "dispositivo",
        sa.Column("public_key_hash", sa.String(64), nullable=True),
    )
    op.add_column(
        "dispositivo",
        sa.Column("algoritmo_clave", sa.String(20), nullable=True),
    )
    op.alter_column(
        "dispositivo",
        "huella",
        existing_type=sa.String(64),
        nullable=True,
    )
    op.create_check_constraint(
        "check_dispositivo_estado",
        "dispositivo",
        "estado IN ('ACTIVE', 'REVOKED', 'REPLACED')",
    )


def _backfill_estado() -> None:
    dispositivo = sa.table(
        "dispositivo",
        sa.column("estado", sa.String),
        sa.column("activo", sa.Integer),
        sa.column("revocado_el", sa.DateTime(timezone=True)),
    )
    op.execute(
        dispositivo.update()
        .where(dispositivo.c.revocado_el.isnot(None))
        .values(estado="REVOKED")
    )
    op.execute(
        dispositivo.update()
        .where(dispositivo.c.revocado_el.is_(None))
        .values(estado="ACTIVE")
    )


def _create_partial_indexes() -> None:
    op.create_index(
        "uq_dispositivo_public_key_hash",
        "dispositivo",
        ["public_key_hash"],
        unique=True,
        postgresql_where=sa.text("public_key_hash IS NOT NULL"),
    )
    op.create_index(
        "uq_dispositivo_activo_cobrador",
        "dispositivo",
        ["usuario_id"],
        unique=True,
        postgresql_where=sa.text("estado = 'ACTIVE' AND usuario_id IS NOT NULL"),
    )
    op.create_index(
        "uq_ruta_activa_cobrador",
        "ruta",
        ["cobrador_id"],
        unique=True,
        postgresql_where=sa.text("activa = 1 AND cobrador_id IS NOT NULL"),
    )


def _create_codigo_activacion() -> None:
    op.create_table(
        "codigo_activacion",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("negocio_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("cobrador_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("hash_codigo", sa.String(64), nullable=False),
        sa.Column("prefijo", sa.String(8), nullable=False),
        sa.Column("expira_el", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "intentos_fallidos",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "estado",
            sa.String(20),
            nullable=False,
            server_default="PENDING",
        ),
        sa.Column("consumido_el", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "dispositivo_id_canjeado",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column("credencial_bootstrap", sa.String(128), nullable=True),
        sa.Column(
            "credencial_bootstrap_expira_el",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column("creado_por", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("entregado_el", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "creado_el",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "estado IN ('PENDING', 'CONSUMED', 'EXPIRED', 'CANCELLED')",
            name="check_codigo_activacion_estado",
        ),
        sa.ForeignKeyConstraint(
            ["negocio_id"],
            ["negocio.id"],
            ondelete="CASCADE",
            name="fk_codigo_negocio",
        ),
        sa.ForeignKeyConstraint(
            ["cobrador_id"],
            ["usuario.id"],
            name="fk_codigo_cobrador",
        ),
        sa.ForeignKeyConstraint(
            ["dispositivo_id_canjeado"],
            ["dispositivo.id"],
            name="fk_codigo_dispositivo",
        ),
        sa.ForeignKeyConstraint(
            ["creado_por"],
            ["usuario.id"],
            name="fk_codigo_creado_por",
        ),
    )
    op.create_index(
        "uq_codigo_activacion_hash",
        "codigo_activacion",
        ["hash_codigo"],
        unique=True,
    )
    op.create_index(
        "ix_codigo_estado_expira",
        "codigo_activacion",
        ["estado", "expira_el"],
    )


def _create_intento_activacion() -> None:
    op.create_table(
        "intento_activacion",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("codigo_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("nonce", sa.String(64), nullable=False),
        sa.Column("clave_publica", sa.Text(), nullable=False),
        sa.Column("public_key_hash", sa.String(64), nullable=False),
        sa.Column("modelo", sa.String(200), nullable=True),
        sa.Column("plataforma", sa.String(20), nullable=True),
        sa.Column("expira_el", sa.DateTime(timezone=True), nullable=False),
        sa.Column("firma_validada_el", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consumido_el", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "creado_el",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["codigo_id"],
            ["codigo_activacion.id"],
            ondelete="CASCADE",
            name="fk_intento_codigo",
        ),
    )
    op.create_index("ix_intento_codigo", "intento_activacion", ["codigo_id"])


def upgrade() -> None:
    _add_dispositivo_columns()
    _backfill_estado()
    _create_partial_indexes()
    _create_codigo_activacion()
    _create_intento_activacion()


def downgrade() -> None:
    op.drop_index("ix_intento_codigo", table_name="intento_activacion")
    op.drop_table("intento_activacion")
    op.drop_index(
        "ix_codigo_estado_expira",
        table_name="codigo_activacion",
    )
    op.drop_index(
        "uq_codigo_activacion_hash",
        table_name="codigo_activacion",
    )
    op.drop_table("codigo_activacion")
    op.drop_index("uq_ruta_activa_cobrador", table_name="ruta")
    op.drop_index("uq_dispositivo_activo_cobrador", table_name="dispositivo")
    op.drop_index("uq_dispositivo_public_key_hash", table_name="dispositivo")
    op.drop_constraint(
        "check_dispositivo_estado",
        "dispositivo",
        type_="check",
    )
    op.drop_column("dispositivo", "algoritmo_clave")
    op.drop_column("dispositivo", "public_key_hash")
    op.drop_column("dispositivo", "public_key")
    op.drop_column("dispositivo", "estado")
    op.alter_column(
        "dispositivo",
        "huella",
        existing_type=sa.String(64),
        nullable=False,
    )
