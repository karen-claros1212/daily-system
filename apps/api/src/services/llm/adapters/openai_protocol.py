"""W10 — Adapter del protocolo OpenAI (chat completions).

Compartido por las familias que implementan el contrato OpenAI-compatible:
  - OPENAI_NATIVE            (api.openai.com)
  - MISTRAL_NATIVE           (api.mistral.ai — API OpenAI-compatible)
  - CEREBRAS_OPENAI_COMPATIBLE (api.cerebras.ai — OpenAI-compatible)
  - OPENAI_COMPATIBLE_GENERIC  (endpoint profiles allowlistados)

Cada subclase fija su base_url nativo y sus capacidades. El mapping
request/response al protocolo OpenAI vive aquí (una sola implementación).

Contrato HTTP verificado contra la documentación oficial de OpenAI
(/v1/chat/completions). Para los compatibles (Mistral/Cerebras/generic) se
valida el contrato compatible SIN asumir que todas las features de OpenAI
existen: las capacidades se declaran por adapter.
"""

from __future__ import annotations

import json
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


class OpenAIProtocolAdapter(BaseAdapter):
    """Implementa el protocolo OpenAI chat completions."""

    protocol = "openai"

    # --- request mapping ---

    def _map_message(self, m: LLMMessage) -> dict[str, Any]:
        msg: dict[str, Any] = {"role": m.role}
        if m.parts is not None:
            # Vision/multimodal: content como lista de partes.
            msg["content"] = m.parts
        elif m.content is not None:
            msg["content"] = m.content
        if m.role == "assistant" and m.tool_calls:
            msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.name, "arguments": json.dumps(tc.arguments)},
                }
                for tc in m.tool_calls
            ]
        if m.role == "tool":
            if m.tool_call_id is not None:
                msg["tool_call_id"] = m.tool_call_id
            if m.name is not None:
                msg["name"] = m.name
        return msg

    def _build_body(self, request: LLMRequest) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": request.model or self.model,
            "messages": [self._map_message(m) for m in request.messages],
        }
        if request.max_output_tokens is not None:
            body["max_tokens"] = request.max_output_tokens
        if request.temperature is not None:
            body["temperature"] = request.temperature
        if request.tools:
            body["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        **({"description": t.description} if t.description else {}),
                        "parameters": t.parameters or {"type": "object", "properties": {}},
                    },
                }
                for t in request.tools
            ]
        if request.response_format is not None:
            body["response_format"] = request.response_format
        if request.stream:
            body["stream"] = True
        return body

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    # --- response mapping ---

    def _parse_response(self, resp: httpx.Response, start: float) -> LLMResponse:
        latency = int((time.monotonic() - start) * 1000)
        err = self._classify_http(resp.status_code, provider=self.provider, model=self.model)
        if err is not None:
            raise err
        try:
            data = resp.json()
        except (json.JSONDecodeError, ValueError):
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

    def _map_response(self, data: dict[str, Any], latency: int) -> LLMResponse:
        choices = data.get("choices") or []
        content: str | None = None
        tool_calls: list[LLMToolCall] = []
        finish_reason: str | None = None
        if choices:
            choice = choices[0]
            message = choice.get("message") or {}
            content = message.get("content")
            finish_reason = choice.get("finish_reason")
            for tc in message.get("tool_calls") or []:
                fn = tc.get("function") or {}
                raw_args = fn.get("arguments")
                if isinstance(raw_args, str):
                    try:
                        args = json.loads(raw_args) if raw_args else {}
                    except json.JSONDecodeError:
                        args = {"_raw": raw_args}
                elif isinstance(raw_args, dict):
                    args = raw_args
                else:
                    args = {}
                tool_calls.append(
                    LLMToolCall(id=tc.get("id", ""), name=fn.get("name", ""), arguments=args)
                )
        usage_raw = data.get("usage") or {}
        usage = LLMUsage(
            input_tokens=int(usage_raw.get("prompt_tokens") or 0),
            output_tokens=int(usage_raw.get("completion_tokens") or 0),
            total_tokens=int(usage_raw.get("total_tokens") or 0),
        )
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

    # --- complete ---

    def complete(self, request: LLMRequest) -> LLMResponse:
        start = time.monotonic()
        body = self._build_body(request)
        try:
            resp = self._client.post(
                "/chat/completions",
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
