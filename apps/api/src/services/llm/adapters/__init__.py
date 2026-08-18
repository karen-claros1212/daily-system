"""W10 — Adapters de proveedor (uno por familia MUST).

Los 6 adapters MUST del contrato W10:
  - OPENAI_NATIVE            -> OpenAINativeAdapter
  - MISTRAL_NATIVE           -> MistralNativeAdapter
  - CEREBRAS_OPENAI_COMPATIBLE -> CerebrasOpenAIAdapter
  - ANTHROPIC_NATIVE         -> AnthropicNativeAdapter
  - GEMINI_NATIVE            -> GeminiNativeAdapter
  - OPENAI_COMPATIBLE_GENERIC -> OpenAICompatibleAdapter (endpoint profiles)

El core NO importa SDKs de proveedor — solo httpx + stdlib.
"""

from src.services.llm.adapters.anthropic_native import AnthropicNativeAdapter
from src.services.llm.adapters.base import BaseAdapter
from src.services.llm.adapters.cerebras_openai import CerebrasOpenAIAdapter
from src.services.llm.adapters.gemini_native import GeminiNativeAdapter
from src.services.llm.adapters.mistral_native import MistralNativeAdapter
from src.services.llm.adapters.openai_compatible import OpenAICompatibleAdapter
from src.services.llm.adapters.openai_native import OpenAINativeAdapter
from src.services.llm.adapters.openai_protocol import OpenAIProtocolAdapter

__all__ = [
    "BaseAdapter",
    "OpenAIProtocolAdapter",
    "OpenAINativeAdapter",
    "MistralNativeAdapter",
    "CerebrasOpenAIAdapter",
    "AnthropicNativeAdapter",
    "GeminiNativeAdapter",
    "OpenAICompatibleAdapter",
]
