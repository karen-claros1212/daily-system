"""m10 audit_log extensible + documento unico — W1 hardening (H2 + H4).

Revision ID: m10_audit_documento
Revises: m9_audit_log
Create Date: 2026-08-15

Migracion forward-only que:
1. Elimina el CHECK cerrada en action (permitir acciones futuras sin migracion).
2. Crea unique index parcial (negocio_id, documento) WHERE documento IS NOT NULL.
3. Corrige typo: USUARIO_DESATIVADO -> USUARIO_DESACTIVADO en el CHECK (si se mantiene).

Mapear el typo en la DB: renombrar filas existentes.
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "m10_audit_documento"
down_revision = "m9_audit_log"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Corregir typo en datos existentes
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "UPDATE audit_log SET action = 'USUARIO_DESACTIVADO' "
            "WHERE action = 'USUARIO_DESATIVADO'"
        )
    )

    # 2. Drop CHECK constraint cerrada
    op.drop_constraint("check_audit_action", "audit_log", type_="check")

    # 3. Crear unique index parcial (negocio_id, documento) WHERE documento IS NOT NULL
    #    Solo para PostgreSQL; SQLite no soporta partial indexes.
    op.create_index(
        "uq_usuario_negocio_documento",
        "usuario",
        ["negocio_id", "documento"],
        unique=True,
        postgresql_where=sa.text("documento IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_usuario_negocio_documento",
        table_name="usuario",
        postgresql_where=sa.text("documento IS NOT NULL"),
    )

    # Restaurar CHECK constraint cerrada
    op.create_check_constraint(
        "check_audit_action",
        "audit_log",
        "action IN ("
        "'USUARIO_CREADO', 'USUARIO_ACTIVADO', 'USUARIO_DESACTIVADO', "
        "'USUARIO_EDITADO', "
        "'RUTA_CREADA', 'RUTA_EDITADA', 'RUTA_ELIMINADA', "
        "'DISPOSITIVO_REGISTRADO', 'DISPOSITIVO_REVOCADO', 'DISPOSITIVO_REEMPLAZADO', "
        "'CODIGO_ACTIVACION_CREADO', "
        "'NEGOCIO_ACTUALIZADO', "
        "'JORNADA_CERRADA', "
        "'PAGO_REGISTRADO', 'PAGO_REVERSADO', "
        "'CREDITO_CREADO', 'CREDITO_EDITADO', 'CREDITO_ELIMINADO' "
        ")",
    )
