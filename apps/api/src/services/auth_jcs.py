"""Perfil JCS daily-auth-v1 — renovacion de sesion (Bloque 7, D7-01).

Perfil de serializacion SEPARADO del protocolo de activacion (daily-v1):
  - daily-v1      : canje de activacion (src/services/jcs.py)
  - daily-auth-v1 : renovacion challenge-response del token productivo

Reutiliza la canonizacion JCS (RFC 8785) byte a byte de src.services.jcs
(la misma funcion canonica, un perfil de campos distinto). El payload firmado
tiene claves string, sin numeros, sin nulos; el dispositivo lo firma con su
clave privada (SHA256withECDSA) y el servidor lo verifica contra la public_key
SPKI registrada en el canje.
"""

from datetime import datetime, timedelta, timezone

from src.services.jcs import (
    VALID_ENVIRONMENTS,
    format_rfc3339_seconds,
    jcs_canonicalize,
)

PROTOCOL_VERSION = "daily-auth-v1"

SIGNED_FIELDS = (
    "protocol_version",
    "environment",
    "device_id",
    "nonce",
    "public_key_hash",
    "expires_at",
)


def build_signed_payload(
    *,
    environment: str,
    device_id: str,
    nonce: str,
    public_key_hash: str,
    expires_at: str,
) -> bytes:
    """Construye los bytes JCS exactos del objeto firmado (daily-auth-v1).

    Valida la representacion lexical vinculante por campo ANTES de
    serializar: un valor no conforme produce payload no valido.
    """
    if environment not in VALID_ENVIRONMENTS:
        raise ValueError(f"environment invalido: {environment}")

    obj = {
        "protocol_version": PROTOCOL_VERSION,
        "environment": environment,
        "device_id": device_id,
        "nonce": nonce,
        "public_key_hash": public_key_hash,
        "expires_at": expires_at,
    }
    return jcs_canonicalize(obj)


def rfc3339_now_plus(seconds: int) -> str:
    """Timestamp de expiracion del desafio (RFC 3339, segundos, UTC)."""
    dt = datetime.now(timezone.utc) + timedelta(seconds=seconds)
    return format_rfc3339_seconds(dt)
