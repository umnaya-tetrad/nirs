from __future__ import annotations

from typing import Protocol

from .gigachat import GigaChatDirectClient


class VisionProvider(Protocol):
    def analyze(self, image_bytes: bytes, mime_type: str, mode: str, prompt_version: str | None = None): ...


GigaChatAdapter = GigaChatDirectClient
