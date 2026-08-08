"""JWT productivo — auth de sesion (Bloque 7, D7-01/D7-H1).

Emision y validacion de tokens firmados por el servidor con PyJWT (unica
libreria JWT; D7-01). Sin OAuth, sin PKCE, sin refresh token: la renovacion
es challenge-response con la clave privada del dispositivo (daily-auth-v1).

Reglas de seguridad:
  - Algoritmo FIJO ES256 (ECDSA P-256). El `alg` del token NUNCA se lee del
    header; siempre se pasa `algorithms=["ES256"]` a la verificacion. Esto
    elimina alg-confusion (none/hs256/rs256) y fallos de clave/header.
  - Fail-closed: sin AUTH_JWT_PRIVATE_KEY no se emite ni se valida ningun
    token, en ningun ambiente. NO hay secreto por defecto ni fallback. En
    staging/production ademas se exige la clave al arrancar (main.py).
    AUTH_JWT_PUBLIC_KEY es obligatoria o derivable de la privada.
  - Claims fijos (payload productivo, sin autoridad geografica): iss, aud,
    sub (usuario_id), negocio_id, device_id, public_key_hash,
    version_asignacion, jti, iat, exp, typ="access",
    protocol_version="daily-auth-v1". NO lleva role ni route_id: rol y ruta se
    derivan de la base en CADA request (deps.py).
  - Revocacion con efecto inmediato: la validacion en cada request comprueba
    dispositivo.estado == ACTIVE y version_asignacion == claim; cualquier
    bump deja el token muerto aunque `exp` siga lejano.
  - jti aleatorio por token: impide replay directo del mismo JWT como
    credencial de renovacion.
"""

import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

# Unica clave de algoritmo permitida. Fija en codigo: el header del token no
# influye en la seleccion.
ALLOWED_ALGORITHM = "ES256"

# Identidad del emisor/audiencia del token. Constantes de despliegue: si un
# despliegue necesita diferenciar emisores, se ajustan aqui (no por env).
TOKEN_ISSUER = "daily-system-api"
TOKEN_AUDIENCE = "daily-system-mobile"

# Claims de valor fijo del payload productivo.
ACCESS_TOKEN_TYP = "access"
TOKEN_PROTOCOL_VERSION = "daily-auth-v1"

# Claims que el servidor exige presentes (presencia; `exp` ademas valida
# vigencia, e iss/aud se validan contra TOKEN_ISSUER/TOKEN_AUDIENCE).
REQUIRED_CLAIMS = (
    "iss",
    "aud",
    "sub",
    "negocio_id",
    "device_id",
    "public_key_hash",
    "version_asignacion",
    "jti",
    "iat",
    "exp",
    "typ",
    "protocol_version",
)


class TokenError(Exception):
    """Raiz de errores de token (clase, no para uso directo)."""


class TokenConfigError(TokenError):
    """Claves ES256 ausentes o invalidas: fail-closed, nunca fallback."""


class TokenInvalidError(TokenError):
    """Token malformado, firma invalida, expirado o fuera de espectro."""


class TokenExpiredError(TokenInvalidError):
    """Token expirado (se usa para renovacion explicita)."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _private_key() -> ec.EllipticCurvePrivateKey:
    """Carga y valida AUTH_JWT_PRIVATE_KEY (fail-closed).

    Lanza TokenConfigError si la variable falta o no es una clave privada
    EC P-256 (secp256r1). No existe secreto por defecto.
    """
    pem = os.getenv("AUTH_JWT_PRIVATE_KEY", "").strip()
    if not pem:
        raise TokenConfigError(
            "AUTH_JWT_PRIVATE_KEY requerida para emitir/validar JWT ES256 "
            "(fail-closed: no hay secreto por defecto)"
        )
    try:
        key = serialization.load_pem_private_key(pem.encode("utf-8"), password=None)
    except Exception as e:  # noqa: BLE001 — entrada de config, no del atacante
        raise TokenConfigError("AUTH_JWT_PRIVATE_KEY no es una clave PEM valida") from e
    if not isinstance(key, ec.EllipticCurvePrivateKey) or key.curve.name != "secp256r1":
        raise TokenConfigError("AUTH_JWT_PRIVATE_KEY debe ser EC P-256 (secp256r1)")
    return key


def _public_key() -> ec.EllipticCurvePublicKey:
    """Clave publica ES256: AUTH_JWT_PUBLIC_KEY, o derivada de la privada."""
    pem = os.getenv("AUTH_JWT_PUBLIC_KEY", "").strip()
    if pem:
        try:
            key = serialization.load_pem_public_key(pem.encode("utf-8"))
        except Exception as e:  # noqa: BLE001 — entrada de config, no del atacante
            raise TokenConfigError("AUTH_JWT_PUBLIC_KEY no es una clave publica PEM valida") from e
        if not isinstance(key, ec.EllipticCurvePublicKey) or key.curve.name != "secp256r1":
            raise TokenConfigError("AUTH_JWT_PUBLIC_KEY debe ser EC P-256 (secp256r1)")
        return key
    return _private_key().public_key()


def _private_key_pem() -> bytes:
    return _private_key().private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )


def _public_key_pem() -> bytes:
    return _public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )


def ensure_es256_configured() -> None:
    """Gate de arranque: falla si faltan las claves ES256 (staging/production)."""
    _private_key_pem()


def issue_token(
    *,
    negocio_id: UUID,
    usuario_id: UUID,
    dispositivo_id: UUID,
    public_key_hash: str,
    version_asignacion: int,
    ttl_seconds: int = 3600,
) -> str:
    """Emite un JWT productivo de sesion (ES256, servidor-firmado)."""
    if not public_key_hash:
        raise TokenConfigError("public_key_hash es obligatorio en el JWT")
    now = _now()
    payload: dict[str, Any] = {
        "iss": TOKEN_ISSUER,
        "aud": TOKEN_AUDIENCE,
        "sub": str(usuario_id),
        "negocio_id": str(negocio_id),
        "device_id": str(dispositivo_id),
        "public_key_hash": public_key_hash,
        "version_asignacion": int(version_asignacion),
        "jti": secrets.token_urlsafe(16),
        "iat": now,
        "exp": now + timedelta(seconds=ttl_seconds),
        "typ": ACCESS_TOKEN_TYP,
        "protocol_version": TOKEN_PROTOCOL_VERSION,
    }
    return jwt.encode(
        payload,
        _private_key_pem(),
        algorithm=ALLOWED_ALGORITHM,
    )


def decode_token(token: str) -> dict[str, Any]:
    """Valida y devuelve los claims de un token productivo.

    Solo ES256 (allow-list fija). Expira >= ahora. Verifica la firma contra la
    clave publica del servidor (AUTH_JWT_PUBLIC_KEY o derivada de la privada).
    Nunca confia en `alg` ni en la clave del header. Fail-closed: sin claves
    configuradas lanza TokenConfigError.
    """
    try:
        claims = jwt.decode(
            token,
            _public_key_pem(),
            algorithms=[ALLOWED_ALGORITHM],
            issuer=TOKEN_ISSUER,
            audience=TOKEN_AUDIENCE,
            options={
                "require": list(REQUIRED_CLAIMS),
            },
        )
    except jwt.ExpiredSignatureError as e:
        raise TokenExpiredError("token expirado") from e
    except jwt.PyJWTError as e:
        raise TokenInvalidError("token invalido") from e

    # Valor de claims fijos: presencia la exige `require`; el valor se valida
    # aqui (PyJWT no puede exigir igualdad de claims arbitrarios).
    if claims.get("typ") != ACCESS_TOKEN_TYP:
        raise TokenInvalidError("typ del token no es 'access'")
    if claims.get("protocol_version") != TOKEN_PROTOCOL_VERSION:
        raise TokenInvalidError("protocol_version del token no es daily-auth-v1")

    return claims


def token_version(token: str) -> int:
    """Devuelve el claim version_asignacion de un token valido."""
    claims = decode_token(token)
    return int(claims["version_asignacion"])
