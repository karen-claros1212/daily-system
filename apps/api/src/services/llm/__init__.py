"""W10 — Capa Multi-LLM / Provider Gateway + BYOK.

Paquete del Provider Gateway: tipos canónicos, registry de proveedores,
SecretStore, resolver de credenciales, gateway y adapters. El core de Daily
System NO importa SDKs de proveedor — solo httpx + stdlib.
"""

from src.services.llm.errors import LLMErrorClass, LLMProviderError, ALL_ERROR_CLASSES
from src.services.llm.gateway import LLMObservation, ProviderGateway, get_gateway
from src.services.llm.registry import (
    ALL_PROVIDERS,
    ENDPOINT_PROFILES,
    PROVIDER_SPECS,
    ProviderSpec,
    EndpointProfile,
    get_endpoint_profile,
    get_spec,
    is_known_provider,
)
from src.services.llm.secret_store import (
    SecretNotFound,
    SecretStore,
    SecretStoreError,
    SecretStoreNotConfigured,
)
from src.services.llm.types import (
    LLMCapabilities,
    LLMMessage,
    LLMRequest,
    LLMResolvedProvider,
    LLMResponse,
    LLMToolCall,
    LLMToolDefinition,
    LLMUsage,
)

__all__ = [
    "LLMErrorClass",
    "LLMProviderError",
    "ALL_ERROR_CLASSES",
    "LLMObservation",
    "ProviderGateway",
    "get_gateway",
    "ALL_PROVIDERS",
    "ENDPOINT_PROFILES",
    "PROVIDER_SPECS",
    "ProviderSpec",
    "EndpointProfile",
    "get_endpoint_profile",
    "get_spec",
    "is_known_provider",
    "SecretNotFound",
    "SecretStore",
    "SecretStoreError",
    "SecretStoreNotConfigured",
    "LLMCapabilities",
    "LLMMessage",
    "LLMRequest",
    "LLMResolvedProvider",
    "LLMResponse",
    "LLMToolCall",
    "LLMToolDefinition",
    "LLMUsage",
]
