"""m9 audit_log — tabla de auditoria append-only (W1, A1).

Revision ID: m9_audit_log
Revises: m8_negocio_nit
Create Date: 2026-08-15

Migracion FORWARD-ONLY. Crea la tabla audit_log con:
- negocio_id (FK -> negocio.id CASCADE)
- actor_id (FK -> usuario.id)
- action (CHECK: lista de acciones validas)
- entity_type, entity_id
- metadata_col (JSONB)
- ip_address, user_agent
- creado_el (server default now)

Indices: negocio_id+creado_el (query por negocio), entity_type+entity_id
(query por entidad), action (query por tipo).
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "m9_audit_log"
down_revision = "m8_negocio_nit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audit_log",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("negocio_id", sa.Uuid(), sa.ForeignKey("negocio.id", ondelete="CASCADE"), nullable=False),
        sa.Column("actor_id", sa.Uuid(), sa.ForeignKey("usuario.id"), nullable=False),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=True),
        sa.Column("metadata_col", sa.dialects.postgresql.JSONB(), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(500), nullable=True),
        sa.Column(
            "creado_el",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "action IN ("
            "'USUARIO_CREADO', 'USUARIO_ACTIVADO', 'USUARIO_DESATIVADO', "
            "'USUARIO_EDITADO', "
            "'RUTA_CREADA', 'RUTA_EDITADA', 'RUTA_ELIMINADA', "
            "'DISPOSITIVO_REGISTRADO', 'DISPOSITIVO_REVOCADO', 'DISPOSITIVO_REEMPLAZADO', "
            "'CODIGO_ACTIVACION_CREADO', "
            "'NEGOCIO_ACTUALIZADO', "
            "'JORNADA_CERRADA', "
            "'PAGO_REGISTRADO', 'PAGO_REVERSADO', "
            "'CREDITO_CREADO', 'CREDITO_EDITADO', 'CREDITO_ELIMINADO' "
            ")",
            name="check_audit_action",
        ),
    )

    op.create_index("ix_audit_log_negocio_creado", "audit_log", ["negocio_id", "creado_el"])
    op.create_index("ix_audit_log_entity", "audit_log", ["entity_type", "entity_id"])
    op.create_index("ix_audit_log_action", "audit_log", ["action"])


def downgrade() -> None:
    op.drop_index("ix_audit_log_action", table_name="audit_log")
    op.drop_index("ix_audit_log_entity", table_name="audit_log")
    op.drop_index("ix_audit_log_negocio_creado", table_name="audit_log")
    op.drop_table("audit_log")
