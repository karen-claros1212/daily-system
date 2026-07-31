"""empty message

Revision ID: init
Revises:
Create Date: 2026-07-28

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'init'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- negocio ---
    op.create_table(
        'negocio',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('nombre', sa.String(255), nullable=False),
        sa.Column('nit', sa.String(50)),
        sa.Column('pais', sa.String(3), nullable=False, server_default='CO'),
        sa.Column('moneda', sa.String(3), nullable=False, server_default='COP'),
        sa.Column('zona_horaria', sa.String(50), nullable=False, server_default='America/Bogota'),
        sa.Column('plan', sa.String(50), nullable=False, server_default='basic'),
        sa.Column('estado_suscripcion', sa.String(20), nullable=False, server_default='al_dia'),
        sa.Column('paid_through_at', sa.DateTime()),
        sa.Column('creado_el', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # --- usuario ---
    op.create_table(
        'usuario',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('negocio_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('rol', sa.String(20), nullable=False),
        sa.Column('nombre', sa.String(255), nullable=False),
        sa.Column('documento', sa.String(50)),
        sa.Column('telegram_id', sa.Integer),
        sa.Column('activo', sa.Integer, nullable=False, server_default='1'),
        sa.Column('creado_el', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['negocio_id'], ['negocio.id'], ondelete='CASCADE'),
        sa.CheckConstraint("rol IN ('INVERSIONISTA', 'ADMINISTRADOR', 'COBRADOR')", name='check_rol_valido'),
    )

    # --- ruta ---
    op.create_table(
        'ruta',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('negocio_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('nombre', sa.String(100), nullable=False),
        sa.Column('cobrador_id', postgresql.UUID(as_uuid=True)),
        sa.Column('activa', sa.Integer, nullable=False, server_default='1'),
        sa.Column('version', sa.Integer, nullable=False, server_default='1'),
        sa.Column('creado_el', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['negocio_id'], ['negocio.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('negocio_id', 'nombre', name='uq_ruta_nombre_negocio'),
    )

    # --- cliente ---
    op.create_table(
        'cliente',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('negocio_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tipo_documento', sa.String(20)),
        sa.Column('documento_normalizado', sa.String(50)),
        sa.Column('identity_status', sa.String(20), nullable=False, server_default='PROVISIONAL'),
        sa.Column('primer_apellido', sa.String(100)),
        sa.Column('segundo_apellido', sa.String(100)),
        sa.Column('nombres', sa.String(200)),
        sa.Column('telefono_1', sa.String(20)),
        sa.Column('telefono_2', sa.String(20)),
        sa.Column('direccion', sa.String(300)),
        sa.Column('barrio', sa.String(100)),
        sa.Column('ciudad', sa.String(100)),
        sa.Column('ocupacion', sa.String(100)),
        sa.Column('creado_el', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['negocio_id'], ['negocio.id'], ondelete='CASCADE'),
        sa.CheckConstraint("identity_status IN ('PROVISIONAL', 'VERIFIED', 'POSSIBLE_DUPLICATE')", name='check_identity_status'),
    )

    # --- credito ---
    op.create_table(
        'credito',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('negocio_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('cliente_id', postgresql.UUID(as_uuid=True)),
        sa.Column('ruta_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('origination_type', sa.String(20), nullable=False, server_default='NEW'),
        sa.Column('cuota', sa.Integer, nullable=False),
        sa.Column('n_cuotas', sa.Integer, nullable=False),
        sa.Column('monto', sa.Integer, nullable=False),
        sa.Column('total', sa.Integer, nullable=False),
        sa.Column('periodicidad', sa.String(20), nullable=False, server_default='DIARIO'),
        sa.Column('dia_semana', sa.Integer),
        sa.Column('ancla_quincenal', sa.String(10)),
        sa.Column('fecha_inicio', sa.Date, nullable=False),
        sa.Column('estado', sa.String(20), nullable=False, server_default='ACTIVO'),
        sa.Column('credito_anterior_id', postgresql.UUID(as_uuid=True)),
        sa.Column('tasa_efectiva_anual', sa.Numeric(10, 6)),
        sa.Column('residuo_redondeo', sa.Integer, server_default='0'),
        sa.Column('version', sa.Integer, nullable=False, server_default='1'),
        sa.Column('creado_el', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['negocio_id'], ['negocio.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['cliente_id'], ['cliente.id']),
        sa.ForeignKeyConstraint(['ruta_id'], ['ruta.id']),
        sa.ForeignKeyConstraint(['credito_anterior_id'], ['credito.id']),
        sa.CheckConstraint("origination_type IN ('NEW', 'RETURNING', 'PARALLEL', 'RENEWAL')", name='check_origination_type'),
        sa.CheckConstraint("periodicidad IN ('DIARIO', 'SEMANAL', 'QUINCENAL', 'UNICA')", name='check_periodicidad'),
        sa.CheckConstraint("estado IN ('ACTIVO', 'PAGADO', 'REFINANCIADO', 'CANCELADO')", name='check_credito_estado'),
        sa.CheckConstraint('total = cuota * n_cuotas', name='check_total_contractual'),
    )

    # --- cuota_programada ---
    op.create_table(
        'cuota_programada',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('negocio_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('credito_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('numero', sa.Integer, nullable=False),
        sa.Column('fecha_vencimiento', sa.Date, nullable=False),
        sa.Column('monto', sa.Integer, nullable=False),
        sa.Column('estado', sa.String(20), nullable=False, server_default='PENDIENTE'),
        sa.ForeignKeyConstraint(['negocio_id'], ['negocio.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['credito_id'], ['credito.id']),
        sa.CheckConstraint("estado IN ('PENDIENTE', 'PAGADO', 'VENCIDO', 'RENANCIADO')", name='check_cuota_estado'),
        sa.UniqueConstraint('credito_id', 'numero', name='uq_cuota_numero'),
    )

    # --- jornada ---
    op.create_table(
        'jornada',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('negocio_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('ruta_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('cobrador_id', postgresql.UUID(as_uuid=True)),
        sa.Column('fecha', sa.Date, nullable=False),
        sa.Column('estado', sa.String(30), nullable=False, server_default='OPEN'),
        sa.Column('opening_base', sa.Integer, nullable=False, server_default='0'),
        sa.Column('opening_carry', sa.Integer, nullable=False, server_default='0'),
        sa.Column('esperado', sa.Integer, nullable=False, server_default='0'),
        sa.Column('contado', sa.Integer, nullable=False, server_default='0'),
        sa.Column('diferencia', sa.Integer, nullable=False, server_default='0'),
        sa.Column('diferencia_motivo', sa.String(300)),
        sa.Column('sobrante_manana', sa.Integer, nullable=False, server_default='0'),
        sa.Column('cerrada_local_el', sa.DateTime(timezone=True)),
        sa.Column('recibida_servidor_el', sa.DateTime(timezone=True)),
        sa.Column('sincronizada_el', sa.DateTime(timezone=True)),
        sa.Column('creado_el', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['negocio_id'], ['negocio.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['ruta_id'], ['ruta.id']),
        sa.ForeignKeyConstraint(['cobrador_id'], ['usuario.id']),
        sa.CheckConstraint("estado IN ('OPEN', 'CLOSING', 'CLOSED_LOCAL_PENDING_SYNC', 'CLOSED_SYNCED')", name='check_jornada_estado'),
        sa.UniqueConstraint('negocio_id', 'ruta_id', 'fecha', name='uq_jornada_fecha'),
    )

    # --- pago ---
    op.create_table(
        'pago',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('negocio_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('credito_id', postgresql.UUID(as_uuid=True)),
        sa.Column('jornada_id', postgresql.UUID(as_uuid=True)),
        sa.Column('cobrador_id', postgresql.UUID(as_uuid=True)),
        sa.Column('dispositivo_id', postgresql.UUID(as_uuid=True)),
        sa.Column('tipo', sa.String(20), nullable=False),
        sa.Column('reversal_of_payment_id', postgresql.UUID(as_uuid=True)),
        sa.Column('monto', sa.Integer, nullable=False),
        sa.Column('registrado_el_dispositivo', sa.DateTime(timezone=True)),
        sa.Column('recibido_el_servidor', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('clave_idempotencia', sa.String(100), nullable=False),
        sa.Column('nota', sa.Text),
        sa.ForeignKeyConstraint(['negocio_id'], ['negocio.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['credito_id'], ['credito.id']),
        sa.ForeignKeyConstraint(['jornada_id'], ['jornada.id']),
        sa.ForeignKeyConstraint(['cobrador_id'], ['usuario.id']),
        sa.ForeignKeyConstraint(['reversal_of_payment_id'], ['pago.id']),
        sa.CheckConstraint("tipo IN ('PAYMENT', 'REVERSAL')", name='check_pago_tipo'),
        sa.UniqueConstraint('negocio_id', 'clave_idempotencia', name='uq_pago_idempotencia'),
    )

    # --- movimiento_caja ---
    op.create_table(
        'movimiento_caja',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('negocio_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('jornada_id', postgresql.UUID(as_uuid=True)),
        sa.Column('tipo', sa.String(50), nullable=False),
        sa.Column('naturaleza', sa.String(50)),
        sa.Column('monto', sa.Integer, nullable=False),
        sa.Column('nota', sa.Text),
        sa.Column('creado_por', postgresql.UUID(as_uuid=True)),
        sa.Column('creado_el', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['negocio_id'], ['negocio.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['jornada_id'], ['jornada.id']),
        sa.CheckConstraint("tipo IN ('GASOLINA', 'OFICINA', 'AHORRO', 'VALE', 'ENTREGA', 'RECIBIDO', 'DESEMBOLSO', 'AJUSTE', 'OTRO')", name='check_movimiento_tipo'),
        sa.CheckConstraint("naturaleza IN ('GASTO', 'CUSTODIA', 'CUENTA_POR_COBRAR', 'TRASLADO_ENTRADA', 'TRASLADO_SALIDA', 'DESEMBOLSO', 'AJUSTE')", name='check_movimiento_naturaleza'),
    )

    # --- renovacion ---
    op.create_table(
        'renovacion',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('negocio_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('credito_viejo_id', postgresql.UUID(as_uuid=True)),
        sa.Column('credito_nuevo_id', postgresql.UUID(as_uuid=True)),
        sa.Column('saldo_anterior', sa.Integer, nullable=False),
        sa.Column('pago_efectivo', sa.Integer, nullable=False, server_default='0'),
        sa.Column('saldo_refinanciado', sa.Integer, nullable=False),
        sa.Column('monto_nuevo', sa.Integer, nullable=False),
        sa.Column('dinero_nuevo_entregado', sa.Integer, nullable=False, server_default='0'),
        sa.Column('creado_por', postgresql.UUID(as_uuid=True)),
        sa.Column('creado_el', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['negocio_id'], ['negocio.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['credito_viejo_id'], ['credito.id']),
        sa.ForeignKeyConstraint(['credito_nuevo_id'], ['credito.id']),
        sa.CheckConstraint('saldo_anterior = pago_efectivo + saldo_refinanciado', name='check_renovacion_saldo'),
    )


def downgrade() -> None:
    op.drop_table('renovacion')
    op.drop_table('movimiento_caja')
    op.drop_table('pago')
    op.drop_table('jornada')
    op.drop_table('cuota_programada')
    op.drop_table('credito')
    op.drop_table('cliente')
    op.drop_table('ruta')
    op.drop_table('usuario')
    op.drop_table('negocio')
