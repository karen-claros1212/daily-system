"""m10 audit_log extensible + documento unico — W1 hardening (H2 + H4).

Revision ID: m10_audit_documento
Revises: m9_audit_log
Create Date: 2026-08-15

Migracion forward-only que:
1. Elimina el CHECK cerrada en action (permitir acciones futuras sin migracion).
2. Corrige typo: USUARIO_DESATIVADO -> USUARIO_DESACTIVADO en datos existentes.
3. Crea unique index parcial (negocio_id, documento) WHERE documento IS NOT NULL.

Orden critico: DROP CHECK ANTES del UPDATE para que PostgreSQL no rechace
el UPDATE con el valor nuevo que el CHECK viejo no acepta.
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "m10_audit_documento"
down_revision = "m9_audit_log"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Drop CHECK constraint cerrada PRIMERO (permitir valores nuevos)
    op.drop_constraint("check_audit_action", "audit_log", type_="check")

    # 2. Corregir typo en datos existentes (ahora el CHECK ya no bloquea)
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "UPDATE audit_log SET action = 'USUARIO_DESACTIVADO' "
            "WHERE action = 'USUARIO_DESATIVADO'"
        )
    )

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
