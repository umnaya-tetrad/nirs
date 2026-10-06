import base64
import json

import httpx
import pytest

from nirs_llm.client import GeminiPolzaClient, PolzaInvalidResponseError, PolzaProviderError
from nirs_llm.config import Settings


def response(content: dict) -> httpx.Response:
    return httpx.Response(200, json={"model": "google/gemini-3.7-flash", "usage": {"prompt_tokens": 10, "completion_tokens": 20}, "choices": [{"message": {"content": json.dumps(content)}}]})


def test_e2e_request_serializes_image_and_fixed_options() -> None:
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return response({"schema_version": "e2e_gemini_v1", "steps": [{"step_id": "s1", "latex": "x=1"}], "has_error": False, "first_error_step": None})

    client = GeminiPolzaClient(Settings("test-key"), transport=httpx.MockTransport(handler))
    result = client.analyze(b"image-bytes", "image/png", "e2e")

    assert result.content["has_error"] is False
    assert captured["model"] == "google/gemini-3.7-flash"
    assert captured["response_format"] == {"type": "json_object"}
    assert captured["temperature"] == 0
    assert "metadata" not in captured
    image_url = captured["messages"][1]["content"][1]["image_url"]["url"]
    assert image_url == f"data:image/png;base64,{base64.b64encode(b'image-bytes').decode()}"


def test_rejects_non_json_model_content() -> None:
    client = GeminiPolzaClient(Settings("test-key"), transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"choices": [{"message": {"content": "not json"}}]})))
    with pytest.raises(PolzaInvalidResponseError):
        client.analyze(b"x", "image/png", "e2e")


def test_exposes_safe_provider_error() -> None:
    client = GeminiPolzaClient(Settings("test-key"), transport=httpx.MockTransport(lambda _: httpx.Response(429, json={"error": {"code": "rate_limit"}})))
    with pytest.raises(PolzaProviderError) as raised:
        client.analyze(b"x", "image/png", "e2e")
    assert raised.value.status_code == 429
    assert raised.value.error_code == "rate_limit"

