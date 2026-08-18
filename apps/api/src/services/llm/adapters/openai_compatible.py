"""W10 — Adapter OPENAI_COMPATIBLE_GENERIC (endpoint profiles allowlistados).

El adapter genérico OpenAI-compatible NO recibe una base_url arbitraria del
tenant (eso sería SSRF/config arbitraria). En su lugar, el tenant elige un
`endpoint_profile` (id) que el servidor resuelve a una base_url aprobada
(server-side allowlist, ver registry.ENDPOINT_PROFILES).

Capacidades conservadoras: text + streaming. tools/structured/vision se
activan solo si el profile lo declara (la mayoría de endpoints genéricos no
garantizan el contrato completo de OpenAI).
"""

from __future__ import annotations

import httpx

from src.services.llm.adapters.openai_protocol import OpenAIProtocolAdapter
from src.services.llm.types import LLMCapabilities


class OpenAICompatibleAdapter(OpenAIProtocolAdapter):
    provider = "OPENAI_COMPATIBLE_GENERIC"

    def __init__(
        self,
        base_url: str,
        api_key: str = "",
        model: str = "gpt-4o-mini",
        *,
        client: httpx.Client | None = None,
        timeout: httpx.Timeout | None = None,
        capabilities: LLMCapabilities | None = None,
    ) -> None:
        super().__init__(base_url=base_url, api_key=api_key, model=model, client=client, timeout=timeout)
        self._capabilities = capabilities or LLMCapabilities(text=True, streaming=True)

    def capabilities(self) -> LLMCapabilities:
        return self._capabilities
