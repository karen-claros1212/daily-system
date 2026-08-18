"""W10 — Provider Gateway: enrutamiento + negociación de capacidades + observabilidad.

El gateway es la única puerta de entrada del core a los proveedores:
  1. Resuelve la credencial (TENANT_BYOK → PLATFORM_MANAGED → UNAVAILABLE).
  2. Negocia capacidades: si la operación exige una capability que el
     provider/model no soporta -> UNSUPPORTED_CAPABILITY (sin degradación
     silenciosa).
  3. Instancia el adapter correcto y ejecuta la petición.
  4. Registra metadatos técnicos de observabilidad (nunca clave/prompt/
     respuesta completa).

El gateway NO conoce el protocolo HTTP de ningún proveedor: eso lo hace el
adapter. El core llama a gateway.complete(request) y recibe un LLMResponse
canónico.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy.orm import Session

from src.services.llm import registry
from src.services.llm.adapters import BaseAdapter
from src.services.llm.credentials import resolve_credential
from src.services.llm.errors import LLMErrorClass, LLMProviderError
from src.services.llm.secret_store import SecretStore
from src.services.llm.types import LLMRequest, LLMResponse, LLMResolvedProvider

logger = logging.getLogger("daily.llm.gateway")


@dataclass
class LLMObservation:
    """Metadatos técnicos de una operación (observabilidad W10 §14).

    NUNCA contiene: API key, Authorization header, prompt completo, respuesta
    completa, PII innecesaria, tool payload sensible.
    """

    provider: str
    model: str | None
    negocio_id: UUID | None
    operation: str
    latency_ms: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    status: str = "OK"  # "OK" | error_class
    credential_source: str | None = None
    provider_request_id: str | None = None
    cost_estimate: float | None = None  # nullable; autoridad de pricing configurable


class ProviderGateway:
    """Gateway de proveedores LLM (autoridad de enrutamiento)."""

    def __init__(self, secret_store: SecretStore) -> None:
        self._secret_store = secret_store

    # --- resolución + adapter ---

    def resolve(self, db: Session, negocio_id: UUID, provider: str) -> LLMResolvedProvider:
        return resolve_credential(db, negocio_id, provider, self._secret_store)

    def _build_adapter(
        self,
        resolved: LLMResolvedProvider,
        client: httpx.Client | None = None,
    ) -> BaseAdapter:
        spec = registry.get_spec(resolved.provider)
        if spec is None or resolved.base_url is None or resolved.api_key is None:
            raise LLMProviderError(
                LLMErrorClass.INVALID_CONFIGURATION,
                f"provider {resolved.provider} no resuelto",
                provider=resolved.provider,
            )
        if spec.uses_endpoint_profile:
            profile = registry.get_endpoint_profile(resolved.endpoint_profile or "")
            caps = profile.capabilities if profile else None
            return spec.adapter_cls(
                base_url=resolved.base_url,
                api_key=resolved.api_key,
                model=resolved.model or spec.default_model,
                client=client,
                capabilities=caps,
            )
        return spec.adapter_cls(
            base_url=resolved.base_url,
            api_key=resolved.api_key,
            model=resolved.model or spec.default_model,
            client=client,
        )

    # --- negociación de capacidades (W10 §4) ---

    @staticmethod
    def _check_capabilities(request: LLMRequest, caps) -> None:
        """Si la operación exige una capability no soportada -> UNSUPPORTED_CAPABILITY.

        Seguridad nunca se degrada para conseguir una respuesta.
        """
        if request.tools and not caps.supports("tools"):
            raise LLMProviderError(
                LLMErrorClass.UNSUPPORTED_CAPABILITY,
                "el provider/model no soporta tools (function calling)",
            )
        if request.response_format is not None and not caps.supports("structured_output"):
            raise LLMProviderError(
                LLMErrorClass.UNSUPPORTED_CAPABILITY,
                "el provider/model no soporta structured output",
            )
        if any(m.parts for m in request.messages) and not caps.supports("vision"):
            raise LLMProviderError(
                LLMErrorClass.UNSUPPORTED_CAPABILITY,
                "el provider/model no soporta vision/multimodal",
            )
        if request.stream and not caps.supports("streaming"):
            raise LLMProviderError(
                LLMErrorClass.UNSUPPORTED_CAPABILITY,
                "el provider/model no soporta streaming",
            )

    # --- complete ---

    def complete(
        self,
        db: Session,
        negocio_id: UUID,
        provider: str,
        request: LLMRequest,
        *,
        operation: str = "complete",
        client: httpx.Client | None = None,
    ) -> tuple[LLMResponse, LLMObservation]:
        """Ejecuta una petición canónica contra el provider resuelto.

        Devuelve (LLMResponse, LLMObservation). Lanza LLMProviderError tipado.
        """
        resolved = self.resolve(db, negocio_id, provider)
        if not resolved.available or resolved.api_key is None:
            obs = LLMObservation(
                provider=provider,
                model=request.model,
                negocio_id=negocio_id,
                operation=operation,
                status=LLMErrorClass.PROVIDER_UNAVAILABLE,
                credential_source=resolved.credential_source,
            )
            raise LLMProviderError(
                LLMErrorClass.PROVIDER_UNAVAILABLE,
                f"sin credencial para {provider}",
                provider=provider,
            )

        adapter = self._build_adapter(resolved, client=client)
        try:
            caps = adapter.capabilities()
            self._check_capabilities(request, caps)
            response = adapter.complete(request)
        finally:
            adapter.close()

        obs = LLMObservation(
            provider=provider,
            model=response.model or request.model,
            negocio_id=negocio_id,
            operation=operation,
            latency_ms=response.latency_ms,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            total_tokens=response.usage.total_tokens,
            status="OK",
            credential_source=resolved.credential_source,
            provider_request_id=response.provider_request_id,
        )
        return response, obs

    # --- test de conexión (W10 §13) ---

    def test_connection(
        self,
        db: Session,
        negocio_id: UUID,
        provider: str,
        *,
        client: httpx.Client | None = None,
    ) -> dict[str, Any]:
        """Petición mínima, controlada y sanitizada para comprobar credenciales.

        Devuelve un dict con: status, provider, model, latency_ms,
        capabilities, credential_source. NO devuelve texto sensible.
        """
        resolved = self.resolve(db, negocio_id, provider)
        result: dict[str, Any] = {
            "provider": provider,
            "model": resolved.model,
            "credential_source": resolved.credential_source,
            "available": resolved.available,
        }
        if not resolved.available or resolved.api_key is None:
            result.update({"status": LLMErrorClass.PROVIDER_UNAVAILABLE, "latency_ms": None})
            return result
        adapter = self._build_adapter(resolved, client=client)
        try:
            caps = adapter.capabilities()
            # Petición mínima no financiera.
            from src.services.llm.types import LLMMessage

            minimal = LLMRequest(
                model=resolved.model or "",
                messages=[LLMMessage(role="user", content="ping")],
                max_output_tokens=1,
                temperature=0,
            )
            response = adapter.complete(minimal)
            result.update(
                {
                    "status": "OK",
                    "latency_ms": response.latency_ms,
                    "capabilities": {
                        "text": caps.text,
                        "tools": caps.tools,
                        "structured_output": caps.structured_output,
                        "vision": caps.vision,
                        "streaming": caps.streaming,
                    },
                }
            )
        except LLMProviderError as e:
            result.update({"status": e.error_class, "latency_ms": None})
        finally:
            adapter.close()
        return result


def get_gateway() -> ProviderGateway:
    """Factory del gateway con el SecretStore desde ENV (fail-closed)."""
    return ProviderGateway(SecretStore.from_env())
