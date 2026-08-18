"""W10 — Registro de proveedores (6 familias MUST) + endpoint profiles.

El registry mapea cada familia de proveedor a:
  - su clase de adapter,
  - su base_url nativa (para providers nativos),
  - su protocolo,
  - un modelo por defecto,
  - sus capacidades (declaradas por el adapter).

Para OPENAI_COMPATIBLE_GENERIC el base_url NO viene del tenant (SSRF): el
tenant elige un `endpoint_profile` (id) que el servidor resuelve a una
base_url aprobada (allowlist server-side). En producción esta allowlist puede
venir de env/SecretStore; aquí es el set canónico.

Regla W10 §8: NO permitir base_url arbitraria enviada por tenant.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.services.llm.adapters import (
    AnthropicNativeAdapter,
    BaseAdapter,
    CerebrasOpenAIAdapter,
    GeminiNativeAdapter,
    MistralNativeAdapter,
    OpenAICompatibleAdapter,
    OpenAINativeAdapter,
)
from src.services.llm.types import LLMCapabilities


# --- ids canónicos de familia de proveedor (estables) ---
OPENAI_NATIVE = "OPENAI_NATIVE"
MISTRAL_NATIVE = "MISTRAL_NATIVE"
CEREBRAS_OPENAI_COMPATIBLE = "CEREBRAS_OPENAI_COMPATIBLE"
ANTHROPIC_NATIVE = "ANTHROPIC_NATIVE"
GEMINI_NATIVE = "GEMINI_NATIVE"
OPENAI_COMPATIBLE_GENERIC = "OPENAI_COMPATIBLE_GENERIC"

ALL_PROVIDERS: tuple[str, ...] = (
    OPENAI_NATIVE,
    MISTRAL_NATIVE,
    CEREBRAS_OPENAI_COMPATIBLE,
    ANTHROPIC_NATIVE,
    GEMINI_NATIVE,
    OPENAI_COMPATIBLE_GENERIC,
)

# --- protocolos ---
PROTOCOL_OPENAI = "openai"
PROTOCOL_ANTHROPIC = "anthropic"
PROTOCOL_GEMINI = "gemini"


@dataclass(frozen=True)
class EndpointProfile:
    """Endpoint profile allowlistado para OPENAI_COMPATIBLE_GENERIC.

    El tenant envía profile_id; el servidor lo resuelve a base_url aprobada.
    Esto evita SSRF / configuración arbitraria de base_url.
    """

    profile_id: str
    base_url: str
    label: str
    protocol: str = PROTOCOL_OPENAI
    capabilities: LLMCapabilities = field(
        default_factory=lambda: LLMCapabilities(text=True, streaming=True)
    )


# Allowlist de endpoint profiles (server-side). En producción, configurable
# por env/SecretStore. El tenant NUNCA escribe la URL: elige un profile_id.
ENDPOINT_PROFILES: dict[str, EndpointProfile] = {
    "openrouter": EndpointProfile(
        profile_id="openrouter",
        base_url="https://openrouter.ai/api/v1",
        label="OpenRouter",
        capabilities=LLMCapabilities(text=True, tools=True, structured_output=True, vision=True, streaming=True),
    ),
    "groq": EndpointProfile(
        profile_id="groq",
        base_url="https://api.groq.com/openai/v1",
        label="Groq",
        capabilities=LLMCapabilities(text=True, tools=True, structured_output=True, streaming=True),
    ),
    "together": EndpointProfile(
        profile_id="together",
        base_url="https://api.together.xyz/v1",
        label="Together AI",
        capabilities=LLMCapabilities(text=True, tools=True, structured_output=True, streaming=True),
    ),
    "local-ollama": EndpointProfile(
        profile_id="local-ollama",
        base_url="http://ollama.internal:11434/v1",
        label="Ollama (local)",
        capabilities=LLMCapabilities(text=True, tools=True, streaming=True),
    ),
    "local-vllm": EndpointProfile(
        profile_id="local-vllm",
        base_url="http://vllm.internal:8000/v1",
        label="vLLM (local)",
        capabilities=LLMCapabilities(text=True, tools=True, structured_output=True, streaming=True),
    ),
}


@dataclass(frozen=True)
class ProviderSpec:
    """Especificación de una familia de proveedor."""

    provider: str
    adapter_cls: type[BaseAdapter]
    protocol: str
    native_base_url: str | None
    default_model: str
    #: True si el provider usa endpoint profiles (OPENAI_COMPATIBLE_GENERIC)
    uses_endpoint_profile: bool = False


PROVIDER_SPECS: dict[str, ProviderSpec] = {
    OPENAI_NATIVE: ProviderSpec(
        provider=OPENAI_NATIVE,
        adapter_cls=OpenAINativeAdapter,
        protocol=PROTOCOL_OPENAI,
        native_base_url="https://api.openai.com/v1",
        default_model="gpt-4o",
    ),
    MISTRAL_NATIVE: ProviderSpec(
        provider=MISTRAL_NATIVE,
        adapter_cls=MistralNativeAdapter,
        protocol=PROTOCOL_OPENAI,
        native_base_url="https://api.mistral.ai/v1",
        default_model="mistral-large-latest",
    ),
    CEREBRAS_OPENAI_COMPATIBLE: ProviderSpec(
        provider=CEREBRAS_OPENAI_COMPATIBLE,
        adapter_cls=CerebrasOpenAIAdapter,
        protocol=PROTOCOL_OPENAI,
        native_base_url="https://api.cerebras.ai/v1",
        default_model="llama3.1-70b",
    ),
    ANTHROPIC_NATIVE: ProviderSpec(
        provider=ANTHROPIC_NATIVE,
        adapter_cls=AnthropicNativeAdapter,
        protocol=PROTOCOL_ANTHROPIC,
        native_base_url="https://api.anthropic.com/v1",
        default_model="claude-sonnet-4-20250514",
    ),
    GEMINI_NATIVE: ProviderSpec(
        provider=GEMINI_NATIVE,
        adapter_cls=GeminiNativeAdapter,
        protocol=PROTOCOL_GEMINI,
        native_base_url="https://generativelanguage.googleapis.com/v1beta",
        default_model="gemini-1.5-pro",
    ),
    OPENAI_COMPATIBLE_GENERIC: ProviderSpec(
        provider=OPENAI_COMPATIBLE_GENERIC,
        adapter_cls=OpenAICompatibleAdapter,
        protocol=PROTOCOL_OPENAI,
        native_base_url=None,  # viene del endpoint profile
        default_model="gpt-4o-mini",
        uses_endpoint_profile=True,
    ),
}


def is_known_provider(provider: str) -> bool:
    return provider in PROVIDER_SPECS


def get_spec(provider: str) -> ProviderSpec | None:
    return PROVIDER_SPECS.get(provider)


def get_endpoint_profile(profile_id: str) -> EndpointProfile | None:
    return ENDPOINT_PROFILES.get(profile_id)
