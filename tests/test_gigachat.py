import json

import httpx
import pytest

from nirs_llm.config import Settings
from nirs_llm.gigachat import GigaChatDirectClient, GigaChatProviderError, _response_format


def _settings() -> Settings:
    return Settings(
        polza_api_key="",
        gigachat_authorization_key="authorization-key",
        gigachat_oauth_url="https://test.local/oauth",
        gigachat_base_url="https://test.local/v1",
    )


def test_vision_request_uploads_image_and_uses_fixed_json_contract() -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if request.url.path == "/oauth":
            assert request.headers["Authorization"] == "Basic authorization-key"
            assert b"scope=GIGACHAT_API_PERS" in request.content
            return httpx.Response(200, json={"access_token": "short-lived-token"})
        if request.url.path == "/v1/files" and request.method == "POST":
            assert b"image-bytes" in request.content
            assert request.headers["Authorization"] == "Bearer short-lived-token"
            return httpx.Response(200, json={"id": "file-1"})
        if request.url.path == "/v1/chat/completions":
            payload = json.loads(request.content)
            assert payload["model"] == "GigaChat-2-Pro"
            assert payload["messages"][1]["attachments"] == ["file-1"]
            assert payload["response_format"]["type"] == "json_schema"
            assert payload["response_format"]["strict"] is True
            assert payload["response_format"]["schema"]["properties"]["schema_version"]["enum"] == ["e2e_gigachat_v1"]
            assert payload["response_format"]["schema"]["additionalProperties"] is False
            assert payload["temperature"] == 0
            assert payload["max_tokens"] == 2000
            content = {"schema_version": "e2e_gigachat_v1", "steps": [{"step_id": "s1", "latex": "x=1"}], "has_error": False, "first_error_step": None}
            return httpx.Response(200, json={"model": "GigaChat-2-Pro", "usage": {"prompt_tokens": 3, "completion_tokens": 4}, "choices": [{"message": {"content": json.dumps(content)}}]})
        if request.url.path == "/v1/files/file-1/delete" and request.method == "POST":
            return httpx.Response(204)
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    client = GigaChatDirectClient(_settings(), transport=httpx.MockTransport(handler))
    result = client.analyze(b"image-bytes", "image/png", "e2e")

    assert result.content["schema_version"] == "e2e_gigachat_v1"
    assert result.usage == {"prompt_tokens": 3, "completion_tokens": 4}
    assert len(calls) == 4


def test_oauth_http_failure_stops_before_upload_or_inference() -> None:
    calls = 0

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(500, json={"error": {"code": "temporary_failure"}})

    client = GigaChatDirectClient(_settings(), transport=httpx.MockTransport(handler))
    with pytest.raises(GigaChatProviderError) as raised:
        client.analyze(b"image", "image/png", "e2e")
    assert raised.value.operation == "OAuth"
    assert raised.value.status_code == 500
    assert calls == 1


def test_extraction_schema_constrains_the_fields_required_by_math_core() -> None:
    schema = _response_format("extraction", "extraction_gigachat_v2")["schema"]
    problem = schema["properties"]["problem"]
    equation = problem["properties"]["equations"]["items"]

    assert problem["required"] == ["kind", "equations", "goal"]
    assert equation["required"] == ["id", "relation", "latex"]
    assert problem["properties"]["goal"]["required"] == ["type"]


def test_rejects_bad_model_json_after_single_completion() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(f"{request.method} {request.url.path}")
        if request.url.path == "/oauth":
            return httpx.Response(200, json={"access_token": "token"})
        if request.method == "POST" and request.url.path == "/v1/files":
            return httpx.Response(200, json={"id": "file-1"})
        if request.url.path == "/v1/chat/completions":
            return httpx.Response(200, json={"choices": [{"message": {"content": "not json"}}]})
        if request.method == "POST" and request.url.path == "/v1/files/file-1/delete":
            return httpx.Response(204)
        raise AssertionError("unexpected request")

    client = GigaChatDirectClient(_settings(), transport=httpx.MockTransport(handler))
    with pytest.raises(Exception, match="requested JSON"):
        client.analyze(b"image", "image/png", "e2e")
    assert calls == ["POST /oauth", "POST /v1/files", "POST /v1/chat/completions", "POST /v1/files/file-1/delete"]
