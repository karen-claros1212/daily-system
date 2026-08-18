"""W10 — Adapter OPENAI_NATIVE (api.openai.com).

Protocolo OpenAI nativo. Capacidades plenas (text/tools/structured/vision/
streaming) para los modelos actuales de OpenAI.
"""

from __future__ import annotations

import httpx

from src.services.llm.adapters.openai_protocol import OpenAIProtocolAdapter
from src.services.llm.types import LLMCapabilities

NATIVE_BASE_URL = "https://api.openai.com/v1"


class OpenAINativeAdapter(OpenAIProtocolAdapter):
    provider = "OPENAI_NATIVE"

    def __init__(
        self,
        base_url: str = NATIVE_BASE_URL,
        api_key: str = "",
        model: str = "gpt-4o",
        *,
        client: httpx.Client | None = None,
        timeout: httpx.Timeout | None = None,
    ) -> None:
        super().__init__(base_url=base_url, api_key=api_key, model=model, client=client, timeout=timeout)

    def capabilities(self) -> LLMCapabilities:
        return LLMCapabilities(
            text=True,
            tools=True,
            structured_output=True,
            vision=True,
            streaming=True,
        )
