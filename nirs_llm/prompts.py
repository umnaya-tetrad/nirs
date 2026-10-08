from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path


GEMINI_MODEL = "google/gemini-3.7-flash"
GIGACHAT_MODEL = "GigaChat-2-Pro"
PROMPTS_ROOT = Path(__file__).resolve().parents[1] / "prompts"
_DEFAULT_VERSION = {
    ("gemini", "e2e"): "v1",
    ("gemini", "extraction"): "v2",
    ("gigachat", "e2e"): "v1",
    ("gigachat", "extraction"): "v3",
}


@dataclass(frozen=True)
class PromptSpec:
    provider: str
    mode: str
    version: str
    schema_version: str
    system: str
    user: str
    sha256: str

    def artifact(self) -> dict[str, str]:
        return {
            "provider": self.provider,
            "mode": self.mode,
            "version": self.version,
            "schema_version": self.schema_version,
            "system": self.system,
            "user": self.user,
            "sha256": self.sha256,
        }


def load_prompt(mode: str, provider: str = "gemini", version: str | None = None) -> PromptSpec:
    key = (provider, mode)
    if key not in _DEFAULT_VERSION:
        raise ValueError(f"Unsupported prompt combination: {provider}/{mode}")
    resolved_version = version or _DEFAULT_VERSION[key]
    directory = PROMPTS_ROOT / provider / mode / resolved_version
    system_path = directory / "system.txt"
    user_path = directory / "user.txt"
    if not system_path.is_file() or not user_path.is_file():
        raise ValueError(f"Unknown prompt version: {provider}/{mode}/{resolved_version}")
    schema_version = f"{mode}_{provider}_{resolved_version}"
    system = system_path.read_text(encoding="utf-8").replace("{{schema_version}}", schema_version).strip()
    user = user_path.read_text(encoding="utf-8").strip()
    fingerprint = sha256(f"system\0{system}\0user\0{user}".encode("utf-8")).hexdigest()
    return PromptSpec(provider, mode, resolved_version, schema_version, system, user, fingerprint)


def prompt_for(mode: str, provider: str = "gemini", version: str | None = None) -> tuple[str, str]:
    """Compatibility helper for callers that only need schema version and system text."""
    prompt = load_prompt(mode, provider, version)
    return prompt.schema_version, prompt.system
