from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx

from .client import ModelResponse, PolzaInvalidResponseError
from .config import Settings
from .prompts import GIGACHAT_MODEL, load_prompt


_MINCIFRY_CA_URL = "https://gu-st.ru/content/lending/russian_trusted_root_ca_pem.crt"
_MINCIFRY_CA_SHA256 = "936a43fea6e8e525bcc0f81acd9c3d21b4fc4b9b68acea7906d698005afc6504"
# Official direct-API synchronous list price, VAT included, checked 2026-10-07.
# This is an experiment estimate: a physical-person Freemium quota can make billing zero.
GIGACHAT_2_PRO_RUB_PER_1K_TOKENS = 0.5


class GigaChatUnavailableError(RuntimeError):
    """No inference request was completed: configuration, network, or OAuth failed."""


class GigaChatProviderError(RuntimeError):
    def __init__(self, operation: str, status_code: int, error_code: str | None = None) -> None:
        suffix = f" ({error_code})" if error_code else ""
        super().__init__(f"GigaChat {operation} returned HTTP {status_code}{suffix}")
        self.operation = operation
        self.status_code = status_code
        self.error_code = error_code


@dataclass
class GigaChatDirectClient:
    """Direct GigaChat vision client: OAuth -> upload -> one chat completion -> cleanup."""

    settings: Settings
    transport: httpx.BaseTransport | None = None
    model: str = GIGACHAT_MODEL
    timeout: httpx.Timeout | None = None
    max_completion_tokens: int = 2000

    def __post_init__(self) -> None:
        if self.timeout is None:
            self.timeout = httpx.Timeout(self.settings.timeout_seconds, connect=self.settings.connect_timeout_seconds)

    def analyze(
        self, image_bytes: bytes, mime_type: str, mode: str, prompt_version: str | None = None
    ) -> ModelResponse:
        if not self.settings.gigachat_authorization_key:
            raise GigaChatUnavailableError(
                "GIGACHAT_AUTHORIZATION_KEY is not configured. Copy .env.example to .env first."
            )
        if not image_bytes:
            raise GigaChatUnavailableError("Refusing to send an empty image.")
        prompt = load_prompt(mode, "gigachat", prompt_version)
        # trust_env=False deliberately bypasses HTTP(S)_PROXY variables.  A custom CA
        # bundle is opt-in and keeps certificate validation enabled for the Минцифры chain.
        verify: str | bool = self.settings.gigachat_ca_bundle or (
            True if self.transport is not None else _ensure_mincifry_ca_bundle()
        )
        with httpx.Client(timeout=self.timeout, transport=self.transport, trust_env=False, verify=verify) as client:
            access_token = self._access_token(client)
            file_id = self._upload_image(client, access_token, image_bytes, mime_type)
            try:
                return self._completion(
                    client, access_token, file_id, prompt.system, prompt.user, prompt.schema_version, mode
                )
            finally:
                self._delete_file(client, access_token, file_id)

    def _access_token(self, client: httpx.Client) -> str:
        try:
            response = client.post(
                self.settings.gigachat_oauth_url,
                headers={"Authorization": f"Basic {self.settings.gigachat_authorization_key}", "RqUID": str(uuid4())},
                data={"scope": self.settings.gigachat_scope},
            )
            response.raise_for_status()
            payload = response.json()
            token = payload.get("access_token") if isinstance(payload, dict) else None
            if not isinstance(token, str) or not token:
                raise ValueError("access_token is missing")
            return token
        except httpx.HTTPStatusError as error:
            raise GigaChatProviderError("OAuth", error.response.status_code, _safe_error_code(error.response)) from error
        except httpx.HTTPError as error:
            raise GigaChatUnavailableError("GigaChat OAuth endpoint is unavailable.") from error
        except ValueError as error:
            raise GigaChatUnavailableError("GigaChat OAuth response has no usable access_token.") from error

    def _upload_image(self, client: httpx.Client, token: str, image_bytes: bytes, mime_type: str) -> str:
        try:
            response = client.post(
                self.settings.gigachat_files_url,
                headers=self._bearer_headers(token),
                data={"purpose": "general"},
                files={"file": ("solution-image", image_bytes, mime_type)},
            )
            response.raise_for_status()
            payload = response.json()
            file_id = payload.get("id") if isinstance(payload, dict) else None
            if not isinstance(file_id, str) or not file_id:
                raise ValueError("file id is missing")
            return file_id
        except httpx.HTTPStatusError as error:
            raise GigaChatProviderError("file upload", error.response.status_code, _safe_error_code(error.response)) from error
        except httpx.HTTPError as error:
            raise GigaChatUnavailableError("GigaChat file endpoint is unavailable.") from error
        except ValueError as error:
            raise GigaChatUnavailableError("GigaChat file upload response has no usable id.") from error

    def _completion(
        self,
        client: httpx.Client,
        token: str,
        file_id: str,
        system_prompt: str,
        user_prompt: str,
        schema_version: str,
        mode: str,
    ) -> ModelResponse:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt, "attachments": [file_id]},
            ],
            "response_format": _response_format(mode, schema_version),
            "temperature": 0,
            "max_tokens": self.max_completion_tokens,
        }
        try:
            response = client.post(self.settings.gigachat_chat_url, headers=self._bearer_headers(token), json=payload)
            response.raise_for_status()
            provider_payload = response.json()
        except httpx.HTTPStatusError as error:
            raise GigaChatProviderError("chat completion", error.response.status_code, _safe_error_code(error.response)) from error
        except httpx.HTTPError as error:
            raise GigaChatUnavailableError("GigaChat chat endpoint is unavailable.") from error
        except ValueError as error:
            raise PolzaInvalidResponseError("GigaChat returned a non-JSON HTTP response.") from error
        try:
            raw_content = provider_payload["choices"][0]["message"]["content"]
            if not isinstance(raw_content, str):
                raise TypeError("content is not a string")
            parsed = json.loads(raw_content)
            if not isinstance(parsed, dict):
                raise TypeError("content is not a JSON object")
            if parsed.get("schema_version") != schema_version:
                raise ValueError("wrong prompt schema_version")
        except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise PolzaInvalidResponseError("GigaChat model response is not the requested JSON object.", locals().get("raw_content")) from error
        return ModelResponse(parsed, raw_content, _provider_model(provider_payload), _safe_usage(provider_payload))

    def _delete_file(self, client: httpx.Client, token: str, file_id: str) -> None:
        try:
            client.post(f"{self.settings.gigachat_files_url}/{file_id}/delete", headers=self._bearer_headers(token)).raise_for_status()
        except httpx.HTTPError:
            # The artifact has already been saved or an inference error is being raised. Cleanup must not hide it.
            return

    @staticmethod
    def _bearer_headers(token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {token}", "User-Agent": "nirs-vlm-experiment/1.0"}


def _provider_model(payload: dict[str, Any]) -> str | None:
    value = payload.get("model")
    return value if isinstance(value, str) and value else None


def _safe_usage(payload: dict[str, Any]) -> dict[str, int | float]:
    usage = payload.get("usage")
    if not isinstance(usage, dict):
        return {}
    result = {
        key: value for key in ("prompt_tokens", "completion_tokens", "total_tokens")
        if isinstance((value := usage.get(key)), (int, float)) and not isinstance(value, bool)
    }
    total_tokens = result.get("total_tokens")
    if isinstance(total_tokens, (int, float)):
        result["estimated_cost_rub"] = estimate_gigachat_2_pro_cost_rub(int(total_tokens))
        result["price_rub_per_1k_tokens"] = GIGACHAT_2_PRO_RUB_PER_1K_TOKENS
    return result


def estimate_gigachat_2_pro_cost_rub(total_tokens: int) -> float:
    if total_tokens < 0:
        raise ValueError("total_tokens cannot be negative")
    return round(total_tokens * GIGACHAT_2_PRO_RUB_PER_1K_TOKENS / 1000, 6)


def _safe_error_code(response: httpx.Response) -> str | None:
    try:
        payload = response.json()
    except ValueError:
        return None
    error = payload.get("error") if isinstance(payload, dict) else None
    if not isinstance(error, dict):
        return None
    value = error.get("code") or error.get("type")
    return value if isinstance(value, str) and len(value) <= 100 else None


def _ensure_mincifry_ca_bundle() -> str:
    """Install the official root PEM once, pinning the expected file hash.

    The first download cannot use that root certificate yet. Its bytes are therefore
    verified against the pinned SHA-256 before they ever become trusted by httpx.
    """
    path = Path(__file__).resolve().parents[1] / ".nirs-certs" / "russian_trusted_root_ca_pem.crt"
    if path.is_file() and _sha256(path.read_bytes()) == _MINCIFRY_CA_SHA256:
        return str(path)
    try:
        with httpx.Client(timeout=20.0, trust_env=False, verify=False, follow_redirects=True) as client:
            response = client.get(_MINCIFRY_CA_URL)
            response.raise_for_status()
            contents = response.content
    except httpx.HTTPError as error:
        raise GigaChatUnavailableError(
            "Cannot download the GigaChat Минцифры root certificate. Set GIGACHAT_CA_BUNDLE manually."
        ) from error
    if _sha256(contents) != _MINCIFRY_CA_SHA256:
        raise GigaChatUnavailableError(
            "Downloaded GigaChat certificate did not match the pinned SHA-256. Set GIGACHAT_CA_BUNDLE manually."
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(".tmp")
    temporary_path.write_bytes(contents)
    temporary_path.replace(path)
    return str(path)


def _sha256(contents: bytes) -> str:
    return hashlib.sha256(contents).hexdigest()


def _response_format(mode: str, prompt_version: str) -> dict[str, Any]:
    """Small provider schema: the repository schemas remain the final authority."""
    step = {
        "type": "object",
        "properties": {
            "step_id": {"type": "string"},
            "latex": {"type": "string"},
            "kind": {"type": "string"},
        },
        "required": ["step_id", "latex"],
        "additionalProperties": False,
    }
    if mode == "e2e":
        schema = {
            "type": "object",
            "properties": {
                "schema_version": {"type": "string", "enum": [prompt_version]},
                "steps": {"type": "array", "minItems": 1, "items": step},
                "has_error": {"type": "boolean"},
                "first_error_step": {"type": ["string", "null"]},
            },
            "required": ["schema_version", "steps", "has_error", "first_error_step"],
            "additionalProperties": False,
        }
    elif mode == "extraction":
        transcription_step = {
            "type": "object",
            "properties": {"latex": {"type": "string"}},
            "required": ["latex"],
            "additionalProperties": False,
        }
        schema = {
            "type": "object",
            "properties": {
                "schema_version": {"type": "string", "enum": [prompt_version]},
                "steps": {"type": "array", "minItems": 1, "items": transcription_step},
                "ambiguous_step_ids": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["schema_version", "steps", "ambiguous_step_ids"],
            "additionalProperties": False,
        }
    elif mode == "assisted_extraction":
        assisted_step = {
            "type": "object",
            "properties": {
                "step_id": {"type": "string"}, "latex": {"type": "string"},
                "role": {"enum": ["initial", "transformation", "substitution", "definition", "answer", "independent"]},
                "derives_from": {"type": "array", "items": {"type": "string"}},
                "uses_givens": {"type": "array", "items": {"type": "string"}},
                "branch": {"type": "string"}, "exactness": {"enum": ["exact", "approximate", "unknown"]},
            },
            "required": ["step_id", "latex", "role", "derives_from", "branch", "exactness"],
            "additionalProperties": False,
        }
        task = {
            "type": "object",
            "properties": {
                "visibility": {"enum": ["visible", "not_visible"]}, "raw_latex": {"type": "string"},
                "givens": {"type": "array", "items": {"type": "object", "properties": {"given_id": {"type": "string"}, "latex": {"type": "string"}}, "required": ["given_id", "latex"], "additionalProperties": False}},
                "goal": {"type": "object", "properties": {"type": {"enum": ["solve", "simplify", "evaluate", "prove", "compute_function", "unknown"]}, "target_latex": {"type": "string"}}, "required": ["type"], "additionalProperties": False},
                "constraints": {"type": "array", "items": {"type": "string"}},
            }, "required": ["visibility"], "additionalProperties": False,
        }
        schema = {
            "type": "object", "properties": {
                "schema_version": {"type": "string", "enum": [prompt_version]}, "task": task,
                "steps": {"type": "array", "minItems": 1, "items": assisted_step},
            }, "required": ["schema_version", "task", "steps"], "additionalProperties": False,
        }
    else:
        raise ValueError(f"Unknown mode: {mode}")
    return {"type": "json_schema", "schema": schema, "strict": True}
