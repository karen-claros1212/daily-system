"""add fk ruta.cobrador_id -> usuario.id

Revision ID: m4_ruta_cobrador_fk
Revises: m3_dispositivo
Create Date: 2026-08-06

The init migration created ruta.cobrador_id as a plain uuid column without a
foreign key. The model declares ForeignKey("usuario.id"). Add the missing
constraint as a new reversible migration (applied migrations are not rewritten).
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "m4_ruta_cobrador_fk"
down_revision = "m3_dispositivo"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_foreign_key(
        "fk_ruta_cobrador",
        "ruta",
        "usuario",
        ["cobrador_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_ruta_cobrador", "ruta", type_="foreignkey")
