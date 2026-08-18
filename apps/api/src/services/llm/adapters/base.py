"""W10 — Base class de los adapters de proveedor.

Un adapter traduce los tipos canónicos (LLMRequest/LLMResponse) al protocolo
HTTP de su proveedor y viceversa. El core NO importa SDKs de proveedor: cada
adapter usa httpx directamente contra el contrato HTTP oficial del proveedor.

Testabilidad: el adapter acepta un `client` httpx inyectado. En CI se inyecta
un httpx.Client con MockTransport (fake server determinista) — NO se llaman
servicios reales.
"""

from __future__ import annotations

import httpx

from src.services.llm.errors import LLMProviderError
from src.services.llm.types import LLMCapabilities, LLMRequest, LLMResponse

# Timeout estricto por defecto (contrato W10 §13: timeout estricto).
DEFAULT_TIMEOUT = httpx.Timeout(15.0, connect=5.0)


class BaseAdapter:
    """Interfaz de un adapter de proveedor."""

    #: id canónico de la familia de proveedor (ver registry.py)
    provider: str = ""
    #: protocolo HTTP que implementa ("openai" | "anthropic" | "gemini")
    protocol: str = ""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        *,
        client: httpx.Client | None = None,
        timeout: httpx.Timeout | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self._timeout = timeout or DEFAULT_TIMEOUT
        if client is not None:
            self._client = client
            self._owns_client = False
        else:
            self._client = httpx.Client(base_url=self.base_url, timeout=self._timeout)
            self._owns_client = True

    # --- interfaz a implementar por cada adapter ---

    def capabilities(self) -> LLMCapabilities:
        """Capacidades REALES de este provider/model."""
        raise NotImplementedError

    def complete(self, request: LLMRequest) -> LLMResponse:
        """Petición no-streaming. Devuelve LLMResponse o lanza LLMProviderError."""
        raise NotImplementedError

    # --- helpers compartidos ---

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> "BaseAdapter":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    @staticmethod
    def _classify_http(status_code: int, *, provider: str, model: str) -> LLMProviderError | None:
        """Clasifica un status HTTP upstream en una LLMProviderError (o None si 2xx)."""
        if 200 <= status_code < 300:
            return None
        if status_code in (401, 403):
            return LLMProviderError("AUTH_ERROR", provider=provider, model=model, upstream_status=status_code)
        if status_code == 429:
            return LLMProviderError("RATE_LIMITED", provider=provider, model=model, upstream_status=status_code)
        if 500 <= status_code < 600:
            return LLMProviderError("PROVIDER_UNAVAILABLE", provider=provider, model=model, upstream_status=status_code)
        return LLMProviderError("UPSTREAM_ERROR", provider=provider, model=model, upstream_status=status_code)
