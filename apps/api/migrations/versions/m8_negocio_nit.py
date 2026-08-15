"""m8 negocio.nit — invariante de NIT garantizada por la base de datos
(HARDENING FINAL ONBOARDING, defecto 1)

Revision ID: m8_negocio_nit
Revises: m7_desafio_auth
Create Date: 2026-08-14

Migracion FORWARD-ONLY (expand-and-contract). NO contrae nada y NO toca
migraciones aplicadas.

Semantica (invariante de NIT):
- El NIT de un negocio es unico si esta presente; los NULLs multiples
  conviven (negocios sin NIT). El fast-path `verificar_nit_disponible` (SELECT)
  es solo comodidad UX: la AUTORIDAD del "no hay dos negocios con el mismo
  NIT" queda en el indice unico de la base (race condition imposible).
- Precondicion: la migracion DETECTA duplicados no-null existentes y, si los
  hay, FALLA con diagnostico explicito. NO borra ni fusiona registros.

Upgrade:   detecta duplicados no-null (FAIL con diagnostico) y crea el indice
           unico `uq_negocio_nit` sobre negocio(nit) (NULLs multiples OK).

Downgrade: solo contrae el indice. No toca m7 ni datos legacy.
"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "m8_negocio_nit"
down_revision = "m7_desafio_auth"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    dups = bind.execute(
        sa.text(
            "SELECT nit, count(*) AS n "
            "FROM negocio "
            "WHERE nit IS NOT NULL "
            "GROUP BY nit "
            "HAVING count(*) > 1 "
            "ORDER BY nit"
        )
    ).mappings().all()
    if dups:
        detalle = "; ".join(f"nit={d['nit']!r} x{d['n']}" for d in dups)
        raise RuntimeError(
            "m8_negocio_nit abortada: existen NIT no-null duplicados en "
            f"negocio y la invariante uq_negocio_nit no puede aplicarse. "
            f"Duplicados: {detalle}. Revise los datos manualmente; la "
            "migracion NO borra ni fusiona registros."
        )

    op.create_index(
        "uq_negocio_nit",
        "negocio",
        ["nit"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_negocio_nit", table_name="negocio")
