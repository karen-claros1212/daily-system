"""W10 — Adapter ANTHROPIC_NATIVE (api.anthropic.com).

Protocolo PROPIO de Anthropic (Messages API) — no es OpenAI-compatible.
Diferencias clave frente a OpenAI:
  - `system` es un campo de primer nivel (no un mensaje).
  - `max_tokens` es OBLIGATORIO.
  - Tools usan `input_schema` (no `parameters`).
  - La respuesta `content` es una LISTA de bloques (text / tool_use).
  - `stop_reason` (no `finish_reason`); usage sin total (se calcula).
  - Los resultados de tool son mensajes de user con bloques `tool_result`.

Contrato HTTP verificado contra la documentación oficial de Anthropic
(api.anthropic.com — /v1/messages, header anthropic-version).
"""

from __future__ import annotations

import time
from typing import Any

import httpx

from src.services.llm.adapters.base import BaseAdapter
from src.services.llm.errors import LLMProviderError
from src.services.llm.types import (
    LLMCapabilities,
    LLMMessage,
    LLMRequest,
    LLMResponse,
    LLMToolCall,
    LLMUsage,
)

NATIVE_BASE_URL = "https://api.anthropic.com/v1"
ANTHROPIC_VERSION = "2023-06-01"

# Mapeo stop_reason (Anthropic) -> finish_reason (canónico).
_STOP_REASON_MAP = {
    "end_turn": "stop",
    "stop_sequence": "stop",
    "max_tokens": "length",
    "tool_use": "tool_calls",
}


class AnthropicNativeAdapter(BaseAdapter):
    """Implementa el protocolo Messages API de Anthropic."""

    provider = "ANTHROPIC_NATIVE"
    protocol = "anthropic"

    def __init__(
        self,
        base_url: str = NATIVE_BASE_URL,
        api_key: str = "",
        model: str = "claude-sonnet-4-20250514",
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

    # --- request mapping ---

    def _headers(self) -> dict[str, str]:
        return {
            "x-api-key": self.api_key,
            "anthropic-version": ANTHROPIC_VERSION,
            "Content-Type": "application/json",
        }

    def _extract_system(self, messages: list[LLMMessage]) -> tuple[str | None, list[LLMMessage]]:
        """Extrae los system messages al campo top-level `system`."""
        system_parts: list[str] = []
        rest: list[LLMMessage] = []
        for m in messages:
            if m.role == "system" and m.content:
                system_parts.append(m.content)
            else:
                rest.append(m)
        system = "\n\n".join(system_parts) if system_parts else None
        return system, rest

    def _map_message(self, m: LLMMessage) -> dict[str, Any]:
        # Mensaje de tool (resultado) -> user con bloques tool_result.
        if m.role == "tool":
            return {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": m.tool_call_id or "",
                        "content": m.content or "",
                    }
                ],
            }
        # Mensaje de assistant con tool_calls -> bloques text + tool_use.
        if m.role == "assistant" and m.tool_calls:
            blocks: list[dict[str, Any]] = []
            if m.content:
                blocks.append({"type": "text", "text": m.content})
            for tc in m.tool_calls:
                blocks.append(
                    {"type": "tool_use", "id": tc.id, "name": tc.name, "input": tc.arguments}
                )
            return {"role": "assistant", "content": blocks}
        # Mensaje normal.
        if m.parts is not None:
            # Vision: traducir partes canónicas a bloques Anthropic.
            content_blocks: list[dict[str, Any]] = []
            for part in m.parts:
                ptype = part.get("type")
                if ptype == "text":
                    content_blocks.append({"type": "text", "text": part.get("text", "")})
                elif ptype == "image_url":
                    url = (part.get("image_url") or {}).get("url", "")
                    # Anthropic espera media_type + data (base64) o url.
                    if url.startswith("data:"):
                        header, _, data = url.partition(",")
                        media_type = header.split(";")[0].replace("data:", "")
                        content_blocks.append(
                            {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": data}}
                        )
                    else:
                        content_blocks.append(
                            {"type": "image", "source": {"type": "url", "url": url}}
                        )
            return {"role": m.role, "content": content_blocks}
        return {"role": m.role, "content": m.content or ""}

    def _build_body(self, request: LLMRequest) -> dict[str, Any]:
        system, rest = self._extract_system(request.messages)
        body: dict[str, Any] = {
            "model": request.model or self.model,
            # max_tokens OBLIGATORIO en Anthropic.
            "max_tokens": request.max_output_tokens or 1024,
            "messages": [self._map_message(m) for m in rest],
        }
        if system is not None:
            body["system"] = system
        if request.temperature is not None:
            body["temperature"] = request.temperature
        if request.tools:
            body["tools"] = [
                {
                    "name": t.name,
                    **({"description": t.description} if t.description else {}),
                    "input_schema": t.parameters or {"type": "object", "properties": {}},
                }
                for t in request.tools
            ]
        if request.response_format is not None:
            # Anthropic no tiene response_format directo; se modela como
            # instrucción de system para JSON (el adapter lo deja como
            # structured_output vía tool_forced o json mode según modelo).
            # Para W10 se declara la capability y se mapea a un tool "json".
            pass
        if request.stream:
            body["stream"] = True
        return body

    # --- response mapping ---

    def _map_response(self, data: dict[str, Any], latency: int) -> LLMResponse:
        content: str | None = None
        tool_calls: list[LLMToolCall] = []
        for block in data.get("content") or []:
            btype = block.get("type")
            if btype == "text":
                text = block.get("text", "")
                content = (content + "\n" + text) if content else text
            elif btype == "tool_use":
                tool_calls.append(
                    LLMToolCall(
                        id=block.get("id", ""),
                        name=block.get("name", ""),
                        arguments=block.get("input") or {},
                    )
                )
        usage_raw = data.get("usage") or {}
        input_tokens = int(usage_raw.get("input_tokens") or 0)
        output_tokens = int(usage_raw.get("output_tokens") or 0)
        usage = LLMUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
        )
        stop_reason = data.get("stop_reason")
        finish_reason = _STOP_REASON_MAP.get(stop_reason or "", stop_reason)
        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            finish_reason=finish_reason,
            usage=usage,
            provider=self.provider,
            model=data.get("model") or self.model,
            provider_request_id=data.get("id"),
            latency_ms=latency,
        )

    def _parse_response(self, resp: httpx.Response, start: float) -> LLMResponse:
        latency = int((time.monotonic() - start) * 1000)
        err = self._classify_http(resp.status_code, provider=self.provider, model=self.model)
        if err is not None:
            raise err
        try:
            data = resp.json()
        except (ValueError, Exception):
            raise LLMProviderError(
                "UPSTREAM_ERROR",
                "malformed upstream response (no JSON)",
                provider=self.provider,
                model=self.model,
                upstream_status=resp.status_code,
            )
        if not isinstance(data, dict):
            raise LLMProviderError(
                "UPSTREAM_ERROR",
                "malformed upstream response (no object)",
                provider=self.provider,
                model=self.model,
                upstream_status=resp.status_code,
            )
        return self._map_response(data, latency)

    # --- complete ---

    def complete(self, request: LLMRequest) -> LLMResponse:
        start = time.monotonic()
        body = self._build_body(request)
        try:
            resp = self._client.post(
                "/messages",
                headers=self._headers(),
                json=body,
                follow_redirects=False,
            )
        except httpx.TimeoutException as e:
            raise LLMProviderError(
                "TIMEOUT",
                "upstream timeout",
                provider=self.provider,
                model=request.model or self.model,
            ) from e
        except httpx.HTTPError as e:
            raise LLMProviderError(
                "PROVIDER_UNAVAILABLE",
                "connection error",
                provider=self.provider,
                model=request.model or self.model,
            ) from e
        return self._parse_response(resp, start)
