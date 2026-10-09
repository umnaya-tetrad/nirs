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
    polza_max_completion_tokens: int = 4000
    gigachat_authorization_key: str = ""
    gigachat_scope: str = "GIGACHAT_API_PERS"
    gigachat_oauth_url: str = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
    gigachat_base_url: str = "https://api.giga.chat/v1"
    gigachat_ca_bundle: str = ""

    @property
    def chat_url(self) -> str:
        return f"{self.polza_base_url.rstrip('/')}/chat/completions"

    @property
    def gigachat_files_url(self) -> str:
        return f"{self.gigachat_base_url.rstrip('/')}/files"

    @property
    def gigachat_chat_url(self) -> str:
        return f"{self.gigachat_base_url.rstrip('/')}/chat/completions"

    @classmethod
    def from_environment(cls, dotenv_path: Path | None = None) -> "Settings":
        load_dotenv(dotenv_path or Path(".env"))
        return cls(
            polza_api_key=os.getenv("POLZA_API_KEY", ""),
            polza_base_url=os.getenv("POLZA_BASE_URL", cls.polza_base_url),
            timeout_seconds=float(os.getenv("POLZA_TIMEOUT_SECONDS", "75")),
            connect_timeout_seconds=float(os.getenv("POLZA_CONNECT_TIMEOUT_SECONDS", "10")),
            polza_max_completion_tokens=int(os.getenv("POLZA_MAX_COMPLETION_TOKENS", "4000")),
            gigachat_authorization_key=os.getenv("GIGACHAT_AUTHORIZATION_KEY", ""),
            gigachat_scope=os.getenv("GIGACHAT_SCOPE", "GIGACHAT_API_PERS"),
            gigachat_oauth_url=os.getenv("GIGACHAT_OAUTH_URL", cls.gigachat_oauth_url),
            gigachat_base_url=os.getenv("GIGACHAT_BASE_URL", cls.gigachat_base_url),
            gigachat_ca_bundle=os.getenv("GIGACHAT_CA_BUNDLE", ""),
        )

