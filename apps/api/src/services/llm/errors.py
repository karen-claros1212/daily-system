"""W10 — Errores tipados del Provider Gateway.

Errores NORMALIZADOS: el gateway convierte cualquier fallo upstream (HTTP,
timeout, JSON malformado, capability) en una de estas clases estables, de modo
que la capa API y la UI puedan reaccionar sin conocer el protocolo de cada
proveedor. El body upstream completo NUNCA se filtra al navegador.

Clases de error (contrato W10 §13):
  AUTH_ERROR              — credencial inválida/rechazada (401/403 upstream).
  RATE_LIMITED            — límite de tasa (429 upstream).
  TIMEOUT                 — el proveedor no respondió a tiempo.
  PROVIDER_UNAVAILABLE    — el proveedor está caído (5xx upstream).
  INVALID_CONFIGURATION   — la config del provider/model es inválida.
  UNSUPPORTED_CAPABILITY  — la operación exige una capability no soportada.
  UPSTREAM_ERROR          — cualquier otro error upstream no clasificado.
"""

from __future__ import annotations


class LLMErrorClass:
    """Clases de error estables (strings canónicos)."""

    AUTH_ERROR = "AUTH_ERROR"
    RATE_LIMITED = "RATE_LIMITED"
    TIMEOUT = "TIMEOUT"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    INVALID_CONFIGURATION = "INVALID_CONFIGURATION"
    UNSUPPORTED_CAPABILITY = "UNSUPPORTED_CAPABILITY"
    UPSTREAM_ERROR = "UPSTREAM_ERROR"


ALL_ERROR_CLASSES: tuple[str, ...] = (
    LLMErrorClass.AUTH_ERROR,
    LLMErrorClass.RATE_LIMITED,
    LLMErrorClass.TIMEOUT,
    LLMErrorClass.PROVIDER_UNAVAILABLE,
    LLMErrorClass.INVALID_CONFIGURATION,
    LLMErrorClass.UNSUPPORTED_CAPABILITY,
    LLMErrorClass.UPSTREAM_ERROR,
)


class LLMProviderError(Exception):
    """Error tipado emitido por el Provider Gateway.

    status_code: HTTP status que la capa API debería devolver al cliente.
      - UNSUPPORTED_CAPABILITY / INVALID_CONFIGURATION -> 422 (error del
        consumidor/config, no del proveedor).
      - AUTH_ERROR -> 401 (la credencial resuelta no es válida).
      - RATE_LIMITED -> 429.
      - TIMEOUT / PROVIDER_UNAVAILABLE / UPSTREAM_ERROR -> 502 (upstream).
    upstream_status: status HTTP que emitió el proveedor (si aplica).
    """

    def __init__(
        self,
        error_class: str,
        detail: str | None = None,
        *,
        provider: str | None = None,
        model: str | None = None,
        upstream_status: int | None = None,
        status_code: int | None = None,
    ) -> None:
        self.error_class = error_class
        self.detail = detail
        self.provider = provider
        self.model = model
        self.upstream_status = upstream_status
        self.status_code = status_code if status_code is not None else _default_status(error_class)
        super().__init__(f"[{error_class}] {detail or error_class}")

    def to_dict(self) -> dict:
        """Representación serializable (sin la clave, sin body upstream)."""
        d: dict = {"error_class": self.error_class}
        if self.detail:
            d["detail"] = self.detail
        if self.provider:
            d["provider"] = self.provider
        if self.model:
            d["model"] = self.model
        if self.upstream_status is not None:
            d["upstream_status"] = self.upstream_status
        return d


def _default_status(error_class: str) -> int:
    if error_class in (LLMErrorClass.UNSUPPORTED_CAPABILITY, LLMErrorClass.INVALID_CONFIGURATION):
        return 422
    if error_class == LLMErrorClass.AUTH_ERROR:
        return 401
    if error_class == LLMErrorClass.RATE_LIMITED:
        return 429
    # TIMEOUT / PROVIDER_UNAVAILABLE / UPSTREAM_ERROR
    return 502
