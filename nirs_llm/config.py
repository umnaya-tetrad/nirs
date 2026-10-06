from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def load_dotenv(path: Path) -> None:
    """Load simple KEY=VALUE entries without adding a runtime dependency."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)


@dataclass(frozen=True)
class Settings:
    polza_api_key: str
    polza_base_url: str = "https://polza.ai/api/v1"
    timeout_seconds: float = 75.0
    connect_timeout_seconds: float = 10.0

    @property
    def chat_url(self) -> str:
        return f"{self.polza_base_url.rstrip('/')}/chat/completions"

    @classmethod
    def from_environment(cls, dotenv_path: Path | None = None) -> "Settings":
        load_dotenv(dotenv_path or Path(".env"))
        return cls(
            polza_api_key=os.getenv("POLZA_API_KEY", ""),
            polza_base_url=os.getenv("POLZA_BASE_URL", cls.polza_base_url),
            timeout_seconds=float(os.getenv("POLZA_TIMEOUT_SECONDS", "75")),
            connect_timeout_seconds=float(os.getenv("POLZA_CONNECT_TIMEOUT_SECONDS", "10")),
        )

