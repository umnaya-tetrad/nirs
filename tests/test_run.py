import json
from pathlib import Path

from nirs_llm.client import ModelResponse
from nirs_llm import run as runner


def test_mock_smoke_run_writes_raw_response_and_validated_contract(tmp_path: Path, monkeypatch) -> None:
    image = tmp_path / "solution.png"
    image.write_bytes(b"not-a-real-image-for-mock")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"cases": [{"id": "smoke-1", "image": "solution.png"}]}), encoding="utf-8")

    class FakeClient:
        model = "google/gemini-3.7-flash"

        def __init__(self, _settings):
            pass

        def analyze(self, _image: bytes, _mime: str, _mode: str) -> ModelResponse:
            projection = {"schema_version": "e2e_gemini_v1", "steps": [{"step_id": "s1", "latex": "x=1"}], "has_error": False, "first_error_step": None}
            return ModelResponse(projection, json.dumps(projection), self.model, {"prompt_tokens": 3})

    monkeypatch.setattr(runner, "GeminiPolzaClient", FakeClient)
    paths = runner.run("e2e", manifest, tmp_path / "out", Path(__file__).resolve().parents[1])

    artifact = json.loads(paths[0].read_text(encoding="utf-8"))
    assert artifact["raw_response"]
    assert artifact["contract"]["id"] == "smoke-1"
    assert artifact["contract"]["verdict"] == "correct"
