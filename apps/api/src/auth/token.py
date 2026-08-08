"""JWT productivo — auth de sesion (Bloque 7, D7-01).

Emision y validacion de tokens firmados por el servidor con PyJWT (unica
libreria JWT; D7-01). Sin OAuth, sin PKCE, sin refresh token: la renovacion
es challenge-response con la clave privada del dispositivo (daily-auth-v1).

Reglas de seguridad:
  - Allow-list FIJA de algoritmos: solo HS256. El `alg` del token NUNCA se
    lee del header; siempre se pasa `algorithms=["HS256"]` a la verificacion.
    Esto elimina alg-confusion (ning/none) y fallos de clave/header.
  - Payload minimo y sin autoridad geografica: negocio_id, usuario_id,
    dispositivo_id, version_asignacion, jti, iat, exp. NO lleva role ni
    route_id: rol y ruta se derivan de la base en CADA request (deps.py).
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

# Unica clave de algoritmo permitida. Fija en codigo: el header del token no
# influye en la seleccion.
ALLOWED_ALGORITHM = "HS256"

_DEFAULT_SECRET = "daily-system-dev-only-secret-do-not-use-in-prod"


def _secret() -> str:
    secret = os.getenv("AUTH_JWT_SECRET", "")
    return secret if secret else _DEFAULT_SECRET


def _now() -> datetime:
    return datetime.now(timezone.utc)


def issue_token(
    *,
    negocio_id: UUID,
    usuario_id: UUID,
    dispositivo_id: UUID,
    version_asignacion: int,
    ttl_seconds: int = 3600,
) -> str:
    """Emite un JWT productivo de sesion (HS256, servidor-firmado)."""
    now = _now()
    payload: dict[str, Any] = {
        "negocio_id": str(negocio_id),
        "usuario_id": str(usuario_id),
        "dispositivo_id": str(dispositivo_id),
        "version_asignacion": int(version_asignacion),
        "jti": secrets.token_urlsafe(16),
        "iat": now,
        "exp": now + timedelta(seconds=ttl_seconds),
    }
    return jwt.encode(
        payload,
        _secret(),
        algorithm=ALLOWED_ALGORITHM,
    )


class TokenError(Exception):
    """Raiz de errores de token (clase, no para uso directo)."""


class TokenInvalidError(TokenError):
    """Token malformado, firma invalida, expirado o fuera de espectro."""


class TokenExpiredError(TokenInvalidError):
    """Token expirado (se usa para renovacion explicita)."""


def decode_token(token: str) -> dict[str, Any]:
    """Valida y devuelve los claims de un token productivo.

    Solo HS256 (allow-list fija). Expira >= ahora. Verifica firma contra el
    secreto del servidor. Nunca confia en `alg` ni en la clave del header.
    """
    try:
        claims = jwt.decode(
            token,
            _secret(),
            algorithms=[ALLOWED_ALGORITHM],
            options={
                "require": ["negocio_id", "usuario_id", "dispositivo_id",
                            "version_asignacion", "jti", "exp"],
            },
        )
    except jwt.ExpiredSignatureError as e:
        raise TokenExpiredError("token expirado") from e
    except jwt.PyJWTError as e:
        raise TokenInvalidError("token invalido") from e

    return claims


def token_version(token: str) -> int:
    """Devuelve el claim version_asignacion de un token valido."""
    claims = decode_token(token)
    return int(claims["version_asignacion"])
