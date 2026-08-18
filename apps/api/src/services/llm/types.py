"""W10 — Tipos canónicos del Provider Gateway Multi-LLM.

Tipos NEUTRALES de proveedor: el core de Daily System no depende del formato
HTTP de ningún proveedor concreto. Cada adapter (services/llm/adapters/)
traduce estos tipos canónicos al protocolo de su proveedor y viceversa.

Reglas del contrato W10:
  - NO hay lógica financiera aquí (el dominio financiero vive en services/).
  - NO se importan SDKs de proveedor (openai/anthropic/google/mistral/
    langchain/litellm). Solo httpx +stdlib.
  - LLMResolvedProvider guarda la clave de forma TRANSITORIA (el gateway la
    consume para llamar al proveedor); la capa API NUNCA la serializa — solo
    expone credential_source.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class LLMMessage:
    """Un mensaje de chat (neutro de proveedor).

    role: "system" | "user" | "assistant" | "tool"
    content: texto (puede ser None cuando el mensaje es solo tool_calls o parts).
    tool_calls: tool calls que emite un mensaje de assistant.
    tool_call_id: para mensajes de role "tool", el id del tool call que responde.
    name: nombre de la tool (mensajes de role "tool").
    parts: contenido multimodal (vision) como lista de partes {"type": "text"|"image_url", ...}.
    """

    role: str
    content: str | None = None
    tool_calls: list[LLMToolCall] = field(default_factory=list)
    tool_call_id: str | None = None
    name: str | None = None
    parts: list[dict[str, Any]] | None = None


@dataclass
class LLMToolDefinition:
    """Definición de una tool/function (neutra de proveedor).

    parameters: JSON Schema del argumento (o None para tool sin argumentos).
    """

    name: str
    description: str | None = None
    parameters: dict[str, Any] | None = None


@dataclass
class LLMToolCall:
    """Un tool call solicitado por el modelo (neutro de proveedor).

    arguments: dict JSON ya parseado (el adapter se encarga de parsear el
    string JSON que emiten la mayoría de proveedores).
    """

    id: str
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass
class LLMUsage:
    """Uso de tokens (neutro de proveedor)."""

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


@dataclass
class LLMRequest:
    """Una petición LLM canónica (neutra de proveedor).

    system/context: se modela como un LLMMessage de role "system" dentro de
    messages (la mayoría de proveedores lo aceptan así; Anthropic lo extrae).
    response_format: estructura de respuesta estructurada/JSON. Para el
    protocolo OpenAI es el dict tal cual ({"type": "json_object"} o un JSON
    Schema); los adapters nativos lo traducen a su equivalente.
    stream: capability de streaming (W10 certifica la negociación; el
    endpoint productivo de streaming es W11).
    metadata: metadatos técnicos NO sensibles (nunca claves ni PII).
    """

    model: str
    messages: list[LLMMessage]
    max_output_tokens: int | None = None
    temperature: float | None = None
    tools: list[LLMToolDefinition] | None = None
    response_format: dict[str, Any] | None = None
    stream: bool = False
    metadata: dict[str, Any] | None = None


@dataclass
class LLMResponse:
    """Una respuesta LLM canónica (neutra de proveedor).

    provider_request_id: id de petición del proveedor SANITIZADO (no sensible).
    latency_ms: latencia de ida y vuelta medida por el gateway.
    """

    content: str | None = None
    tool_calls: list[LLMToolCall] = field(default_factory=list)
    finish_reason: str | None = None
    usage: LLMUsage = field(default_factory=LLMUsage)
    provider: str | None = None
    model: str | None = None
    provider_request_id: str | None = None
    latency_ms: int | None = None


@dataclass(frozen=True)
class LLMCapabilities:
    """Capacidades REALES que un provider/model soporta.

    Cada adapter declara sus capacidades reales. El gateway las negocia contra
    los requisitos de la petición: si una operación exige una capability que el
    provider/model no soporta, el gateway responde UNSUPPORTED_CAPABILITY
    (nunca degrada en silencio a texto).
    """

    text: bool = True
    tools: bool = False
    structured_output: bool = False
    vision: bool = False
    streaming: bool = False

    def supports(self, capability: str) -> bool:
        return bool(getattr(self, capability, False))


@dataclass
class LLMResolvedProvider:
    """Resultado de la resolución de credenciales para (negocio, provider).

    Orden obligatorio de resolución (credentials.py):
      TENANT_BYOK activo -> PLATFORM_MANAGED disponible -> PROVIDER_UNAVAILABLE

    credential_source: "TENANT_BYOK" | "PLATFORM_MANAGED" | None.
    api_key: TRANSITORIA — el gateway la consume para llamar al proveedor; la
    capa API NUNCA la serializa (solo expone credential_source).
    base_url: URL base a llamar (del endpoint profile allowlistado o nativa).
    available: False cuando no hay credencial (PROVIDER_UNAVAILABLE).
    """

    provider: str
    available: bool
    credential_source: str | None = None
    api_key: str | None = None
    base_url: str | None = None
    model: str | None = None
    capabilities: LLMCapabilities | None = None
    endpoint_profile: str | None = None
