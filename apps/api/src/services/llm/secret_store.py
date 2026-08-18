"""W10 — SecretStore: abstracción de secretos para credenciales BYOK.

El material secreto (la API key) vive SEPARADO del dominio: la config del
provider guarda un `secret_ref` opaco; el SecretStore mapea secret_ref ->
secreto cifrado. Así un KMS/Secret Manager productivo puede sustituir el
backend cifrado sin rehacer el Provider Gateway (el secret_ref sigue siendo
opaco).

Backend W10: cifrado autenticado AES-GCM (cryptography.AESGCM) con master key
por ENV. La master key:
  - NUNCA en repo, NUNCA en DB, NUNCA en log, NUNCA en respuesta API.
  - CI: secret efímero / inyección de fixture.

Fail-closed: si la master key no está configurada, BYOK no puede escribirse
ni descifrarse (SecretStoreNotConfigured).
"""

from __future__ import annotations

import base64
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone


class SecretStoreError(Exception):
    """Error base del SecretStore."""


class SecretStoreNotConfigured(SecretStoreError):
    """La master key no está configurada (fail-closed)."""


class SecretNotFound(SecretStoreError):
    """El secret_ref no existe (o fue invalidado)."""


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class SecretRecord:
    """Registro de un secreto cifrado en el backend del SecretStore."""

    secret_ref: str
    #: nonce (12B) || ciphertext+tag (AES-GCM)
    blob: bytes
    created_el: datetime
    updated_el: datetime | None = None


class SecretStore:
    """SecretStore con backend AES-GCM y secret_ref opaco.

    El backend en memoria (dict) es la implementación W10; en producción se
    sustituye por una tabla `llm_secret` (migración) o KMS — la interfaz
    (put/get/delete/has) se mantiene.
    """

    def __init__(self, master_key: bytes | None) -> None:
        self._master_key = master_key
        self._records: dict[str, SecretRecord] = {}

    # --- construcción ---

    @classmethod
    def from_env(cls) -> "SecretStore":
        """Construye el SecretStore desde LLM_SECRET_MASTER_KEY (base64).

        Fail-closed: sin variable -> master_key None (put/get lanzan
        SecretStoreNotConfigured). Variable inválida -> SecretStoreNotConfigured.
        """
        raw = os.getenv("LLM_SECRET_MASTER_KEY")
        if not raw:
            return cls(None)
        try:
            key = base64.b64decode(raw, validate=True)
        except Exception as e:
            raise SecretStoreNotConfigured("LLM_SECRET_MASTER_KEY no es base64 válido") from e
        if len(key) not in (16, 24, 32):
            raise SecretStoreNotConfigured(
                "LLM_SECRET_MASTER_KEY debe ser 16/24/32 bytes (AES-128/192/256)"
            )
        return cls(key)

    @property
    def is_configured(self) -> bool:
        return self._master_key is not None

    # --- interior ---

    def _require_configured(self) -> None:
        if self._master_key is None:
            raise SecretStoreNotConfigured(
                "SecretStore no configurado (LLM_SECRET_MASTER_KEY ausente)"
            )

    @staticmethod
    def _new_ref() -> str:
        return f"llmsec_{uuid.uuid4().hex}"

    # --- API pública ---

    def put(self, plaintext: str, secret_ref: str | None = None) -> str:
        """Cifra y almacena un secreto. Devuelve el secret_ref opaco."""
        self._require_configured()
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        ref = secret_ref or self._new_ref()
        nonce = os.urandom(12)
        blob = AESGCM(self._master_key).encrypt(nonce, plaintext.encode("utf-8"), None)
        now = _utcnow()
        existing = self._records.get(ref)
        self._records[ref] = SecretRecord(
            secret_ref=ref,
            blob=nonce + blob,
            created_el=existing.created_el if existing else now,
            updated_el=now,
        )
        return ref

    def get(self, secret_ref: str) -> str:
        """Descifra y devuelve el secreto para un secret_ref."""
        self._require_configured()
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        record = self._records.get(secret_ref)
        if record is None:
            raise SecretNotFound(secret_ref)
        nonce, blob = record.blob[:12], record.blob[12:]
        try:
            plaintext = AESGCM(self._master_key).decrypt(nonce, blob, None)
        except Exception as e:
            # Master key equivocada o blob corrupto -> fail-closed.
            raise SecretStoreNotConfigured("secreto no descifrable (master key incorrecta?)") from e
        return plaintext.decode("utf-8")

    def delete(self, secret_ref: str) -> bool:
        """Invalida un secret_ref. Devuelve True si existía."""
        return self._records.pop(secret_ref, None) is not None

    def has(self, secret_ref: str | None) -> bool:
        """¿Existe un secreto vivo para este secret_ref?"""
        if not secret_ref:
            return False
        return secret_ref in self._records

    # --- util para tests / observabilidad ---

    def refs(self) -> list[str]:
        return list(self._records.keys())
