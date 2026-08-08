"""Servicio de auth productiva — renovacion de sesion (Bloque 7, D7-01).

Flujo de renovacion challenge-response (sin refresh token, sin OAuth/PKCE):
  1. El dispositivo presenta su JWT actual (Bearer) a
     POST /api/mobile/auth/renovar.
  2. El servidor valida el JWT, carga el Dispositivo y construye el payload
     JCS `daily-auth-v1` (protocolo separado del canje de activacion).
  3. El dispositivo firma los bytes exactos del payload con su clave privada
     (SHA256withECDSA) y devuelve la firma base64url.
  4. El servidor verifica la firma contra la public_key SPKI registrada en el
     canje y emite un JWT nuevo con el version_asignacion ACTUAL de la base.

Seguridad:
  - La renovacion exige prueba de posesion de la clave privada del
    dispositivo; un token robado NO permite renovar.
  - El payload fija environment, device_id, nonce, public_key_hash y
    expiracion; impide reuso entre ambientes y claves.
  - El version_asignacion del token nuevo sale de la base (no de claims
    antiguos): revocacion/reemplazo con bump mata tokens vigentes.
"""

import base64
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from sqlalchemy.orm import Session

from src.auth.token import (
    TokenExpiredError,
    TokenInvalidError,
    decode_token,
    issue_token,
)
from src.models import Dispositivo, Ruta, Usuario
from src.services.auth_jcs import build_signed_payload
from src.services.jcs import format_rfc3339_seconds

# Duracion de la renovacion: el dispositivo re-firma ~5 min antes de expirar.
RENOVACION_TTL_SECONDS = 3600
DESAFIO_MARGEN_MINUTOS = 10


class AuthError(Exception):
    """Business error for the auth flow."""

    def __init__(self, detail: str, code: str = "AUTH_ERROR", status_code: int = 400):
        self.detail = detail
        self.code = code
        self.status_code = status_code
        super().__init__(detail)


@dataclass(frozen=True)
class RenovacionResult:
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


def renovar_sesion(
    db: Session,
    token: str,
    firma: str,
    expires_at: str,
) -> RenovacionResult:
    """Renueva el JWT de sesion mediante challenge-response (daily-auth-v1).

    El token presentado debe ser valido y su firma de renovacion debe
    verificar contra la public_key registrada. El token nuevo usa el
    version_asignacion ACTUAL de la base: si hubo revocacion/reemplazo, la
    renovacion falla aunque el viejo no hubiera expirado.

    `expires_at` lo provee el cliente (es el plazo que firmo con su clave);
    el servidor valida que caiga en una ventana de frescura estricta.
    """
    try:
        claims = decode_token(token)
    except TokenExpiredError:
        raise AuthError(
            "Token expirado; no se renueva fuera de vigencia",
            "TOKEN_EXPIRADO",
            401,
        )
    except TokenInvalidError:
        raise AuthError("Token invalido", "TOKEN_INVALIDO", 401)

    dispositivo_id = UUID(claims["dispositivo_id"])
    dispositivo = _cargar_dispositivo_activo(db, dispositivo_id)
    if not dispositivo.public_key:
        raise AuthError(
            "Dispositivo sin clave publica registrada",
            "SIN_CLAVE_PUBLICA",
            401,
        )

    # version_asignacion vigente: la base manda, no el claim del token viejo.
    version_actual = dispositivo.version_asignacion or 1
    if version_actual != int(claims["version_asignacion"]):
        raise AuthError(
            "Asignacion del dispositivo cambiada; se requiere reactivacion",
            "VERSION_DESACTUALIZADA",
            401,
        )

    usuario = (
        db.query(Usuario)
        .filter(Usuario.id == UUID(claims["usuario_id"]))
        .first()
    )
    if not usuario or usuario.activo != 1:
        raise AuthError("Usuario no activo", "USUARIO_INACTIVO", 401)

    expira_dt = _parse_expira_el(expires_at)
    firma_bytes = _firma_bytes(firma)
    nonce = claims["jti"]
    payload = build_signed_payload(
        environment=_get_active_environment(),
        device_id=str(dispositivo_id),
        nonce=nonce,
        public_key_hash=dispositivo.public_key_hash,
        expires_at=expires_at,
    )
    _verificar_firma(dispositivo.public_key, firma_bytes, payload)

    token_nuevo = issue_token(
        negocio_id=dispositivo.negocio_id,
        usuario_id=usuario.id,
        dispositivo_id=dispositivo.id,
        version_asignacion=version_actual,
        ttl_seconds=RENOVACION_TTL_SECONDS,
    )
    return RenovacionResult(
        token=token_nuevo,
        negocio_id=dispositivo.negocio_id,
        usuario_id=usuario.id,
        dispositivo_id=dispositivo.id,
        version_asignacion=version_actual,
        expira_el=format_rfc3339_seconds(expira_dt),
    )


def _parse_expira_el(expires_at: str) -> datetime:
    """Valida que expires_at sea RFC 3339 y caiga en la ventana de frescura.

    La ventana es de hasta DESAFIO_MARGEN_MINUTOS en el futuro y nada en el
    pasado: un payload firmado con un plazo vencido o demasiado lejano se
    rechaza (limita replay del par {token, firma} a esa ventana).
    """
    try:
        expira_dt = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        raise AuthError("expires_at no es RFC 3339 valido", "EXPIRES_AT_INVALIDO", 400)
    if expira_dt.tzinfo is None:
        expira_dt = expira_dt.replace(tzinfo=timezone.utc)
    expira_dt = expira_dt.astimezone(timezone.utc)

    ahora = _now()
    margen_max = timedelta(minutes=DESAFIO_MARGEN_MINUTOS)
    if expira_dt <= ahora or expira_dt > ahora + margen_max:
        raise AuthError(
            "expires_at fuera de la ventana de frescura del desafio",
            "DESAFIO_VENCIDO",
            401,
        )
    return expira_dt


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
