"""Servicio de activacion de dispositivos — Contrato de activacion (Bloque 6).

Flujo challenge-response de 2 pasos (seccion 4 del contrato):
  1. POST /api/activaciones/codigos   (ADMIN)   genera codigo de un solo uso
  2. POST /api/activaciones/desafio   (publico) crea IntentoActivacion + nonce
  3. POST /api/activaciones/canjear   (publico) verifica firma JCS + consume

Garantias (cierre revision 4):
  - Intento de UN SOLO uso (reintento idempotente -> misma credencial, nunca
    un segundo dispositivo).
  - nonce CSPRNG >= 32 bytes (secrets.token_urlsafe(32) == 43 base64url).
  - Verificacion + consumo en una sola transaccion con bloqueo de fila
    (SELECT ... FOR UPDATE sobre codigo e intento en PostgreSQL).
  - Serializacion JCS (RFC 8785) byte a byte (src.services.jcs) y
    SHA256withECDSA sobre los bytes exactos; environment impide reuso entre
    ambientes.
  - El cuerpo publico NO acepta negocio_id/cobrador_id/ruta_id/rol/estado:
    el servidor deriva todo desde el codigo.
"""

import base64
import hashlib
import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from sqlalchemy.orm import Session

from src.models import (
    CodigoActivacion,
    Dispositivo,
    IntentoActivacion,
    Negocio,
    Ruta,
    Usuario,
)
from src.services.jcs import (
    PROTOCOL_VERSION,
    build_signed_payload,
    format_rfc3339_seconds,
)

DEFAULT_CODIGO_TTL_MINUTES = 10
DEFAULT_INTENTO_TTL_MINUTES = 5
DEFAULT_BOOTSTRAP_TTL_MINUTES = 5
ALGORITMO_CLAVE = "EC_P256"

CODIGO_CANCELADO = "CANCELLED"
CODIGO_CONSUMIDO = "CONSUMED"
CODIGO_EXPIRADO = "EXPIRED"
CODIGO_PENDIENTE = "PENDING"

MAX_INTENTOS_FALLIDOS = 5


class ActivacionError(Exception):
    """Business error for the activation flow."""

    def __init__(self, detail: str, code: str = "ACTIVACION_ERROR", status_code: int = 400):
        self.detail = detail
        self.code = code
        self.status_code = status_code
        super().__init__(detail)


@dataclass(frozen=True)
class DesafioResult:
    intento_id: UUID
    nonce: str
    expira_el: str
    environment: str


@dataclass(frozen=True)
class CanjeResult:
    dispositivo_id: UUID
    negocio_id: UUID
    cobrador_id: UUID
    credencial_bootstrap: str
    expira_el: str
    idempotente: bool = False


@dataclass(frozen=True)
class BootstrapResult:
    negocio_id: UUID
    negocio_nombre: str
    cobrador_id: UUID
    cobrador_nombre: str
    dispositivo_id: UUID
    ruta_id: UUID
    ruta_nombre: str
    rol: str


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware_utc(dt: datetime | None) -> datetime | None:
    """SQLite devuelve DateTime(timezone=True) como naive; asumir UTC."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def get_active_environment() -> str:
    """Ambiente activo del servidor, segun DAILY_ENV (perfil 13.3.8)."""
    env = os.getenv("DAILY_ENV", "test")
    if env in ("production", "prod"):
        return "production"
    if env in ("staging",):
        return "staging"
    return "development"


def _lock(db: Session, query):
    """SELECT ... FOR UPDATE solo en PostgreSQL (SQLite de tests no lo soporta)."""
    if db.get_bind().dialect.name == "postgresql":
        return query.with_for_update()
    return query


def _parse_clave_publica(clave_publica: str) -> tuple[bytes, str]:
    """Valida clave publica X.509 SPKI (DER base64) EC P-256.

    Devuelve (der_bytes, sha256_hex_del_spki). El hash es del SPKI exacto que
    se guarda, de modo que la verificacion de firma y el perfil coinciden.
    """
    try:
        der = base64.b64decode(clave_publica, validate=True)
    except Exception:  # noqa: BLE001 — entrada arbitraria del atacante (base64/DER)
        raise ActivacionError(
            "clave_publica no es SPKI base64 valido",
            "CLAVE_PUBLICA_INVALIDA",
            400,
        )
    if not der:
        raise ActivacionError("clave_publica vacia", "CLAVE_PUBLICA_INVALIDA", 400)
    try:
        pub = serialization.load_der_public_key(der)
    except Exception:  # noqa: BLE001 — entrada arbitraria del atacante (base64/DER)
        raise ActivacionError(
            "clave_publica no es una clave publica DER valida",
            "CLAVE_PUBLICA_INVALIDA",
            400,
        )
    if not isinstance(pub, ec.EllipticCurvePublicKey) or pub.curve.name != "secp256r1":
        raise ActivacionError(
            "clave_publica debe ser EC P-256 (secp256r1)",
            "CLAVE_PUBLICA_INVALIDA",
            400,
        )
    return der, hashlib.sha256(der).hexdigest()


def _validar_cobrador_con_ruta(db: Session, negocio_id: UUID, cobrador_id: UUID) -> Ruta:
    cobrador = db.query(Usuario).filter(Usuario.id == cobrador_id).first()
    if not cobrador or cobrador.rol != "COBRADOR" or cobrador.negocio_id != negocio_id:
        raise ActivacionError(
            "Cobrador no valido para el negocio del codigo",
            "COBRADOR_INVALIDO",
            409,
        )
    ruta = (
        db.query(Ruta)
        .filter(
            Ruta.negocio_id == negocio_id,
            Ruta.cobrador_id == cobrador_id,
            Ruta.activa == 1,
        )
        .first()
    )
    if not ruta:
        raise ActivacionError(
            "El cobrador no tiene una ruta activa asignada",
            "COBRADOR_SIN_RUTA_ACTIVA",
            409,
        )
    return ruta


def generar_codigo(
    db: Session,
    negocio_id: UUID,
    cobrador_id: UUID,
    creado_por: UUID,
    expira_minutos: int = DEFAULT_CODIGO_TTL_MINUTES,
) -> tuple[CodigoActivacion, str]:
    """Genera token de alta entropia ligado a negocio+cobrador.

    El token se devuelve UNA vez (QR/admin); el servidor guarda solo el digest.
    """
    _validar_cobrador_con_ruta(db, negocio_id, cobrador_id)

    token = secrets.token_urlsafe(32)
    codigo = CodigoActivacion(
        negocio_id=negocio_id,
        cobrador_id=cobrador_id,
        hash_codigo=_sha256_hex(token),
        prefijo=token[:8],
        expira_el=_now() + timedelta(minutes=expira_minutos),
        estado=CODIGO_PENDIENTE,
        creado_por=creado_por,
        entregado_el=_now(),
    )
    db.add(codigo)
    db.flush()
    return codigo, token


def _buscar_codigo_por_token(db: Session, token: str) -> CodigoActivacion:
    codigo = (
        db.query(CodigoActivacion)
        .filter(CodigoActivacion.hash_codigo == _sha256_hex(token))
        .first()
    )
    if not codigo:
        raise ActivacionError(
            "Token de activacion invalido",
            "CODIGO_INVALIDO",
            404,
        )
    return codigo


def desafio(
    db: Session,
    token: str,
    clave_publica: str,
    modelo: str | None = None,
    plataforma: str | None = None,
) -> DesafioResult:
    """Paso 1: crea IntentoActivacion de un solo uso. NO consume el codigo."""
    der, public_key_hash = _parse_clave_publica(clave_publica)
    codigo = _buscar_codigo_por_token(db, token)

    if codigo.estado == CODIGO_CONSUMIDO:
        raise ActivacionError(
            "Codigo ya consumido",
            "CODIGO_CONSUMIDO",
            409,
        )
    if codigo.estado == CODIGO_EXPIRADO:
        raise ActivacionError(
            "Codigo expirado",
            "CODIGO_EXPIRADO",
            409,
        )
    if codigo.estado == CODIGO_CANCELADO:
        raise ActivacionError(
            "Codigo cancelado",
            "CODIGO_CANCELADO",
            409,
        )
    if _aware_utc(codigo.expira_el) < _now():
        if codigo.estado == CODIGO_PENDIENTE:
            codigo.estado = CODIGO_EXPIRADO
            db.flush()
        raise ActivacionError(
            "Codigo expirado",
            "CODIGO_EXPIRADO",
            409,
        )

    _validar_cobrador_con_ruta(db, codigo.negocio_id, codigo.cobrador_id)

    nonce = secrets.token_urlsafe(32)
    intento = IntentoActivacion(
        codigo_id=codigo.id,
        nonce=nonce,
        clave_publica=base64.b64encode(der).decode("ascii"),
        public_key_hash=public_key_hash,
        modelo=modelo,
        plataforma=plataforma,
        expira_el=_now() + timedelta(minutes=DEFAULT_INTENTO_TTL_MINUTES),
    )
    db.add(intento)
    db.flush()
    return DesafioResult(
        intento_id=intento.id,
        nonce=nonce,
        expira_el=format_rfc3339_seconds(intento.expira_el),
        environment=get_active_environment(),
    )


def _firma_bytes(firma: str) -> bytes:
    try:
        padding = "=" * (-len(firma) % 4)
        return base64.urlsafe_b64decode(firma + padding)
    except Exception:  # noqa: BLE001 — entrada arbitraria del atacante (base64/DER)
        raise ActivacionError("firma no es base64url valido", "FIRMA_INVALIDA", 400)


def _verificar_firma(
    clave_publica: str,
    firma: bytes,
    payload: bytes,
) -> None:
    try:
        der = base64.b64decode(clave_publica, validate=True)
        pub = serialization.load_der_public_key(der)
        pub.verify(firma, payload, ec.ECDSA(hashes.SHA256()))
    except InvalidSignature:
        raise ActivacionError(
            "Firma invalida: el firmante no posee la clave privada del par presentado",
            "FIRMA_INVALIDA",
            401,
        )
    except Exception as e:  # noqa: BLE001 — entrada arbitraria del atacante (base64/DER)
        raise ActivacionError(
            f"Verificacion de firma fallo: {type(e).__name__}",
            "FIRMA_INVALIDA",
            401,
        )


def _puede_crear_dispositivo(db: Session, cobrador_id: UUID) -> None:
    existente = (
        db.query(Dispositivo)
        .filter(
            Dispositivo.usuario_id == cobrador_id,
            Dispositivo.estado == "ACTIVE",
        )
        .first()
    )
    if existente:
        raise ActivacionError(
            "El cobrador ya tiene un dispositivo ACTIVE; revoque o reemplace antes",
            "COBRADOR_YA_ACTIVO",
            409,
        )


def canjear(
    db: Session,
    intento_id: UUID,
    firma: str,
) -> CanjeResult:
    """Paso 2: verifica la firma y consume, en una transaccion con bloqueo.

    Idempotencia: si el intento ya fue consumido con exito, devuelve la misma
    credencial bootstrap dentro del plazo. Nunca crea un segundo dispositivo.
    """
    firma_bytes = _firma_bytes(firma)

    intento = _lock(
        db,
        db.query(IntentoActivacion).filter(IntentoActivacion.id == intento_id),
    ).first()
    if not intento:
        raise ActivacionError(
            "Intento de activacion invalido",
            "INTENTO_INVALIDO",
            404,
        )

    codigo = _lock(
        db,
        db.query(CodigoActivacion).filter(CodigoActivacion.id == intento.codigo_id),
    ).first()

    if intento.consumido_el is not None:
        # Ya procesado: reintento idempotente o agotado.
        # Seguridad: solo el poseedor de la clave privada del par registrado en
        # el intento puede reobtener la credencial (reintento legitimo con la
        # MISMA firma). Un segundo actor con una firma distinta (aunque conozca
        # intento_id) NO hereda por idempotencia el dispositivo/credencial del
        # primero: se rechaza y nunca se crea un segundo dispositivo.
        if (
            codigo
            and codigo.estado == CODIGO_CONSUMIDO
            and codigo.dispositivo_id_canjeado is not None
            and codigo.credencial_bootstrap
            and codigo.credencial_bootstrap_expira_el
            and _aware_utc(codigo.credencial_bootstrap_expira_el) > _now()
        ):
            payload = build_signed_payload(
                protocol_version=PROTOCOL_VERSION,
                environment=get_active_environment(),
                attempt_id=str(intento.id),
                nonce=intento.nonce,
                public_key_hash=intento.public_key_hash,
                expires_at=format_rfc3339_seconds(intento.expira_el),
            )
            _verificar_firma(intento.clave_publica, firma_bytes, payload)
            return CanjeResult(
                dispositivo_id=codigo.dispositivo_id_canjeado,
                negocio_id=codigo.negocio_id,
                cobrador_id=codigo.cobrador_id,
                credencial_bootstrap=codigo.credencial_bootstrap,
                expira_el=format_rfc3339_seconds(codigo.credencial_bootstrap_expira_el),
                idempotente=True,
            )
        raise ActivacionError(
            "Intento de activacion ya utilizado",
            "INTENTO_AGOTADO",
            409,
        )

    if _aware_utc(intento.expira_el) < _now():
        intento.consumido_el = _now()
        db.flush()
        raise ActivacionError(
            "Intento de activacion expirado",
            "INTENTO_EXPIRADO",
            410,
        )

    if codigo.estado != CODIGO_PENDIENTE:
        if codigo.estado == CODIGO_EXPIRADO:
            raise ActivacionError("Codigo expirado", "CODIGO_EXPIRADO", 409)
        raise ActivacionError(
            f"Codigo en estado {codigo.estado}",
            "CODIGO_NO_CANJEABLE",
            409,
        )
    if codigo.expira_el is not None and _aware_utc(codigo.expira_el) < _now():
        codigo.estado = CODIGO_EXPIRADO
        db.flush()
        raise ActivacionError("Codigo expirado", "CODIGO_EXPIRADO", 409)

    payload = build_signed_payload(
        protocol_version=PROTOCOL_VERSION,
        environment=get_active_environment(),
        attempt_id=str(intento.id),
        nonce=intento.nonce,
        public_key_hash=intento.public_key_hash,
        expires_at=format_rfc3339_seconds(intento.expira_el),
    )

    try:
        _verificar_firma(intento.clave_publica, firma_bytes, payload)
    except ActivacionError:
        intento.consumido_el = _now()
        codigo.intentos_fallidos = (codigo.intentos_fallidos or 0) + 1
        if codigo.intentos_fallidos >= MAX_INTENTOS_FALLIDOS:
            codigo.estado = CODIGO_EXPIRADO
        db.flush()
        raise

    _puede_crear_dispositivo(db, codigo.cobrador_id)

    dispositivo = Dispositivo(
        negocio_id=codigo.negocio_id,
        usuario_id=codigo.cobrador_id,
        huella=None,
        public_key=intento.clave_publica,
        public_key_hash=intento.public_key_hash,
        algoritmo_clave=ALGORITMO_CLAVE,
        modelo=intento.modelo,
        plataforma=intento.plataforma,
        estado="ACTIVE",
        autorizado_por=codigo.creado_por,
        autorizado_el=_now(),
        ultima_validacion_servidor=_now(),
        activo=1,
    )
    db.add(dispositivo)
    db.flush()

    bootstrap = secrets.token_urlsafe(32)
    bootstrap_expira = _now() + timedelta(minutes=DEFAULT_BOOTSTRAP_TTL_MINUTES)

    codigo.estado = CODIGO_CONSUMIDO
    codigo.consumido_el = _now()
    codigo.dispositivo_id_canjeado = dispositivo.id
    codigo.credencial_bootstrap = bootstrap
    codigo.credencial_bootstrap_expira_el = bootstrap_expira
    intento.firma_validada_el = _now()
    intento.consumido_el = _now()
    db.flush()

    return CanjeResult(
        dispositivo_id=dispositivo.id,
        negocio_id=codigo.negocio_id,
        cobrador_id=codigo.cobrador_id,
        credencial_bootstrap=bootstrap,
        expira_el=format_rfc3339_seconds(bootstrap_expira),
    )


def bootstrappear(db: Session, credencial: str) -> BootstrapResult:
    """Sustituye el bootstrap legacy por credencial (GET /api/mobile/bootstrap).

    El servidor deriva negocio/cobrador/dispositivo/ruta de la credencial de
    corta vigencia emitida en el canje. Sin parametros en la URL (aislamiento).
    """
    codigo = (
        db.query(CodigoActivacion)
        .filter(CodigoActivacion.credencial_bootstrap == credencial)
        .first()
    )
    if not codigo or codigo.estado != CODIGO_CONSUMIDO:
        raise ActivacionError(
            "Credencial bootstrap invalida",
            "BOOTSTRAP_INVALIDA",
            401,
        )
    if (
        not codigo.credencial_bootstrap_expira_el
        or _aware_utc(codigo.credencial_bootstrap_expira_el) < _now()
    ):
        raise ActivacionError(
            "Credencial bootstrap vencida",
            "BOOTSTRAP_VENCIDA",
            401,
        )

    dispositivo = (
        db.query(Dispositivo)
        .filter(Dispositivo.id == codigo.dispositivo_id_canjeado)
        .first()
    )
    if not dispositivo or dispositivo.estado != "ACTIVE":
        raise ActivacionError(
            "Credencial bootstrap invalida",
            "BOOTSTRAP_INVALIDA",
            401,
        )

    ruta = _validar_cobrador_con_ruta(db, codigo.negocio_id, codigo.cobrador_id)
    cobrador = db.query(Usuario).filter(Usuario.id == codigo.cobrador_id).first()
    negocio = db.query(Negocio).filter(Negocio.id == codigo.negocio_id).first()

    return BootstrapResult(
        negocio_id=codigo.negocio_id,
        negocio_nombre=negocio.nombre if negocio else "",
        cobrador_id=codigo.cobrador_id,
        cobrador_nombre=cobrador.nombre if cobrador else "",
        dispositivo_id=codigo.dispositivo_id_canjeado,
        ruta_id=ruta.id,
        ruta_nombre=ruta.nombre,
        rol="COBRADOR",
    )
