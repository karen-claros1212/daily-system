import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from src.database import Base


class Negocio(Base):
    __tablename__ = "negocio"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nombre = Column(String(255), nullable=False)
    nit = Column(String(50))
    pais = Column(String(3), nullable=False, default="CO")
    moneda = Column(String(3), nullable=False, default="COP")
    zona_horaria = Column(String(50), nullable=False, default="America/Bogota")
    plan = Column(String(50), nullable=False, default="basic")
    estado_suscripcion = Column(
        String(20),
        nullable=False,
        default="al_dia",
    )
    paid_through_at = Column(DateTime)
    creado_el = Column(DateTime(timezone=True), server_default=func.now())

    usuarios = relationship("Usuario", back_populates="negocio")
    rutas = relationship("Ruta", back_populates="negocio")
    clientes = relationship("Cliente", back_populates="negocio")
    creditos = relationship("Credito", back_populates="negocio")
    dispositivos = relationship("Dispositivo", back_populates="negocio")


class Usuario(Base):
    __tablename__ = "usuario"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    negocio_id = Column(
        UUID(as_uuid=True),
        ForeignKey("negocio.id", ondelete="CASCADE"),
        nullable=False,
    )
    rol = Column(
        String(20),
        nullable=False,
    )
    nombre = Column(String(255), nullable=False)
    documento = Column(String(50))
    telegram_id = Column(Integer)
    activo = Column(Integer, nullable=False, default=1)
    creado_el = Column(DateTime(timezone=True), server_default=func.now())

    negocio = relationship("Negocio", back_populates="usuarios")
    rutas = relationship("Ruta", back_populates="cobrador")

    __table_args__ = (
        CheckConstraint(
            "rol IN ('INVERSIONISTA', 'ADMINISTRADOR', 'COBRADOR')",
            name="check_rol_valido",
        ),
    )


class Ruta(Base):
    __tablename__ = "ruta"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    negocio_id = Column(
        UUID(as_uuid=True),
        ForeignKey("negocio.id", ondelete="CASCADE"),
        nullable=False,
    )
    nombre = Column(String(100), nullable=False)
    cobrador_id = Column(
        UUID(as_uuid=True),
        ForeignKey("usuario.id", name="fk_ruta_cobrador"),
    )
    activa = Column(Integer, nullable=False, default=1)
    version = Column(Integer, nullable=False, default=1)
    creado_el = Column(DateTime(timezone=True), server_default=func.now())

    negocio = relationship("Negocio", back_populates="rutas")
    cobrador = relationship("Usuario", back_populates="rutas")
    creditos = relationship("Credito", back_populates="ruta")

    __table_args__ = (
        UniqueConstraint("negocio_id", "nombre", name="uq_ruta_nombre_negocio"),
        Index(
            "uq_ruta_activa_cobrador",
            "cobrador_id",
            unique=True,
            postgresql_where=text("activa = 1 AND cobrador_id IS NOT NULL"),
            sqlite_where=text("activa = 1 AND cobrador_id IS NOT NULL"),
        ),
    )


class Cliente(Base):
    __tablename__ = "cliente"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    negocio_id = Column(
        UUID(as_uuid=True),
        ForeignKey("negocio.id", ondelete="CASCADE"),
        nullable=False,
    )
    tipo_documento = Column(String(20))
    documento_normalizado = Column(String(50))
    identity_status = Column(
        String(20),
        nullable=False,
        default="PROVISIONAL",
    )
    primer_apellido = Column(String(100))
    segundo_apellido = Column(String(100))
    nombres = Column(String(200))
    telefono_1 = Column(String(20))
    telefono_2 = Column(String(20))
    direccion = Column(String(300))
    barrio = Column(String(100))
    ciudad = Column(String(100))
    ocupacion = Column(String(100))
    creado_el = Column(DateTime(timezone=True), server_default=func.now())

    negocio = relationship("Negocio", back_populates="clientes")
    creditos = relationship("Credito", back_populates="cliente")

    __table_args__ = (
        CheckConstraint(
            "identity_status IN ('PROVISIONAL', 'VERIFIED', 'POSSIBLE_DUPLICATE')",
            name="check_identity_status",
        ),
    )


class Credito(Base):
    __tablename__ = "credito"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    negocio_id = Column(
        UUID(as_uuid=True),
        ForeignKey("negocio.id", ondelete="CASCADE"),
        nullable=False,
    )
    cliente_id = Column(
        UUID(as_uuid=True),
        ForeignKey("cliente.id"),
    )
    ruta_id = Column(
        UUID(as_uuid=True),
        ForeignKey("ruta.id"),
        nullable=False,
    )
    origination_type = Column(
        String(20),
        nullable=False,
        default="NEW",
    )
    cuota = Column(Integer, nullable=False)
    n_cuotas = Column(Integer, nullable=False)
    monto = Column(Integer, nullable=False)
    total = Column(Integer, nullable=False)
    periodicidad = Column(
        String(20),
        nullable=False,
        default="DIARIO",
    )
    dia_semana = Column(Integer)
    ancla_quincenal = Column(String(10))
    fecha_inicio = Column(Date, nullable=False)
    estado = Column(
        String(20),
        nullable=False,
        default="ACTIVO",
    )
    credito_anterior_id = Column(
        UUID(as_uuid=True),
        ForeignKey("credito.id"),
    )
    tasa_efectiva_anual = Column(Numeric(10, 6))
    residuo_redondeo = Column(Integer, default=0)
    version = Column(Integer, nullable=False, default=1)
    creado_el = Column(DateTime(timezone=True), server_default=func.now())

    negocio = relationship("Negocio", back_populates="creditos")
    cliente = relationship("Cliente", back_populates="creditos")
    ruta = relationship("Ruta", back_populates="creditos")
    cuotas = relationship("CuotaProgramada", back_populates="credito")
    pagos = relationship("Pago", back_populates="credito")
    renovacion_vieja = relationship(
        "Renovacion",
        foreign_keys="Renovacion.credito_viejo_id",
        back_populates="credito_viejo",
    )
    renovacion_nueva = relationship(
        "Renovacion",
        foreign_keys="Renovacion.credito_nuevo_id",
        back_populates="credito_nuevo",
    )

    __table_args__ = (
        CheckConstraint(
            "origination_type IN ('NEW', 'RETURNING', 'PARALLEL', 'RENEWAL')",
            name="check_origination_type",
        ),
        CheckConstraint(
            "periodicidad IN ('DIARIO', 'SEMANAL', 'QUINCENAL', 'UNICA')",
            name="check_periodicidad",
        ),
        CheckConstraint(
            "estado IN ('ACTIVO', 'PAGADO', 'REFINANCIADO', 'CANCELADO')",
            name="check_credito_estado",
        ),
        CheckConstraint(
            "total = cuota * n_cuotas",
            name="check_total_contractual",
        ),
    )


class CuotaProgramada(Base):
    __tablename__ = "cuota_programada"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    negocio_id = Column(
        UUID(as_uuid=True),
        ForeignKey("negocio.id", ondelete="CASCADE"),
        nullable=False,
    )
    credito_id = Column(
        UUID(as_uuid=True),
        ForeignKey("credito.id"),
        nullable=False,
    )
    numero = Column(Integer, nullable=False)
    fecha_vencimiento = Column(Date, nullable=False)
    monto = Column(Integer, nullable=False)
    estado = Column(
        String(20),
        nullable=False,
        default="PENDIENTE",
    )

    credito = relationship("Credito", back_populates="cuotas")

    __table_args__ = (
        CheckConstraint(
            "estado IN ('PENDIENTE', 'PAGADO', 'VENCIDO', 'RENANCIADO')",
            name="check_cuota_estado",
        ),
        UniqueConstraint(
            "credito_id", "numero", name="uq_cuota_numero"
        ),
    )


class Jornada(Base):
    __tablename__ = "jornada"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    negocio_id = Column(
        UUID(as_uuid=True),
        ForeignKey("negocio.id", ondelete="CASCADE"),
        nullable=False,
    )
    ruta_id = Column(
        UUID(as_uuid=True),
        ForeignKey("ruta.id"),
        nullable=False,
    )
    cobrador_id = Column(
        UUID(as_uuid=True),
        ForeignKey("usuario.id"),
    )
    fecha = Column(Date, nullable=False)
    estado = Column(
        String(30),
        nullable=False,
        default="OPEN",
    )
    opening_base = Column(Integer, nullable=False, default=0)
    opening_carry = Column(Integer, nullable=False, default=0)
    esperado = Column(Integer, nullable=False, default=0)
    contado = Column(Integer, nullable=False, default=0)
    diferencia = Column(Integer, nullable=False, default=0)
    diferencia_motivo = Column(String(300))
    sobrante_manana = Column(Integer, nullable=False, default=0)
    cerrada_local_el = Column(DateTime(timezone=True))
    recibida_servidor_el = Column(DateTime(timezone=True))
    sincronizada_el = Column(DateTime(timezone=True))
    creado_el = Column(DateTime(timezone=True), server_default=func.now())
    actualizado_el = Column(DateTime(timezone=True), onupdate=func.now())
    apertura_idempotency_key = Column(String(100))
    cierre_idempotency_key = Column(String(100))
    cierre_snapshot_json = Column(JSONB().with_variant(JSON(), "sqlite"))
    cierre_snapshot_hash = Column(String(64))
    cierre_version = Column(Integer, nullable=False, default=1)
    cerrada_por = Column(UUID(as_uuid=True))

    movimientos = relationship("MovimientoCaja", back_populates="jornada")

    __table_args__ = (
        CheckConstraint(
            "estado IN ("
            "'OPEN', 'CLOSING', "
            "'CLOSED_LOCAL_PENDING_SYNC', "
            "'CLOSED_SYNCED'"
            ")",
            name="check_jornada_estado",
        ),
        UniqueConstraint("negocio_id", "ruta_id", "fecha", name="uq_jornada_fecha"),
        UniqueConstraint("negocio_id", "cierre_idempotency_key", name="uq_jornada_cierre_key"),
        UniqueConstraint("negocio_id", "apertura_idempotency_key", name="uq_jornada_apertura_key"),
    )


class Pago(Base):
    __tablename__ = "pago"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    negocio_id = Column(
        UUID(as_uuid=True),
        ForeignKey("negocio.id", ondelete="CASCADE"),
        nullable=False,
    )
    credito_id = Column(
        UUID(as_uuid=True),
        ForeignKey("credito.id"),
    )
    jornada_id = Column(
        UUID(as_uuid=True),
        ForeignKey("jornada.id"),
    )
    cobrador_id = Column(
        UUID(as_uuid=True),
        ForeignKey("usuario.id"),
    )
    dispositivo_id = Column(UUID(as_uuid=True))
    tipo = Column(
        String(20),
        nullable=False,
    )
    reversal_of_payment_id = Column(
        UUID(as_uuid=True),
        ForeignKey("pago.id"),
    )
    monto = Column(Integer, nullable=False)
    registrado_el_dispositivo = Column(DateTime(timezone=True))
    recibido_el_servidor = Column(DateTime(timezone=True), server_default=func.now())
    clave_idempotencia = Column(String(100), nullable=False)
    nota = Column(Text)

    credito = relationship("Credito", back_populates="pagos")

    __table_args__ = (
        CheckConstraint(
            "tipo IN ('PAYMENT', 'REVERSAL')",
            name="check_pago_tipo",
        ),
        UniqueConstraint(
            "negocio_id", "clave_idempotencia", name="uq_pago_idempotencia"
        ),
    )


class MovimientoCaja(Base):
    __tablename__ = "movimiento_caja"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    negocio_id = Column(
        UUID(as_uuid=True),
        ForeignKey("negocio.id", ondelete="CASCADE"),
        nullable=False,
    )
    jornada_id = Column(
        UUID(as_uuid=True),
        ForeignKey("jornada.id"),
    )
    tipo = Column(String(50), nullable=False)
    naturaleza = Column(String(50))
    monto = Column(Integer, nullable=False)
    nota = Column(Text)
    creado_por = Column(UUID(as_uuid=True))
    creado_el = Column(DateTime(timezone=True), server_default=func.now())
    clave_idempotencia = Column(String(100))
    registrado_el_dispositivo = Column(DateTime(timezone=True))
    recibido_el_servidor = Column(DateTime(timezone=True))
    dispositivo_id = Column(UUID(as_uuid=True))
    credito_id = Column(
        UUID(as_uuid=True),
        ForeignKey("credito.id", name="fk_movimiento_credito", ondelete="SET NULL"),
    )
    renovacion_id = Column(
        UUID(as_uuid=True),
        ForeignKey(
            "renovacion.id", name="fk_movimiento_renovacion", ondelete="SET NULL"
        ),
    )
    ajuste_de_movimiento_id = Column(
        UUID(as_uuid=True),
        ForeignKey(
            "movimiento_caja.id",
            name="fk_movimiento_ajuste",
            ondelete="SET NULL",
        ),
    )

    jornada = relationship("Jornada", back_populates="movimientos")
    credito = relationship("Credito")
    renovacion = relationship("Renovacion")
    ajuste_de = relationship(
        "MovimientoCaja",
        remote_side=[id],
    )

    __table_args__ = (
        CheckConstraint(
            "tipo IN ("
            "'GASOLINA', 'OFICINA', 'AHORRO', 'VALE', 'ENTREGA', "
            "'RECIBIDO', 'DESEMBOLSO', 'AJUSTE', 'OTRO'"
            ")",
            name="check_movimiento_tipo",
        ),
        CheckConstraint(
            "naturaleza IN ("
            "'GASTO', 'CUSTODIA', 'CUENTA_POR_COBRAR', "
            "'TRASLADO_ENTRADA', 'TRASLADO_SALIDA', "
            "'DESEMBOLSO', 'AJUSTE'"
            ")",
            name="check_movimiento_naturaleza",
        ),
        UniqueConstraint("negocio_id", "clave_idempotencia", name="uq_movimiento_idempotencia"),
    )


class Renovacion(Base):
    __tablename__ = "renovacion"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    negocio_id = Column(
        UUID(as_uuid=True),
        ForeignKey("negocio.id", ondelete="CASCADE"),
        nullable=False,
    )
    credito_viejo_id = Column(
        UUID(as_uuid=True),
        ForeignKey("credito.id"),
    )
    credito_nuevo_id = Column(
        UUID(as_uuid=True),
        ForeignKey("credito.id"),
    )
    saldo_anterior = Column(Integer, nullable=False)
    pago_efectivo = Column(Integer, nullable=False, default=0)
    saldo_refinanciado = Column(Integer, nullable=False)
    monto_nuevo = Column(Integer, nullable=False)
    dinero_nuevo_entregado = Column(Integer, nullable=False, default=0)
    creado_por = Column(UUID(as_uuid=True))
    creado_el = Column(DateTime(timezone=True), server_default=func.now())

    credito_viejo = relationship(
        "Credito",
        foreign_keys=[credito_viejo_id],
        back_populates="renovacion_vieja",
    )
    credito_nuevo = relationship(
        "Credito",
        foreign_keys=[credito_nuevo_id],
        back_populates="renovacion_nueva",
    )

    __table_args__ = (
        CheckConstraint(
            "saldo_anterior = pago_efectivo + saldo_refinanciado",
            name="check_renovacion_saldo",
        ),
    )


class Dispositivo(Base):
    """El celular del cobrador. Nace en ACTIVE directamente del canje.

    Ciclo de estados: ACTIVE -> REVOKED (revocacion) | REPLACED (reemplazo).
    No existe PENDING_ACTIVATION ni EXPIRED: el dispositivo se CREA al canjear.

    Expand-and-contract: la columna legacy `huella` se conserva (nullable) para
    el registro administrativo previo; los dispositivos nacidos del canje usan
    `public_key` (SPKI canonico) + `public_key_hash`. El contrato de activacion
    (revision 4) no permite contraer (drop) de huella todavia.
    """

    __tablename__ = "dispositivo"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    negocio_id = Column(
        UUID(as_uuid=True),
        ForeignKey("negocio.id", ondelete="CASCADE"),
        nullable=False,
    )
    usuario_id = Column(
        UUID(as_uuid=True),
        ForeignKey("usuario.id"),
    )
    huella = Column(String(64))
    public_key = Column(Text)
    public_key_hash = Column(String(64))
    algoritmo_clave = Column(String(20))
    modelo = Column(String(200))
    plataforma = Column(String(20))
    estado = Column(String(20), nullable=False, default="ACTIVE")
    version_asignacion = Column(Integer, nullable=False, default=1, server_default="1")
    autorizado_por = Column(UUID(as_uuid=True))
    autorizado_el = Column(DateTime(timezone=True))
    revocado_el = Column(DateTime(timezone=True))
    ultima_validacion_servidor = Column(DateTime(timezone=True))
    activo = Column(Integer, nullable=False, default=1)
    creado_el = Column(DateTime(timezone=True), server_default=func.now())

    negocio = relationship("Negocio", back_populates="dispositivos")

    __table_args__ = (
        UniqueConstraint("negocio_id", "huella", name="uq_dispositivo_huella"),
        Index(
            "uq_dispositivo_public_key_hash",
            "public_key_hash",
            unique=True,
            postgresql_where=text("public_key_hash IS NOT NULL"),
            sqlite_where=text("public_key_hash IS NOT NULL"),
        ),
        Index(
            "uq_dispositivo_activo_cobrador",
            "usuario_id",
            unique=True,
            postgresql_where=text(
                "estado = 'ACTIVE' AND usuario_id IS NOT NULL"
            ),
            sqlite_where=text(
                "estado = 'ACTIVE' AND usuario_id IS NOT NULL"
            ),
        ),
        CheckConstraint(
            "estado IN ('ACTIVE', 'REVOKED', 'REPLACED')",
            name="check_dispositivo_estado",
        ),
        CheckConstraint(
            "plataforma IN ('android', 'ios', 'web', 'linux', 'windows', 'macos', 'other')",
            name="check_dispositivo_plataforma",
        ),
    )


class CodigoActivacion(Base):
    """Codigo de un solo uso para activar un dispositivo (QR/admin).

    El servidor guarda SOLO el digest SHA-256 del token; el token en claro se
    entrega UNA vez al admin. Estados: PENDING -> CONSUMED | EXPIRED |
    CANCELLED. `credencial_bootstrap` es la credencial de corta vigencia
    devuelta en el canje (permite reintento idempotente con el mismo intento).
    """

    __tablename__ = "codigo_activacion"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    negocio_id = Column(
        UUID(as_uuid=True),
        ForeignKey("negocio.id", ondelete="CASCADE"),
        nullable=False,
    )
    cobrador_id = Column(
        UUID(as_uuid=True),
        ForeignKey("usuario.id"),
        nullable=False,
    )
    hash_codigo = Column(String(64), nullable=False)
    prefijo = Column(String(8), nullable=False)
    expira_el = Column(DateTime(timezone=True), nullable=False)
    intentos_fallidos = Column(Integer, nullable=False, default=0)
    estado = Column(String(20), nullable=False, default="PENDING")
    consumido_el = Column(DateTime(timezone=True))
    dispositivo_id_canjeado = Column(
        UUID(as_uuid=True),
        ForeignKey("dispositivo.id"),
    )
    credencial_bootstrap = Column(String(128))
    credencial_bootstrap_expira_el = Column(DateTime(timezone=True))
    creado_por = Column(UUID(as_uuid=True), ForeignKey("usuario.id"))
    entregado_el = Column(DateTime(timezone=True))
    creado_el = Column(DateTime(timezone=True), server_default=func.now())

    intentos = relationship(
        "IntentoActivacion",
        back_populates="codigo",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index(
            "uq_codigo_activacion_hash",
            "hash_codigo",
            unique=True,
        ),
        Index("ix_codigo_estado_expira", "estado", "expira_el"),
        CheckConstraint(
            "estado IN ('PENDING', 'CONSUMED', 'EXPIRED', 'CANCELLED')",
            name="check_codigo_activacion_estado",
        ),
    )


class IntentoActivacion(Base):
    """Intento de canje de UN SOLO USO (challenge-response).

    Creado en el desafio (no consume el codigo). Contiene el `nonce` CSPRNG
    (>= 32 bytes, base64url sin padding) y la clave publica SPKI del par que
    firmara el nonce. `firma_validada_el`/`consumido_el` marcan el uso unico.
    """

    __tablename__ = "intento_activacion"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    codigo_id = Column(
        UUID(as_uuid=True),
        ForeignKey("codigo_activacion.id", ondelete="CASCADE"),
        nullable=False,
    )
    nonce = Column(String(64), nullable=False)
    clave_publica = Column(Text, nullable=False)
    public_key_hash = Column(String(64), nullable=False)
    modelo = Column(String(200))
    plataforma = Column(String(20))
    expira_el = Column(DateTime(timezone=True), nullable=False)
    firma_validada_el = Column(DateTime(timezone=True))
    consumido_el = Column(DateTime(timezone=True))
    creado_el = Column(DateTime(timezone=True), server_default=func.now())

    codigo = relationship("CodigoActivacion", back_populates="intentos")

    __table_args__ = (
        Index("ix_intento_codigo", "codigo_id"),
    )


class DesafioAuth(Base):
    """Desafio de sesion de UN SOLO USO (daily-auth-v1, D7-H2).

    Creado en POST /api/auth/device/desafio; consumido en
    POST /api/auth/device/canjear. Es el UNICO mecanismo que emite access
    tokens ES256: el primer JWT post-activacion (autenticado con la credencial
    bootstrap) y todos los posteriores (autenticado con el JWT vigente).

    Single-use: `consumido_el` marca el uso; el replay del mismo challenge_id
    devuelve 409 (decision explicita del proyecto). El servidor controla
    `expira_el` (el dispositivo firma los bytes exactos emitidos por el
    servidor, no una ventana que elija el cliente).
    """

    __tablename__ = "desafio_auth"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    dispositivo_id = Column(
        UUID(as_uuid=True),
        ForeignKey("dispositivo.id", ondelete="CASCADE"),
        nullable=False,
    )
    nonce = Column(String(64), nullable=False)
    public_key_hash = Column(String(64), nullable=False)
    expira_el = Column(DateTime(timezone=True), nullable=False)
    consumido_el = Column(DateTime(timezone=True))
    creado_el = Column(DateTime(timezone=True), server_default=func.now())

    dispositivo = relationship("Dispositivo")

    __table_args__ = (
        Index("ix_desafio_auth_dispositivo", "dispositivo_id"),
    )
