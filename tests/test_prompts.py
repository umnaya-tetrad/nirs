from __future__ import annotations

import pytest

from nirs_llm.prompts import load_prompt


def test_loads_versioned_prompt_with_stable_fingerprint() -> None:
    first = load_prompt("e2e", "gemini", "v1")
    second = load_prompt("e2e", "gemini", "v1")

    assert first.schema_version == "e2e_gemini_v1"
    assert "{{schema_version}}" not in first.system
    assert first.sha256 == second.sha256
    # This makes an accidental edit to the immutable v1 research artifact visible.
    assert first.sha256 == "0be3fa5de3f674ee4fcb429083d5282d5f6bef066f70baf534100d66fde8a8ad"


def test_default_resolves_current_provider_mode_version() -> None:
    prompt = load_prompt("extraction", "gigachat")
    assert prompt.version == "v3"
    assert prompt.schema_version == "extraction_gigachat_v3"
    assert load_prompt("extraction", "gemini").version == "v2"
    assert load_prompt("assisted_extraction", "gemini").schema_version == "assisted_extraction_gemini_v2"
    assert load_prompt("assisted_extraction", "gigachat").schema_version == "assisted_extraction_gigachat_v2"


def test_rejects_unsupported_prompt_version_and_combination() -> None:
    with pytest.raises(ValueError, match="Unknown prompt version"):
        load_prompt("e2e", "gemini", "v99")
    with pytest.raises(ValueError, match="Unsupported prompt combination"):
        load_prompt("unsupported", "gemini")
