"""W10 — Contract tests por adapter (6 familias MUST).

NO llaman servicios reales: usan httpx.MockTransport (fake server
determinista). Para cada adapter se verifica:
  - request mapping (body enviado al protocolo correcto)
  - response mapping (LLMResponse canónico)
  - usage
  - error auth (401/403 -> AUTH_ERROR)
  - rate limit (429 -> RATE_LIMITED)
  - timeout (-> TIMEOUT)
  - malformed upstream response (-> UPSTREAM_ERROR)
  - capabilities declaradas
  - tool calls (cuando corresponde)
  - structured output (cuando corresponde)

Los native adapters validan su protocolo propio; los OpenAI-compatible
validan el contrato compatible sin asumir todas las features de OpenAI.
"""

from __future__ import annotations

import json

import httpx
import pytest

from src.services.llm.adapters import (
    AnthropicNativeAdapter,
    CerebrasOpenAIAdapter,
    GeminiNativeAdapter,
    MistralNativeAdapter,
    OpenAICompatibleAdapter,
    OpenAINativeAdapter,
)
from src.services.llm.errors import LLMProviderError
from src.services.llm.types import LLMMessage, LLMRequest, LLMToolDefinition


# --- helpers de fake server ---


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler), base_url="http://test")


def _openai_ok(body: dict | None = None) -> httpx.Response:
    payload = {
        "id": "chatcmpl-123",
        "object": "chat.completion",
        "model": "gpt-4o",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "hola", "tool_calls": []},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 5, "completion_tokens": 7, "total_tokens": 12},
    }
    if body:
        payload.update(body)
    return httpx.Response(200, json=payload)


def _req() -> LLMRequest:
    return LLMRequest(
        model="gpt-4o",
        messages=[
            LLMMessage(role="system", content="eres un asistente"),
            LLMMessage(role="user", content="hola"),
        ],
        max_output_tokens=100,
        temperature=0.5,
    )


# --- OPENAI_NATIVE ---


class TestOpenAINativeContract:
    def test_request_mapping(self):
        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["path"] = request.url.path
            captured["auth"] = request.headers.get("authorization")
            captured["body"] = json.loads(request.content)
            return _openai_ok()

        a = OpenAINativeAdapter(api_key="sk-test", model="gpt-4o", client=_client(handler))
        a.complete(_req())
        assert captured["path"] == "/chat/completions"
        assert captured["auth"] == "Bearer sk-test"
        body = captured["body"]
        assert body["model"] == "gpt-4o"
        assert body["max_tokens"] == 100
        assert body["temperature"] == 0.5
        # system + user messages en orden.
        assert body["messages"][0] == {"role": "system", "content": "eres un asistente"}
        assert body["messages"][1] == {"role": "user", "content": "hola"}

    def test_response_mapping_and_usage(self):
        a = OpenAINativeAdapter(api_key="k", model="gpt-4o", client=_client(lambda r: _openai_ok()))
        resp = a.complete(_req())
        assert resp.content == "hola"
        assert resp.finish_reason == "stop"
        assert resp.usage.input_tokens == 5
        assert resp.usage.output_tokens == 7
        assert resp.usage.total_tokens == 12
        assert resp.provider_request_id == "chatcmpl-123"
        assert resp.latency_ms is not None

    def test_auth_error(self):
        a = OpenAINativeAdapter(api_key="k", client=_client(lambda r: httpx.Response(401, json={"error": "bad"})))
        with pytest.raises(LLMProviderError) as e:
            a.complete(_req())
        assert e.value.error_class == "AUTH_ERROR"
        assert e.value.status_code == 401

    def test_rate_limited(self):
        a = OpenAINativeAdapter(api_key="k", client=_client(lambda r: httpx.Response(429, json={})
))
        with pytest.raises(LLMProviderError) as e:
            a.complete(_req())
        assert e.value.error_class == "RATE_LIMITED"
        assert e.value.status_code == 429

    def test_timeout(self):
        def handler(r):
            raise httpx.TimeoutException("slow")

        a = OpenAINativeAdapter(api_key="k", client=_client(handler))
        with pytest.raises(LLMProviderError) as e:
            a.complete(_req())
        assert e.value.error_class == "TIMEOUT"

    def test_provider_unavailable_5xx(self):
        a = OpenAINativeAdapter(api_key="k", client=_client(lambda r: httpx.Response(503, json={})
))
        with pytest.raises(LLMProviderError) as e:
            a.complete(_req())
        assert e.value.error_class == "PROVIDER_UNAVAILABLE"

    def test_malformed_upstream(self):
        a = OpenAINativeAdapter(api_key="k", client=_client(lambda r: httpx.Response(200, content=b"no-json"))
)
        with pytest.raises(LLMProviderError) as e:
            a.complete(_req())
        assert e.value.error_class == "UPSTREAM_ERROR"

    def test_capabilities(self):
        a = OpenAINativeAdapter(api_key="k")
        caps = a.capabilities()
        assert caps.text and caps.tools and caps.structured_output and caps.vision and caps.streaming

    def test_tool_calls_mapping(self):
        payload = {
            "id": "chatcmpl-tc",
            "model": "gpt-4o",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "call_1",
                                "type": "function",
                                "function": {"name": "get_weather", "arguments": '{"city": "Bogota"}'},
                            }
                        ],
                    },
                    "finish_reason": "tool_calls",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }
        a = OpenAINativeAdapter(api_key="k", client=_client(lambda r: httpx.Response(200, json=payload)))
        req = LLMRequest(
            model="gpt-4o",
            messages=[LLMMessage(role="user", content="clima?")],
            tools=[LLMToolDefinition(name="get_weather", description="d", parameters={"type": "object"})],
        )
        resp = a.complete(req)
        assert resp.finish_reason == "tool_calls"
        assert len(resp.tool_calls) == 1
        assert resp.tool_calls[0].name == "get_weather"
        assert resp.tool_calls[0].arguments == {"city": "Bogota"}

    def test_structured_output_request(self):
        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["body"] = json.loads(request.content)
            return _openai_ok()

        a = OpenAINativeAdapter(api_key="k", client=_client(handler))
        req = LLMRequest(
            model="gpt-4o",
            messages=[LLMMessage(role="user", content="json")],
            response_format={"type": "json_object"},
        )
        a.complete(req)
        assert captured["body"]["response_format"] == {"type": "json_object"}


# --- MISTRAL_NATIVE (protocolo OpenAI-compatible, base_url propio) ---


class TestMistralContract:
    def test_native_base_url(self):
        a = MistralNativeAdapter(api_key="k")
        assert a.base_url == "https://api.mistral.ai/v1"

    def test_request_mapping(self):
        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["auth"] = request.headers.get("authorization")
            captured["body"] = json.loads(request.content)
            return _openai_ok({"model": "mistral-large-latest"})

        a = MistralNativeAdapter(api_key="mkey", model="mistral-large-latest", client=_client(handler))
        a.complete(LLMRequest(model="mistral-large-latest", messages=[LLMMessage(role="user", content="hola")]))
        assert captured["auth"] == "Bearer mkey"
        assert captured["body"]["model"] == "mistral-large-latest"

    def test_capabilities(self):
        a = MistralNativeAdapter(api_key="k")
        caps = a.capabilities()
        assert caps.text and caps.tools and caps.streaming

    def test_response_mapping(self):
        a = MistralNativeAdapter(api_key="k", client=_client(lambda r: _openai_ok({"model": "mistral"})))
        resp = a.complete(_req())
        assert resp.content == "hola"
        assert resp.provider == "MISTRAL_NATIVE"


# --- CEREBRAS_OPENAI_COMPATIBLE ---


class TestCerebrasContract:
    def test_native_base_url(self):
        a = CerebrasOpenAIAdapter(api_key="k")
        assert a.base_url == "https://api.cerebras.ai/v1"

    def test_request_and_response(self):
        a = CerebrasOpenAIAdapter(
            api_key="k", model="llama3.1-70b", client=_client(lambda r: _openai_ok({"model": "llama3.1-70b"}))
        )
        resp = a.complete(LLMRequest(model="llama3.1-70b", messages=[LLMMessage(role="user", content="hola")]))
        assert resp.content == "hola"
        assert resp.provider == "CEREBRAS_OPENAI_COMPATIBLE"

    def test_capabilities_conservadoras(self):
        a = CerebrasOpenAIAdapter(api_key="k")
        caps = a.capabilities()
        assert caps.text and caps.streaming
        assert not caps.tools  # conservador: no garantiza function calling


# --- OPENAI_COMPATIBLE_GENERIC (endpoint profiles) ---


class TestOpenAICompatibleContract:
    def test_request_mapping(self):
        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["body"] = json.loads(request.content)
            return _openai_ok({"model": "llama-3.1-70b-instruct"})

        a = OpenAICompatibleAdapter(
            base_url="https://openrouter.ai/api/v1",
            api_key="or-key",
            model="openrouter/llama-3.1-70b",
            client=_client(handler),
        )
        a.complete(LLMRequest(model="openrouter/llama-3.1-70b", messages=[LLMMessage(role="user", content="hola")]))
        assert captured["body"]["model"] == "openrouter/llama-3.1-70b"

    def test_capabilities_from_profile(self):
        from src.services.llm.types import LLMCapabilities

        a = OpenAICompatibleAdapter(
            base_url="http://x",
            api_key="k",
            capabilities=LLMCapabilities(text=True, tools=True, streaming=True),
        )
        caps = a.capabilities()
        assert caps.tools and caps.streaming
        assert not caps.vision


# --- ANTHROPIC_NATIVE (protocolo propio Messages API) ---


def _anthropic_ok(payload: dict | None = None) -> httpx.Response:
    base = {
        "id": "msg_123",
        "type": "message",
        "role": "assistant",
        "model": "claude-sonnet-4-20250514",
        "content": [{"type": "text", "text": "hola claude"}],
        "stop_reason": "end_turn",
        "usage": {"input_tokens": 8, "output_tokens": 4},
    }
    if payload:
        base.update(payload)
    return httpx.Response(200, json=base)


class TestAnthropicContract:
    def test_request_mapping_system_top_level(self):
        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["path"] = request.url.path
            captured["x_api_key"] = request.headers.get("x-api-key")
            captured["version"] = request.headers.get("anthropic-version")
            captured["body"] = json.loads(request.content)
            return _anthropic_ok()

        a = AnthropicNativeAdapter(api_key="ak", model="claude-sonnet-4-20250514", client=_client(handler))
        a.complete(_req())
        assert captured["path"] == "/messages"
        assert captured["x_api_key"] == "ak"
        assert captured["version"] == "2023-06-01"
        body = captured["body"]
        # system extraído a top-level; max_tokens obligatorio.
        assert body["system"] == "eres un asistente"
        assert body["max_tokens"] == 100
        assert body["messages"][0] == {"role": "user", "content": "hola"}
        assert body["model"] == "gpt-4o" or body["model"]

    def test_response_mapping(self):
        a = AnthropicNativeAdapter(api_key="k", client=_client(lambda r: _anthropic_ok()))
        resp = a.complete(_req())
        assert resp.content == "hola claude"
        assert resp.finish_reason == "stop"  # end_turn -> stop
        assert resp.usage.input_tokens == 8
        assert resp.usage.output_tokens == 4
        assert resp.usage.total_tokens == 12
        assert resp.provider_request_id == "msg_123"

    def test_tool_use_mapping(self):
        payload = {
            "id": "msg_tc",
            "model": "claude-sonnet-4-20250514",
            "content": [
                {"type": "text", "text": "llamando tool"},
                {"type": "tool_use", "id": "toolu_1", "name": "get_weather", "input": {"city": "Bogota"}},
            ],
            "stop_reason": "tool_use",
            "usage": {"input_tokens": 10, "output_tokens": 10},
        }
        a = AnthropicNativeAdapter(api_key="k", client=_client(lambda r: httpx.Response(200, json=payload)))
        req = LLMRequest(
            model="claude-sonnet-4-20250514",
            messages=[LLMMessage(role="user", content="clima?")],
            tools=[LLMToolDefinition(name="get_weather", parameters={"type": "object"})],
        )
        resp = a.complete(req)
        assert resp.finish_reason == "tool_calls"  # tool_use -> tool_calls
        assert resp.tool_calls[0].name == "get_weather"
        assert resp.tool_calls[0].arguments == {"city": "Bogota"}

    def test_tools_use_input_schema(self):
        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["body"] = json.loads(request.content)
            return _anthropic_ok()

        a = AnthropicNativeAdapter(api_key="k", client=_client(handler))
        req = LLMRequest(
            model="claude",
            messages=[LLMMessage(role="user", content="x")],
            tools=[LLMToolDefinition(name="f", description="d", parameters={"type": "object", "properties": {}})],
        )
        a.complete(req)
        tool = captured["body"]["tools"][0]
        assert "input_schema" in tool
        assert tool["name"] == "f"

    def test_auth_error(self):
        a = AnthropicNativeAdapter(api_key="k", client=_client(lambda r: httpx.Response(401, json={})
))
        with pytest.raises(LLMProviderError) as e:
            a.complete(_req())
        assert e.value.error_class == "AUTH_ERROR"

    def test_rate_limited(self):
        a = AnthropicNativeAdapter(api_key="k", client=_client(lambda r: httpx.Response(429, json={})
))
        with pytest.raises(LLMProviderError) as e:
            a.complete(_req())
        assert e.value.error_class == "RATE_LIMITED"

    def test_malformed(self):
        a = AnthropicNativeAdapter(api_key="k", client=_client(lambda r: httpx.Response(200, content=b"??"))
)
        with pytest.raises(LLMProviderError) as e:
            a.complete(_req())
        assert e.value.error_class == "UPSTREAM_ERROR"

    def test_capabilities(self):
        a = AnthropicNativeAdapter(api_key="k")
        caps = a.capabilities()
        assert caps.text and caps.tools and caps.structured_output and caps.vision and caps.streaming


# --- GEMINI_NATIVE (protocolo propio generateContent) ---


def _gemini_ok(payload: dict | None = None) -> httpx.Response:
    base = {
        "candidates": [
            {
                "content": {"role": "model", "parts": [{"text": "hola gemini"}]},
                "finishReason": "STOP",
                "index": 0,
            }
        ],
        "usageMetadata": {"promptTokenCount": 6, "candidatesTokenCount": 3, "totalTokenCount": 9},
        "modelVersion": "gemini-1.5-pro",
    }
    if payload:
        base.update(payload)
    return httpx.Response(200, json=base)


class TestGeminiContract:
    def test_request_mapping(self):
        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["path"] = request.url.path
            captured["key"] = request.headers.get("x-goog-api-key")
            captured["body"] = json.loads(request.content)
            return _gemini_ok()

        a = GeminiNativeAdapter(api_key="gk", model="gemini-1.5-pro", client=_client(handler))
        gemini_req = LLMRequest(
            model="gemini-1.5-pro",
            messages=[
                LLMMessage(role="system", content="eres un asistente"),
                LLMMessage(role="user", content="hola"),
            ],
            max_output_tokens=100,
            temperature=0.5,
        )
        a.complete(gemini_req)
        # model va en la URL.
        assert captured["path"] == "/models/gemini-1.5-pro:generateContent"
        assert captured["key"] == "gk"
        body = captured["body"]
        assert body["systemInstruction"]["parts"][0]["text"] == "eres un asistente"
        assert body["contents"][0] == {"role": "user", "parts": [{"text": "hola"}]}
        assert body["generationConfig"]["maxOutputTokens"] == 100
        assert body["generationConfig"]["temperature"] == 0.5

    def test_response_mapping(self):
        a = GeminiNativeAdapter(api_key="k", client=_client(lambda r: _gemini_ok()))
        resp = a.complete(_req())
        assert resp.content == "hola gemini"
        assert resp.finish_reason == "stop"  # STOP -> stop
        assert resp.usage.input_tokens == 6
        assert resp.usage.output_tokens == 3
        assert resp.usage.total_tokens == 9
        assert resp.model == "gemini-1.5-pro"

    def test_function_call_mapping(self):
        payload = {
            "candidates": [
                {
                    "content": {
                        "role": "model",
                        "parts": [{"functionCall": {"name": "get_weather", "args": {"city": "Bogota"}}}],
                    },
                    "finishReason": "TOOL_USE",
                    "index": 0,
                }
            ],
            "usageMetadata": {"promptTokenCount": 5, "candidatesTokenCount": 5, "totalTokenCount": 10},
        }
        a = GeminiNativeAdapter(api_key="k", client=_client(lambda r: httpx.Response(200, json=payload)))
        req = LLMRequest(
            model="gemini-1.5-pro",
            messages=[LLMMessage(role="user", content="clima?")],
            tools=[LLMToolDefinition(name="get_weather", parameters={"type": "object"})],
        )
        resp = a.complete(req)
        assert resp.finish_reason == "tool_calls"  # TOOL_USE -> tool_calls
        assert resp.tool_calls[0].name == "get_weather"
        assert resp.tool_calls[0].arguments == {"city": "Bogota"}

    def test_tools_function_declarations(self):
        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["body"] = json.loads(request.content)
            return _gemini_ok()

        a = GeminiNativeAdapter(api_key="k", client=_client(handler))
        req = LLMRequest(
            model="gemini-1.5-pro",
            messages=[LLMMessage(role="user", content="x")],
            tools=[LLMToolDefinition(name="f", parameters={"type": "object"})],
        )
        a.complete(req)
        decl = captured["body"]["tools"][0]["functionDeclarations"][0]
        assert decl["name"] == "f"
        assert decl["parameters"] == {"type": "object"}

    def test_auth_error(self):
        a = GeminiNativeAdapter(api_key="k", client=_client(lambda r: httpx.Response(401, json={})
))
        with pytest.raises(LLMProviderError) as e:
            a.complete(_req())
        assert e.value.error_class == "AUTH_ERROR"

    def test_error_200_with_error_key(self):
        # Gemini a veces devuelve 200 + {"error": {...}}.
        a = GeminiNativeAdapter(
            api_key="k",
            client=_client(lambda r: httpx.Response(200, json={"error": {"code": 429, "message": "rl"}})),
        )
        with pytest.raises(LLMProviderError) as e:
            a.complete(_req())
        assert e.value.error_class == "RATE_LIMITED"

    def test_capabilities(self):
        a = GeminiNativeAdapter(api_key="k")
        caps = a.capabilities()
        assert caps.text and caps.tools and caps.vision and caps.streaming
