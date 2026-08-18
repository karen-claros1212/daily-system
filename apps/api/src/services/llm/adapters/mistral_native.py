"""W10 — Adapter MISTRAL_NATIVE (api.mistral.ai).

Mistral expone una API OpenAI-compatible. Se trata como familia propia (no se
reduce a "OpenAI-compatible + Anthropic"): base_url nativo de Mistral y
capacidades declaradas según lo que Mistral soporta realmente (text/tools/
structured/vision/streaming).

Contrato HTTP verificado contra la documentación oficial de Mistral
(api.mistral.ai — /v1/chat/completions, OpenAI-compatible).
"""

from __future__ import annotations

import httpx

from src.services.llm.adapters.openai_protocol import OpenAIProtocolAdapter
from src.services.llm.types import LLMCapabilities

NATIVE_BASE_URL = "https://api.mistral.ai/v1"


class MistralNativeAdapter(OpenAIProtocolAdapter):
    provider = "MISTRAL_NATIVE"

    def __init__(
        self,
        base_url: str = NATIVE_BASE_URL,
        api_key: str = "",
        model: str = "mistral-large-latest",
        *,
        client: httpx.Client | None = None,
        timeout: httpx.Timeout | None = None,
    ) -> None:
        super().__init__(base_url=base_url, api_key=api_key, model=model, client=client, timeout=timeout)

    def capabilities(self) -> LLMCapabilities:
        # Mistral soporta tools (function calling), streaming y vision en
        # varios modelos; structured output (json mode) disponible.
        return LLMCapabilities(
            text=True,
            tools=True,
            structured_output=True,
            vision=True,
            streaming=True,
        )
