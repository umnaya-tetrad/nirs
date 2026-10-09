from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from typing import Any

import httpx

from .config import Settings
from .prompts import GEMINI_MODEL, load_prompt


class PolzaUnavailableError(RuntimeError):
    pass


class PolzaProviderError(RuntimeError):
    def __init__(self, status_code: int, error_code: str | None = None, retry_after_seconds: float | None = None) -> None:
        super().__init__(f"Polza AI returned HTTP {status_code}")
        self.status_code = status_code
        self.error_code = error_code
        self.retry_after_seconds = retry_after_seconds


class PolzaInvalidResponseError(RuntimeError):
    def __init__(self, message: str, raw_content: str | None = None) -> None:
        super().__init__(message)
        self.raw_content = raw_content


@dataclass(frozen=True)
class ModelResponse:
    content: dict[str, Any]
    raw_content: str
    provider_model: str | None
    usage: dict[str, int | float]


class GeminiPolzaClient:
    """Minimal OpenAI-compatible Polza client for the fixed Gemini baseline."""

    def __init__(
        self,
        settings: Settings,
        *,
        transport: httpx.BaseTransport | None = None,
        model: str = GEMINI_MODEL,
        timeout: httpx.Timeout | None = None,
    ) -> None:
        self.settings = settings
        self.transport = transport
        self.model = model
        self.timeout = timeout or httpx.Timeout(settings.timeout_seconds, connect=settings.connect_timeout_seconds)

    def analyze(
        self, image_bytes: bytes, mime_type: str, mode: str, prompt_version: str | None = None
    ) -> ModelResponse:
        if not self.settings.polza_api_key:
            raise PolzaUnavailableError("POLZA_API_KEY is not configured. Copy .env.example to .env first.")
        prompt = load_prompt(mode, "gemini", prompt_version)
        image_b64 = base64.b64encode(image_bytes).decode("ascii")
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": prompt.system},
                {"role": "user", "content": [
                    {"type": "text", "text": prompt.user},
                    {"type": "image_url", "image_url": {
                        "url": f"data:{mime_type};base64,{image_b64}", "detail": "high"
                    }},
                ]},
            ],
            # Gemini 3.7 Flash was previously smoke-tested through Polza in json_object mode.
            "response_format": {"type": "json_object"},
            "temperature": 0,
            "max_completion_tokens": 4000,
        }
        try:
            with httpx.Client(timeout=self.timeout, transport=self.transport, trust_env=False) as client:
                response = client.post(
                    self.settings.chat_url,
                    headers={"Authorization": f"Bearer {self.settings.polza_api_key}"},
                    json=payload,
                )
                response.raise_for_status()
                provider_payload = response.json()
        except httpx.HTTPStatusError as error:
            raise PolzaProviderError(error.response.status_code, _safe_error_code(error.response), _retry_after(error.response)) from error
        except httpx.HTTPError as error:
            raise PolzaUnavailableError("Polza AI is unavailable.") from error
        except ValueError as error:
            raise PolzaInvalidResponseError("Polza AI returned a non-JSON HTTP response.") from error

        try:
            raw_content = provider_payload["choices"][0]["message"]["content"]
            if not isinstance(raw_content, str):
                raise TypeError("content is not a string")
            parsed = json.loads(raw_content)
            if not isinstance(parsed, dict):
                raise TypeError("content is not a JSON object")
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as error:
            raise PolzaInvalidResponseError("Model response is not a JSON object.", locals().get("raw_content")) from error
        return ModelResponse(parsed, raw_content, _provider_model(provider_payload), _safe_usage(provider_payload))


def _provider_model(payload: dict[str, Any]) -> str | None:
    value = payload.get("model")
    return value if isinstance(value, str) and value else None


def _safe_usage(payload: dict[str, Any]) -> dict[str, int | float]:
    usage = payload.get("usage")
    if not isinstance(usage, dict):
        return {}
    return {
        key: value for key in ("prompt_tokens", "completion_tokens", "total_tokens", "cost", "cost_rub")
        if isinstance((value := usage.get(key)), (int, float)) and not isinstance(value, bool)
    }


def _safe_error_code(response: httpx.Response) -> str | None:
    try:
        payload = response.json()
    except ValueError:
        return None
    error = payload.get("error") if isinstance(payload, dict) else None
    if not isinstance(error, dict):
        return None
    for key in ("code", "type"):
        value = error.get(key)
        if isinstance(value, str) and len(value) <= 100:
            return value
    return None


def _retry_after(response: httpx.Response) -> float | None:
    """Return a bounded Retry-After delay when the provider supplies one."""
    raw = response.headers.get("Retry-After")
    try:
        value = float(raw) if raw is not None else None
    except ValueError:
        return None
    return value if value is not None and 0 <= value <= 300 else None
