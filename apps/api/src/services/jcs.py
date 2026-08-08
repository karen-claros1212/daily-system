"""JCS (RFC 8785) canonicalization for the activation contract payload.

Contrato de activacion, revision 4, seccion 13:
- Formato UNICO y obligatorio: JCS (RFC 8785); CBOR canonico prohibido.
- El payload firmado tiene 6 claves, todas strings, sin numeros, sin nulos.
- Se firman los bytes UTF-8 exactos de la salida JCS (SHA256withECDSA).

El vector de prueba obligatorio (seccion 13.4) es el criterio de salida:
este modulo debe producir exactamente esos 285 bytes.
"""

import json
import re
from datetime import datetime, timezone
from typing import Any

PROTOCOL_VERSION = "daily-v1"

VALID_ENVIRONMENTS = ("development", "staging", "production")

SIGNED_FIELDS = (
    "attempt_id",
    "environment",
    "expires_at",
    "nonce",
    "protocol_version",
    "public_key_hash",
)

# Representacion lexical VINCULANTE por campo firmado (seccion 13.3): los
# bytes JCS solo son validos si cada valor conforma su forma canonica.
_RE_UUID_LOWER = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)
_RE_NONCE_BASE64URL = re.compile(r"^[A-Za-z0-9_-]{43}$")
_RE_HEX_64 = re.compile(r"^[0-9a-f]{64}$")
_RE_RFC3339_SECONDS = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def validate_uuid_lowercase(value: str, field: str) -> None:
    """El campo debe ser un UUID canónico: lowercase, 8-4-4-4-12."""
    if not _RE_UUID_LOWER.fullmatch(value):
        raise ValueError(f"{field} debe ser un UUID lowercase (8-4-4-4-12)")


def validate_nonce(value: str) -> None:
    """Nonce CSPRNG: base64url sin padding de 43 caracteres (32 bytes)."""
    if not _RE_NONCE_BASE64URL.fullmatch(value):
        raise ValueError("nonce debe ser base64url sin padding de 43 caracteres (32 bytes)")


def validate_public_key_hash(value: str) -> None:
    """Hash SHA-256 del SPKI: hex lowercase de 64 caracteres."""
    if not _RE_HEX_64.fullmatch(value):
        raise ValueError("public_key_hash debe ser hex lowercase de 64 caracteres (SHA-256)")


def validate_rfc3339_seconds(value: str) -> None:
    """Timestamp de expiracion: RFC 3339 en segundos (YYYY-MM-DDTHH:MM:SSZ)."""
    if not _RE_RFC3339_SECONDS.fullmatch(value):
        raise ValueError("expires_at debe ser RFC 3339 en segundos (YYYY-MM-DDTHH:MM:SSZ)")


def _stringify(value: str) -> str:
    """JSON string literal per RFC 8785 (UTF-8 literal, no ensure_ascii).

    json.dumps(ensure_ascii=False) escapa los caracteres de control con la
    forma corta cuando existe (\\b \\t \\n \\f \\r) y \\u00XX en el resto,
    exactamente como exige RFC 8785 seccion 3.2.2.2.
    """
    return json.dumps(value, ensure_ascii=False)


def jcs_canonicalize(obj: Any) -> bytes:
    """Serialize obj to canonical JSON bytes per RFC 8785.

    Solo soporta el subconjunto que el contrato permite: dict con claves
    string, strings, ints, bools y None. Floats se rechazan (el contrato
    prohibe numeros no enteros en el payload firmado).
    """
    if isinstance(obj, dict):
        if not obj:
            return b"{}"
        # RFC 8785 seccion 3.2.3: orden por code points (comparados como
        # unidades de codigo UTF-16). Para claves ASCII es identico.
        parts = ["{"]
        for key in sorted(obj.keys(), key=lambda k: k.encode("utf-16-be")):
            parts.append(_stringify(str(key)))
            parts.append(":")
            parts.append(_stringify_value(obj[key]))
            parts.append(",")
        parts[-1] = "}"
        return "".join(parts).encode("utf-8")
    if isinstance(obj, str):
        return _stringify(obj).encode("utf-8")
    if isinstance(obj, bool):
        return b"true" if obj else b"false"
    if obj is None:
        return b"null"
    if isinstance(obj, int):
        # RFC 8785 seccion 3.3: sin ceros a la izquierda; -0 se serializa 0.
        if obj == 0:
            return b"0"
        return str(obj).encode("ascii")
    raise TypeError(
        f"Tipo no canonicalizable por el perfil del contrato: {type(obj).__name__}"
    )


def _stringify_value(value: Any) -> str:
    return jcs_canonicalize(value).decode("utf-8")


def format_rfc3339_seconds(dt: datetime) -> str:
    """Formato exacto del perfil: YYYY-MM-DDTHH:MM:SSZ (RFC 3339, segundos)."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def build_signed_payload(
    *,
    protocol_version: str,
    environment: str,
    attempt_id: str,
    nonce: str,
    public_key_hash: str,
    expires_at: str,
) -> bytes:
    """Construye los bytes JCS exactos del objeto firmado (perfil 13.3).

    Valida la representacion lexical vinculante por campo ANTES de
    serializar: un valor no conforme produce payload no valido.
    """
    if protocol_version != PROTOCOL_VERSION:
        raise ValueError("protocol_version debe ser 'daily-v1'")
    if environment not in VALID_ENVIRONMENTS:
        raise ValueError(f"environment invalido: {environment}")
    validate_uuid_lowercase(attempt_id, "attempt_id")
    validate_nonce(nonce)
    validate_public_key_hash(public_key_hash)
    validate_rfc3339_seconds(expires_at)

    obj = {
        "protocol_version": protocol_version,
        "environment": environment,
        "attempt_id": attempt_id,
        "nonce": nonce,
        "public_key_hash": public_key_hash,
        "expires_at": expires_at,
    }
    return jcs_canonicalize(obj)
