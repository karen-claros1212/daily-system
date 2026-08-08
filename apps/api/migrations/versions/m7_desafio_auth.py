"""m7 desafio_auth (sesion daily-auth-v1 — Bloque 7, D7-H2)

Revision ID: m7_desafio_auth
Revises: m6_dispositivo_version
Create Date: 2026-08-08

Migracion de EXPANSION y REVERSIBLE (expand-and-contract). NO contrae nada.

Semantica (D7-H2, renovacion 2 pasos persistida):
- `desafio_auth` materializa el challenge de renovacion de sesion: un unico
  mecanismo (POST /api/auth/device/desafio + /canjear) emite el primer JWT
  post-activacion y todos los posteriores (una sola arquitectura de sesion).
- Single-use: `consumido_el` marca el uso; el replay del mismo challenge_id
  devuelve 409 (decision explicita del proyecto). `expira_el` lo controla el
  servidor; `nonce` es CSPRNG >= 32 bytes.

Upgrade:   crea la tabla desafio_auth (id, dispositivo_id, nonce,
           public_key_hash, expira_el, consumido_el, creado_el) + indice por
           dispositivo.

Downgrade: solo contrae desafio_auth. No toca m6 ni datos legacy.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "m7_desafio_auth"
down_revision = "m6_dispositivo_version"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "desafio_auth",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "dispositivo_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("nonce", sa.String(64), nullable=False),
        sa.Column("public_key_hash", sa.String(64), nullable=False),
        sa.Column("expira_el", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumido_el", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "creado_el",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["dispositivo_id"],
            ["dispositivo.id"],
            ondelete="CASCADE",
            name="fk_desafio_dispositivo",
        ),
    )
    op.create_index(
        "ix_desafio_auth_dispositivo",
        "desafio_auth",
        ["dispositivo_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_desafio_auth_dispositivo", table_name="desafio_auth")
    op.drop_table("desafio_auth")
