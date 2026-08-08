"""Servicio de auth productiva — desafio/canje de sesion (Bloque 7, D7-01/02).

Flujo de renovacion challenge-response (sin refresh token, sin OAuth/PKCE):
  1. POST /api/auth/device/desafio con Bearer <JWT vigente> (o la credencial
     bootstrap emitida en la activacion, para el PRIMER JWT post-activacion).
     El servidor autentica el dispositivo y crea un DesafioAuth de un solo
     uso (challenge_id, nonce CSPRNG, public_key_hash, expira_el).
  2. El dispositivo firma los bytes exactos del payload JCS `daily-auth-v1`
     con su clave privada (SHA256withECDSA) y devuelve la firma base64url.
  3. POST /api/auth/device/canjear: verifica la firma contra la public_key
     SPKI registrada en el canje, revalida dispositivo/usuario/asignacion
     desde la base, marca consumido_el y emite un JWT ES256 nuevo.

Un solo mecanismo emite el primer JWT post-activacion y todos los posteriores
(una sola arquitectura de sesion; el canje de activacion solo emite la
credencial bootstrap, que autentica el primer desafio).

Seguridad:
  - La renovacion exige prueba de posesion de la clave privada del
    dispositivo; un token robado NO permite renovar.
  - Single-use: el challenge_id se consume en el canje; el replay del mismo
    challenge_id devuelve 409 (decision explicita del proyecto).
  - El servidor controla la expiracion del desafio (no el cliente): expira_el
    se guarda y se firma tal cual lo emitio el servidor.
  - El version_asignacion del token nuevo sale de la base (no de claims
    antiguos): revocacion/reemplazo con bump mata tokens vigentes.
"""

import base64
import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from sqlalchemy.orm import Session

from src.auth.token import (
    TokenError,
    decode_token,
    issue_token,
)
from src.models import CodigoActivacion, DesafioAuth, Dispositivo, Ruta, Usuario
from src.services.auth_jcs import (
    PURPOSE_ISSUE_ACCESS_TOKEN,
    build_signed_payload,
)
from src.services.jcs import format_rfc3339_seconds

# Duracion de la sesion: el dispositivo re-desafia ~5 min antes de expirar.
SESION_TTL_SECONDS = 3600
# Vigencia del desafio: el dispositivo debe firmar dentro de esta ventana.
DESAFIO_TTL_MINUTOS = 5

CODIGO_CONSUMIDO = "CONSUMED"


class AuthError(Exception):
    """Business error for the auth flow."""

    def __init__(self, detail: str, code: str = "AUTH_ERROR", status_code: int = 400):
        self.detail = detail
        self.code = code
        self.status_code = status_code
        super().__init__(detail)


@dataclass(frozen=True)
class DesafioAuthResult:
    challenge_id: UUID
    nonce: str
    expira_el: str
    environment: str


@dataclass(frozen=True)
class CanjeDesafioResult:
    token: str
    negocio_id: UUID
    usuario_id: UUID
    dispositivo_id: UUID
    version_asignacion: int
    expira_el: str


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _get_active_environment() -> str:
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


def _firma_bytes(firma: str) -> bytes:
    try:
        padding = "=" * (-len(firma) % 4)
        return base64.urlsafe_b64decode(firma + padding)
    except Exception:  # noqa: BLE001 — entrada arbitraria del atacante (base64/DER)
        raise AuthError("firma no es base64url valido", "FIRMA_INVALIDA", 400)


def _verificar_firma(clave_publica: str, firma: bytes, payload: bytes) -> None:
    try:
        der = base64.b64decode(clave_publica, validate=True)
        pub = serialization.load_der_public_key(der)
        pub.verify(firma, payload, ec.ECDSA(hashes.SHA256()))
    except InvalidSignature:
        raise AuthError(
            "Firma invalida: el dispositivo no posee la clave privada del par registrado",
            "FIRMA_INVALIDA",
            401,
        )
    except Exception as e:  # noqa: BLE001 — entrada arbitraria del atacante (base64/DER)
        raise AuthError(
            f"Verificacion de firma fallo: {type(e).__name__}",
            "FIRMA_INVALIDA",
            401,
        )


def _cargar_dispositivo_activo(db: Session, dispositivo_id: UUID) -> Dispositivo:
    dispositivo = (
        db.query(Dispositivo)
        .filter(Dispositivo.id == dispositivo_id)
        .first()
    )
    if not dispositivo or dispositivo.estado != "ACTIVE":
        raise AuthError(
            "Dispositivo no activo",
            "DISPOSITIVO_NO_ACTIVO",
            401,
        )
    return dispositivo


def validar_dispositivo_claims(
    db: Session,
    claims: dict,
) -> Dispositivo:
    """Valida el dispositivo contra los claims del JWT (binding completo, H3).

    Carga el dispositivo del claim `device_id` y exige:
      - estado == ACTIVE
      - version_asignacion == claim (revocacion/reemplazo con bump)
      - usuario_id == claims["sub"]
      - negocio_id == claims["negocio_id"]
      - public_key_hash == claims["public_key_hash"]
    Cualquier mismatch -> AuthError 401. Es el helper comun usado por el
    RequestContext (deps.py) y por el flujo de desafio/canje (auth_service):
    la misma regla congelada aplica a ambas rutas de autenticacion.
    """
    dispositivo_id = UUID(claims["device_id"])
    dispositivo = (
        db.query(Dispositivo)
        .filter(Dispositivo.id == dispositivo_id)
        .first()
    )
    if not dispositivo or dispositivo.estado != "ACTIVE":
        raise AuthError(
            "Dispositivo no activo",
            "DISPOSITIVO_NO_ACTIVO",
            401,
        )
    if (dispositivo.version_asignacion or 1) != int(claims["version_asignacion"]):
        raise AuthError(
            "Asignacion del dispositivo cambiada; se requiere reactivacion",
            "VERSION_DESACTUALIZADA",
            401,
        )
    if dispositivo.negocio_id != UUID(claims["negocio_id"]):
        raise AuthError(
            "Negocio del token no coincide",
            "NEGOCIO_TOKEN_NO_COINCIDE",
            401,
        )
    if dispositivo.usuario_id != UUID(claims["sub"]):
        raise AuthError(
            "El dispositivo no pertenece al usuario del token",
            "USUARIO_TOKEN_NO_COINCIDE",
            401,
        )
    if (
        not dispositivo.public_key_hash
        or dispositivo.public_key_hash != claims["public_key_hash"]
    ):
        raise AuthError(
            "La clave del dispositivo no coincide con el token",
            "CLAVE_TOKEN_NO_COINCIDE",
            401,
        )
    return dispositivo


def _dispositivo_desde_jwt(db: Session, credencial: str) -> Dispositivo | None:
    """Resuelve el dispositivo a partir de un JWT de sesion vigente.

    Binding completo (H3): no basta la firma valida; el dispositivo debe ser
    ACTIVE, con la version vigente y pertenecer al usuario/negocio/clave del
    token. Un JWT firmado con binding incorrecto NO cae al bootstrap: AuthError
    401 directo.
    """
    try:
        claims = decode_token(credencial)
    except TokenError:
        return None
    return validar_dispositivo_claims(db, claims)


def _dispositivo_desde_bootstrap(db: Session, credencial: str) -> Dispositivo | None:
    """Resuelve el dispositivo a partir de la credencial bootstrap del canje.

    Permite el PRIMER desafio post-activacion: la credencial de corta vigencia
    emitida en el canje autentica el dispositivo hasta obtener su primer JWT.
    """
    codigo = (
        db.query(CodigoActivacion)
        .filter(CodigoActivacion.credencial_bootstrap == credencial)
        .first()
    )
    if (
        not codigo
        or codigo.estado != CODIGO_CONSUMIDO
        or not codigo.dispositivo_id_canjeado
        or not codigo.credencial_bootstrap_expira_el
        or _aware_utc(codigo.credencial_bootstrap_expira_el) < _now()
    ):
        return None
    return _cargar_dispositivo_activo(db, codigo.dispositivo_id_canjeado)


def _resolver_dispositivo(db: Session, credencial: str) -> Dispositivo:
    """Autentica el dispositivo por JWT vigente o credencial bootstrap."""
    dispositivo = _dispositivo_desde_jwt(db, credencial)
    if dispositivo is None:
        dispositivo = _dispositivo_desde_bootstrap(db, credencial)
    if dispositivo is None:
        raise AuthError(
            "Credencial de sesion invalida",
            "CREDENCIAL_INVALIDA",
            401,
        )
    return dispositivo


def solicitar_desafio(db: Session, credencial: str) -> DesafioAuthResult:
    """Paso 1: crea un DesafioAuth de un solo uso. No consume nada."""
    dispositivo = _resolver_dispositivo(db, credencial)
    if not dispositivo.public_key or not dispositivo.public_key_hash:
        raise AuthError(
            "Dispositivo sin clave publica registrada",
            "SIN_CLAVE_PUBLICA",
            401,
        )

    nonce = secrets.token_urlsafe(32)
    desafio = DesafioAuth(
        dispositivo_id=dispositivo.id,
        nonce=nonce,
        public_key_hash=dispositivo.public_key_hash,
        expira_el=_now() + timedelta(minutes=DESAFIO_TTL_MINUTOS),
    )
    db.add(desafio)
    db.flush()
    return DesafioAuthResult(
        challenge_id=desafio.id,
        nonce=nonce,
        expira_el=format_rfc3339_seconds(desafio.expira_el),
        environment=_get_active_environment(),
    )


def canjear_desafio(
    db: Session,
    challenge_id: UUID,
    firma: str,
) -> CanjeDesafioResult:
    """Paso 2: verifica la firma y consume el desafio, con bloqueo de fila.

    Single-use: un challenge ya consumido (replay del mismo challenge_id)
    devuelve 409. La firma se verifica contra la public_key registrada del
    dispositivo; el token nuevo usa el version_asignacion ACTUAL de la base:
    si hubo revocacion/reemplazo, el canje falla aunque el viejo no hubiera
    expirado.
    """
    firma_bytes = _firma_bytes(firma)

    desafio = _lock(
        db,
        db.query(DesafioAuth).filter(DesafioAuth.id == challenge_id),
    ).first()
    if not desafio:
        raise AuthError(
            "Desafio de sesion invalido",
            "CHALLENGE_INVALIDO",
            404,
        )
    if desafio.consumido_el is not None:
        raise AuthError(
            "Desafio de sesion ya utilizado (replay)",
            "CHALLENGE_YA_USADO",
            409,
        )
    if _aware_utc(desafio.expira_el) < _now():
        desafio.consumido_el = _now()
        db.flush()
        # La marca de consumo DEBE persistir aunque la request falle (410):
        # get_db_transaction() hace rollback ante cualquier excepcion y la
        # descartaria en produccion (el test SQLite lo enmascara al sustituir
        # la dependencia transaccional). Commit explicito de la penalizacion.
        db.commit()
        raise AuthError(
            "Desafio de sesion vencido",
            "CHALLENGE_VENCIDO",
            410,
        )

    dispositivo = _cargar_dispositivo_activo(db, desafio.dispositivo_id)
    if not dispositivo.public_key:
        raise AuthError(
            "Dispositivo sin clave publica registrada",
            "SIN_CLAVE_PUBLICA",
            401,
        )
    if (
        not dispositivo.public_key_hash
        or dispositivo.public_key_hash != desafio.public_key_hash
    ):
        raise AuthError(
            "La clave registrada no coincide con el desafio",
            "FIRMA_INVALIDA",
            401,
        )

    payload = build_signed_payload(
        purpose=PURPOSE_ISSUE_ACCESS_TOKEN,
        environment=_get_active_environment(),
        challenge_id=str(desafio.id),
        device_id=str(dispositivo.id),
        nonce=desafio.nonce,
        public_key_hash=desafio.public_key_hash,
        expires_at=format_rfc3339_seconds(desafio.expira_el),
    )
    _verificar_firma(dispositivo.public_key, firma_bytes, payload)

    # version_asignacion vigente: la base manda, no el claim del token viejo.
    version_actual = dispositivo.version_asignacion or 1

    usuario = (
        db.query(Usuario)
        .filter(Usuario.id == dispositivo.usuario_id)
        .first()
    )
    if not usuario or usuario.activo != 1:
        raise AuthError("Usuario no activo", "USUARIO_INACTIVO", 401)
    if usuario.negocio_id != dispositivo.negocio_id:
        raise AuthError(
            "El usuario del dispositivo pertenece a otro negocio",
            "USUARIO_DE_OTRO_NEGOCIO",
            401,
        )
    if usuario.rol != "COBRADOR":
        raise AuthError(
            "Los access tokens solo se emiten para cobradores",
            "ROL_NO_PERMITIDO",
            401,
        )

    # H3: antes de emitir el access token, la asignacion actual del cobrador
    # debe ser exactamente UNA ruta activa del mismo negocio. La ruta se deriva
    # de la base (nunca del cliente ni del JWT); un cobrador sin ruta o con mas
    # de una no puede renovar sesion.
    exigir_ruta_activa_unica(db, usuario.id, usuario.negocio_id)

    token_nuevo = issue_token(
        negocio_id=dispositivo.negocio_id,
        usuario_id=usuario.id,
        dispositivo_id=dispositivo.id,
        public_key_hash=desafio.public_key_hash,
        version_asignacion=version_actual,
        ttl_seconds=SESION_TTL_SECONDS,
    )
    desafio.consumido_el = _now()
    db.flush()

    return CanjeDesafioResult(
        token=token_nuevo,
        negocio_id=dispositivo.negocio_id,
        usuario_id=usuario.id,
        dispositivo_id=dispositivo.id,
        version_asignacion=version_actual,
        expira_el=format_rfc3339_seconds(_now() + timedelta(seconds=SESION_TTL_SECONDS)),
    )


def rutas_activas_cobrador(db: Session, usuario_id: UUID) -> list[Ruta]:
    """Rutas ACTIVAS del cobrador (derivadas de la base, no del cliente/JWT)."""
    return (
        db.query(Ruta)
        .filter(
            Ruta.cobrador_id == usuario_id,
            Ruta.activa == 1,
        )
        .all()
    )


def exigir_ruta_activa_unica(
    db: Session,
    usuario_id: UUID,
    negocio_id: UUID,
) -> Ruta:
    """Exige exactamente UNA ruta activa del cobrador en el negocio (H3).

    La regla congelada del binding: un cobrador sin ruta activa o con mas de
    una NO obtiene sesion ni contexto (0 -> 401, >1 -> 401). La ruta se deriva
    del negocio del usuario, nunca de claims ni del cliente.
    """
    rutas = [
        r
        for r in rutas_activas_cobrador(db, usuario_id)
        if r.negocio_id == negocio_id
    ]
    if not rutas:
        raise AuthError(
            "El cobrador no tiene una ruta activa asignada",
            "SIN_RUTA_ACTIVA",
            401,
        )
    if len(rutas) > 1:
        raise AuthError(
            "El cobrador tiene mas de una ruta activa; revise la asignacion",
            "MULTIPLES_RUTAS_ACTIVAS",
            401,
        )
    return rutas[0]


def derivar_ruta_activa(db: Session, usuario_id: UUID) -> Ruta | None:
    """Ruta activa del cobrador (servidor deriva; nunca del cliente/JWT)."""
    return (
        db.query(Ruta)
        .filter(
            Ruta.cobrador_id == usuario_id,
            Ruta.activa == 1,
        )
        .first()
    )
