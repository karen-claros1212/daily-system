"""m6 dispositivo version_asignacion (auth productiva — Bloque 7)

Revision ID: m6_dispositivo_version_asignacion
Revises: m5_dispositivo_activacion
Create Date: 2026-08-06

Migracion de EXPANSION y REVERSIBLE (expand-and-contract). NO contrae nada.

Semantica (auth productiva, D7-01/02):
- `dispositivo.version_asignacion` se incrementa en cada revocacion, reemplazo
  o reasignacion del dispositivo. El JWT productivo lleva ESTE numero como
  claim; el servidor revalida contra la base en cada request, de modo que un
  token vigente muere al instante cuando el contador cambia (efecto inmediato,
  sin esperar a la expiracion del token).

Upgrade:
  dispositivo: + version_asignacion Integer NOT NULL server_default '1'.

Downgrade: solo contrae version_asignacion. No toca m5 ni datos legacy.
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "m6_dispositivo_version"
down_revision = "m5_dispositivo_activacion"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "dispositivo",
        sa.Column(
            "version_asignacion",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
    )


def downgrade() -> None:
    op.drop_column("dispositivo", "version_asignacion")
