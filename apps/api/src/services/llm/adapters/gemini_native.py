"""W10 — Adapter GEMINI_NATIVE (generativelanguage.googleapis.com).

Protocolo PROPIO de Google Gemini (generateContent) — no es OpenAI-compatible.
Diferencias clave:
  - Endpoint: /v1beta/models/{model}:generateContent (el model va en la URL).
  - Auth: header x-goog-api-key.
  - `contents` (role user/model) en vez de messages; `systemInstruction` para
    system.
  - `generationConfig` para maxOutputTokens/temperature.
  - Tools: `tools[].functionDeclarations`.
  - Respuesta: `candidates[0].content.parts` (text / functionCall);
    `finishReason`; `usageMetadata` (prompt/candidates/total).

Contrato HTTP verificado contra la documentación oficial de Gemini
(generativelanguage.googleapis.com — v1beta generateContent).
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

NATIVE_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

# Mapeo finishReason (Gemini) -> finish_reason (canónico).
_FINISH_REASON_MAP = {
    "STOP": "stop",
    "MAX_TOKENS": "length",
    "SAFETY": "stop",
    "RECITATION": "stop",
    "TOOL_USE": "tool_calls",
}


class GeminiNativeAdapter(BaseAdapter):
    """Implementa el protocolo generateContent de Gemini."""

    provider = "GEMINI_NATIVE"
    protocol = "gemini"

    def __init__(
        self,
        base_url: str = NATIVE_BASE_URL,
        api_key: str = "",
        model: str = "gemini-1.5-pro",
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
            "x-goog-api-key": self.api_key,
            "Content-Type": "application/json",
        }

    def _map_part_text(self, text: str) -> dict[str, Any]:
        return {"text": text}

    def _map_message(self, m: LLMMessage) -> dict[str, Any] | None:
        role = "model" if m.role == "assistant" else m.role
        parts: list[dict[str, Any]] = []
        if m.parts is not None:
            for part in m.parts:
                ptype = part.get("type")
                if ptype == "text":
                    parts.append(self._map_part_text(part.get("text", "")))
                elif ptype == "image_url":
                    url = (part.get("image_url") or {}).get("url", "")
                    if url.startswith("data:"):
                        header, _, data = url.partition(",")
                        media_type = header.split(";")[0].replace("data:", "")
                        parts.append({"inlineData": {"mimeType": media_type, "data": data}})
                    else:
                        parts.append({"fileData": {"mimeType": "image/png", "fileUri": url}})
        elif m.content is not None:
            parts.append(self._map_part_text(m.content))
        # tool calls del assistant -> functionCall parts.
        for tc in m.tool_calls:
            parts.append({"functionCall": {"name": tc.name, "args": tc.arguments}})
        # resultado de tool -> part functionResponse en un mensaje user.
        if m.role == "tool":
            return {
                "role": "user",
                "parts": [
                    {
                        "functionResponse": {
                            "name": m.name or "",
                            "response": {"result": m.content or ""},
                        }
                    }
                ],
            }
        if not parts:
            return None
        return {"role": role, "parts": parts}

    def _build_body(self, request: LLMRequest) -> dict[str, Any]:
        system_parts: list[dict[str, Any]] = []
        contents: list[dict[str, Any]] = []
        for m in request.messages:
            if m.role == "system" and m.content:
                system_parts.append(self._map_part_text(m.content))
                continue
            mapped = self._map_message(m)
            if mapped is not None:
                contents.append(mapped)
        body: dict[str, Any] = {"contents": contents}
        if system_parts:
            body["systemInstruction"] = {"parts": system_parts}
        gen_config: dict[str, Any] = {}
        if request.max_output_tokens is not None:
            gen_config["maxOutputTokens"] = request.max_output_tokens
        if request.temperature is not None:
            gen_config["temperature"] = request.temperature
        if gen_config:
            body["generationConfig"] = gen_config
        if request.tools:
            body["tools"] = [
                {
                    "functionDeclarations": [
                        {
                            "name": t.name,
                            **({"description": t.description} if t.description else {}),
                            "parameters": t.parameters or {"type": "object", "properties": {}},
                        }
                        for t in request.tools
                    ]
                }
            ]
        if request.stream:
            body["stream"] = True
        return body

    # --- response mapping ---

    def _map_response(self, data: dict[str, Any], latency: int) -> LLMResponse:
        candidates = data.get("candidates") or []
        content: str | None = None
        tool_calls: list[LLMToolCall] = []
        finish_reason: str | None = None
        if candidates:
            candidate = candidates[0]
            finish_reason_raw = candidate.get("finishReason")
            finish_reason = _FINISH_REASON_MAP.get(finish_reason_raw or "", finish_reason_raw)
            for part in (candidate.get("content") or {}).get("parts") or []:
                if "text" in part:
                    text = part.get("text", "")
                    content = (content + "\n" + text) if content else text
                elif "functionCall" in part:
                    fc = part.get("functionCall") or {}
                    tool_calls.append(
                        LLMToolCall(
                            id=f"gemini-fc-{len(tool_calls)}",
                            name=fc.get("name", ""),
                            arguments=fc.get("args") or {},
                        )
                    )
        usage_raw = data.get("usageMetadata") or {}
        input_tokens = int(usage_raw.get("promptTokenCount") or 0)
        output_tokens = int(usage_raw.get("candidatesTokenCount") or 0)
        total_tokens = int(usage_raw.get("totalTokenCount") or (input_tokens + output_tokens))
        usage = LLMUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
        )
        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            finish_reason=finish_reason,
            usage=usage,
            provider=self.provider,
            model=data.get("modelVersion") or self.model,
            provider_request_id=None,  # Gemini no emite un request id estable en v1beta
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
        # Gemini devuelve errores con 200 + "error" key en algunos casos.
        if "error" in data and "candidates" not in data:
            code = (data.get("error") or {}).get("code")
            if code in (401, 403):
                raise LLMProviderError("AUTH_ERROR", provider=self.provider, model=self.model, upstream_status=code)
            if code == 429:
                raise LLMProviderError("RATE_LIMITED", provider=self.provider, model=self.model, upstream_status=429)
            raise LLMProviderError("UPSTREAM_ERROR", provider=self.provider, model=self.model, upstream_status=code)
        return self._map_response(data, latency)

    def complete(self, request: LLMRequest) -> LLMResponse:
        model = request.model or self.model
        start = time.monotonic()
        body = self._build_body(request)
        path = f"/models/{model}:generateContent"
        try:
            resp = self._client.post(
                path,
                headers=self._headers(),
                json=body,
                follow_redirects=False,
            )
        except httpx.TimeoutException as e:
            raise LLMProviderError(
                "TIMEOUT",
                "upstream timeout",
                provider=self.provider,
                model=model,
            ) from e
        except httpx.HTTPError as e:
            raise LLMProviderError(
                "PROVIDER_UNAVAILABLE",
                "connection error",
                provider=self.provider,
                model=model,
            ) from e
        return self._parse_response(resp, start)
