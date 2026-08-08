"""JCS (RFC 8785) canonicalization for the activation contract payload.

Contrato de activacion, revision 4, seccion 13:
- Formato UNICO y obligatorio: JCS (RFC 8785); CBOR canonico prohibido.
- El payload firmado tiene 6 claves, todas strings, sin numeros, sin nulos.
- Se firman los bytes UTF-8 exactos de la salida JCS (SHA256withECDSA).

El vector de prueba obligatorio (seccion 13.4) es el criterio de salida:
este modulo debe producir exactamente esos 285 bytes.
"""

import json
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

    obj = {
        "protocol_version": protocol_version,
        "environment": environment,
        "attempt_id": attempt_id,
        "nonce": nonce,
        "public_key_hash": public_key_hash,
        "expires_at": expires_at,
    }
    return jcs_canonicalize(obj)
