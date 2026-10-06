import json
from pathlib import Path

from nirs_llm.client import ModelResponse
from nirs_llm.client import PolzaInvalidResponseError
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


def test_accepts_llm_json_test_manifest_format(tmp_path: Path, monkeypatch) -> None:
    image = tmp_path / "solution.jpg"
    image.write_bytes(b"mock")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps([{"case_id": "hf-1", "filename": "solution.jpg"}]), encoding="utf-8")

    class FakeClient:
        model = "google/gemini-3.7-flash"
        def __init__(self, _settings): pass
        def analyze(self, _image, _mime, _mode):
            return ModelResponse({"schema_version": "e2e_gemini_v1", "steps": [{"step_id": "s1", "latex": "x=1"}], "has_error": False, "first_error_step": None}, "{}", self.model, {})

    monkeypatch.setattr(runner, "GeminiPolzaClient", FakeClient)
    assert runner.run("e2e", manifest, tmp_path / "out", Path(__file__).resolve().parents[1])


def test_smoke_run_records_invalid_model_response_and_continues(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "first.jpg").write_bytes(b"first")
    (tmp_path / "second.jpg").write_bytes(b"second")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps([{"case_id": "first", "filename": "first.jpg"}, {"case_id": "second", "filename": "second.jpg"}]), encoding="utf-8")

    class FakeClient:
        model = "google/gemini-3.7-flash"
        def __init__(self, _settings): self.calls = 0
        def analyze(self, *_args):
            self.calls += 1
            if self.calls == 1: raise PolzaInvalidResponseError("bad JSON", "not json")
            return ModelResponse({"schema_version": "e2e_gemini_v1", "steps": [{"step_id": "s1", "latex": "x=1"}], "has_error": False, "first_error_step": None}, "{}", self.model, {})

    monkeypatch.setattr(runner, "GeminiPolzaClient", FakeClient)
    paths = runner.run("e2e", manifest, tmp_path / "out", Path(__file__).resolve().parents[1])
    errors = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
    assert [item["status"] for item in errors] == ["error", "ok"]
    assert errors[0]["raw_response"] == "not json"
