from __future__ import annotations

from typing import Protocol


class VisionProvider(Protocol):
    def analyze(self, image_bytes: bytes, mime_type: str, mode: str): ...


class GigaChatAdapter:
    """Contract-compatible placeholder; model selection and credentials are intentionally deferred."""

    def analyze(self, image_bytes: bytes, mime_type: str, mode: str):
        raise NotImplementedError("GigaChat is intentionally deferred; configure its model in a later experiment step.")

