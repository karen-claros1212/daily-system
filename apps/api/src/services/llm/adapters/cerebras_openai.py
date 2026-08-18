"""W10 — Adapter CEREBRAS_OPENAI_COMPATIBLE (api.cerebras.ai).

Cerebras expone una API OpenAI-compatible. Familia propia del contrato W10.

Contrato HTTP verificado contra la documentación oficial de Cerebras
(api.cerebras.ai — /v1/chat/completions, OpenAI-compatible).
"""

from __future__ import annotations

import httpx

from src.services.llm.adapters.openai_protocol import OpenAIProtocolAdapter
from src.services.llm.types import LLMCapabilities

NATIVE_BASE_URL = "https://api.cerebras.ai/v1"


class CerebrasOpenAIAdapter(OpenAIProtocolAdapter):
    provider = "CEREBRAS_OPENAI_COMPATIBLE"

    def __init__(
        self,
        base_url: str = NATIVE_BASE_URL,
        api_key: str = "",
        model: str = "llama3.1-70b",
        *,
        client: httpx.Client | None = None,
        timeout: httpx.Timeout | None = None,
    ) -> None:
        super().__init__(base_url=base_url, api_key=api_key, model=model, client=client, timeout=timeout)

    def capabilities(self) -> LLMCapabilities:
        # Cerebras soporta text + streaming; tools/structured/vision dependen
        # del modelo (se conservan conservadores: text + streaming).
        return LLMCapabilities(
            text=True,
            tools=False,
            structured_output=False,
            vision=False,
            streaming=True,
        )
