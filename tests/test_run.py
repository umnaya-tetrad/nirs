import json
from pathlib import Path
from threading import Barrier, get_ident

from nirs_llm.client import ModelResponse
from nirs_llm.client import PolzaInvalidResponseError, PolzaProviderError, PolzaUnavailableError
from nirs_llm import run as runner
import pytest


def test_mock_smoke_run_writes_raw_response_and_validated_contract(tmp_path: Path, monkeypatch) -> None:
    image = tmp_path / "solution.png"
    image.write_bytes(b"not-a-real-image-for-mock")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"cases": [{"id": "smoke-1", "image": "solution.png"}]}), encoding="utf-8")

    class FakeClient:
        model = "google/gemini-3.7-flash"

        def __init__(self, _settings):
            self.prompt_versions: list[str | None] = []

        def analyze(self, _image: bytes, _mime: str, _mode: str, _prompt_version: str | None = None) -> ModelResponse:
            self.prompt_versions.append(_prompt_version)
            projection = {"schema_version": "e2e_gemini_v1", "steps": [{"step_id": "s1", "latex": "x=1"}], "has_error": False, "first_error_step": None}
            return ModelResponse(projection, json.dumps(projection), self.model, {"prompt_tokens": 3})

    clients: list[FakeClient] = []
    monkeypatch.setattr(runner, "GeminiPolzaClient", lambda settings: clients.append(FakeClient(settings)) or clients[-1])
    paths = runner.run("e2e", manifest, tmp_path / "out", Path(__file__).resolve().parents[1], workers=1)

    artifact = json.loads(paths[0].read_text(encoding="utf-8"))
    assert artifact["raw_response"]
    assert artifact["contract"]["id"] == "smoke-1"
    assert artifact["contract"]["verdict"] == "correct"
    assert artifact["prompt_version"] == "v1"
    assert artifact["prompt"]["schema_version"] == "e2e_gemini_v1"
    assert len(artifact["prompt"]["sha256"]) == 64
    assert clients[0].prompt_versions == ["v1"]


def test_accepts_llm_json_test_manifest_format(tmp_path: Path, monkeypatch) -> None:
    image = tmp_path / "solution.jpg"
    image.write_bytes(b"mock")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps([{"case_id": "hf-1", "filename": "solution.jpg"}]), encoding="utf-8")

    class FakeClient:
        model = "google/gemini-3.7-flash"
        def __init__(self, _settings): pass
        def analyze(self, _image, _mime, _mode, _prompt_version=None):
            return ModelResponse({"schema_version": "e2e_gemini_v1", "steps": [{"step_id": "s1", "latex": "x=1"}], "has_error": False, "first_error_step": None}, "{}", self.model, {})

    monkeypatch.setattr(runner, "GeminiPolzaClient", FakeClient)
    assert runner.run("e2e", manifest, tmp_path / "out", Path(__file__).resolve().parents[1])


def test_retry_then_resume_never_resends_saved_success(tmp_path: Path, monkeypatch) -> None:
    image = tmp_path / "solution.jpg"
    image.write_bytes(b"mock")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"cases": [{"id": "a", "image": "solution.jpg"}]}), encoding="utf-8")
    calls = []

    class FakeClient:
        model = "google/gemini-3.7-flash"
        def __init__(self, _settings): pass
        def analyze(self, *_args):
            calls.append(1)
            if len(calls) == 1:
                raise PolzaProviderError(503, retry_after_seconds=0)
            projection = {"schema_version": "e2e_gemini_v1", "steps": [{"step_id": "s1", "latex": "x=1"}], "has_error": False, "first_error_step": None}
            return ModelResponse(projection, json.dumps(projection), self.model, {})

    monkeypatch.setattr(runner, "GeminiPolzaClient", FakeClient)
    monkeypatch.setattr(runner.time, "sleep", lambda _delay: None)
    runner.run("e2e", manifest, tmp_path / "out", Path(__file__).resolve().parents[1], run_name="resumable", max_attempts=2)
    assert len(calls) == 2
    runner.run("e2e", manifest, tmp_path / "out", Path(__file__).resolve().parents[1], run_name="resumable", resume=True)
    assert len(calls) == 2
    metadata = json.loads((tmp_path / "out" / "resumable" / "run_metadata.json").read_text(encoding="utf-8"))
    assert metadata["completion"]["successful"] == 1


def test_permanent_provider_error_is_not_retryable():
    assert runner._is_retryable(PolzaProviderError(429))
    assert runner._is_retryable(PolzaProviderError(503))
    assert not runner._is_retryable(PolzaProviderError(401))
    assert not runner._is_retryable(PolzaProviderError(400))


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
    paths = runner.run("e2e", manifest, tmp_path / "out", Path(__file__).resolve().parents[1], workers=1)
    errors = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
    assert [item["status"] for item in errors] == ["error", "ok"]
    assert errors[0]["raw_response"] == "not json"
    assert runner._worker_count("gemini", 1) == 1


def test_runner_retries_transient_network_failure_and_records_attempts(tmp_path: Path, monkeypatch) -> None:
    image = tmp_path / "solution.png"
    image.write_bytes(b"mock")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps([{"case_id": "retry-1", "filename": "solution.png"}]), encoding="utf-8")

    class FlakyClient:
        model = "google/gemini-3.7-flash"
        def __init__(self, _settings): self.calls = 0
        def analyze(self, *_args):
            self.calls += 1
            if self.calls < 3:
                raise PolzaUnavailableError("Polza AI is unavailable.")
            projection = {"schema_version": "extraction_gemini_v2", "steps": [{"latex": "x=1"}], "ambiguous_step_ids": []}
            return ModelResponse(projection, json.dumps(projection), self.model, {})

    clients: list[FlakyClient] = []
    monkeypatch.setattr(runner, "GeminiPolzaClient", lambda settings: clients.append(FlakyClient(settings)) or clients[-1])
    monkeypatch.setattr(runner.time, "sleep", lambda _delay: None)
    path = runner.run("extraction", manifest, tmp_path / "out", Path(__file__).resolve().parents[1], workers=1)[0]
    artifact = json.loads(path.read_text(encoding="utf-8"))
    assert clients[0].calls == 3
    assert artifact["status"] == "ok"
    assert artifact["attempts"] == 3
    assert len(artifact["retry_errors"]) == 2


def test_fail_fast_writes_artifact_then_raises(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "first.jpg").write_bytes(b"first")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps([{"case_id": "first", "filename": "first.jpg"}]), encoding="utf-8")

    class FailingClient:
        model = "GigaChat-2-Pro"
        def analyze(self, *_args):
            raise PolzaInvalidResponseError("bad JSON", "not json")

    monkeypatch.setattr(runner, "_client_for", lambda *_args: FailingClient())
    with pytest.raises(runner.RunFailedError):
        runner.run("e2e", manifest, tmp_path / "out", Path(__file__).resolve().parents[1], provider="gigachat", fail_fast=True)
    artifact = next((tmp_path / "out").rglob("first.json"))
    assert json.loads(artifact.read_text(encoding="utf-8"))["status"] == "error"


def test_fail_fast_does_not_submit_a_second_paid_case(tmp_path: Path, monkeypatch) -> None:
    for name in ("first.jpg", "second.jpg"):
        (tmp_path / name).write_bytes(b"image")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps([
        {"case_id": "first", "filename": "first.jpg"},
        {"case_id": "second", "filename": "second.jpg"},
    ]), encoding="utf-8")

    class FailingClient:
        model = "google/gemini-3.7-flash"
        def __init__(self): self.calls = 0
        def analyze(self, *_args):
            self.calls += 1
            raise PolzaInvalidResponseError("bad JSON", "not json")

    client = FailingClient()
    monkeypatch.setattr(runner, "_client_for", lambda *_args: client)
    with pytest.raises(runner.RunFailedError):
        runner.run("e2e", manifest, tmp_path / "out", Path(__file__).resolve().parents[1], fail_fast=True, workers=1)
    assert client.calls == 1


def test_case_selection_uses_manifest_order_and_rejects_unknown_ids(tmp_path: Path, monkeypatch) -> None:
    for name in ("first.jpg", "second.jpg"):
        (tmp_path / name).write_bytes(b"image")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps([{"case_id": "first", "filename": "first.jpg"}, {"case_id": "second", "filename": "second.jpg"}]),
        encoding="utf-8",
    )

    class FakeClient:
        model = "google/gemini-3.7-flash"
        def __init__(self, _settings): pass
        def analyze(self, _image, _mime, _mode, _prompt_version=None):
            return ModelResponse(
                {"schema_version": "e2e_gemini_v1", "steps": [{"step_id": "s1", "latex": "x=1"}], "has_error": False, "first_error_step": None},
                "{}", self.model, {},
            )

    monkeypatch.setattr(runner, "GeminiPolzaClient", FakeClient)
    paths = runner.run("e2e", manifest, tmp_path / "out", Path(__file__).resolve().parents[1], case_ids={"second"})
    assert [path.stem for path in paths] == ["second"]
    with pytest.raises(ValueError, match="absent from the manifest"):
        runner.run("e2e", manifest, tmp_path / "other", Path(__file__).resolve().parents[1], case_ids={"missing"})


def test_gemini_cases_persist_serially_in_manifest_order(tmp_path: Path, monkeypatch) -> None:
    for name in ("first.jpg", "second.jpg"):
        (tmp_path / name).write_bytes(b"image")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps([{"case_id": "first", "filename": "first.jpg"}, {"case_id": "second", "filename": "second.jpg"}]),
        encoding="utf-8",
    )
    thread_ids: list[int] = []

    class FakeClient:
        model = "google/gemini-3.7-flash"
        def __init__(self, _settings): pass
        def analyze(self, _image, _mime, _mode, _prompt_version=None):
            thread_ids.append(get_ident())
            return ModelResponse(
                {"schema_version": "e2e_gemini_v1", "steps": [{"step_id": "s1", "latex": "x=1"}], "has_error": False, "first_error_step": None},
                "{}", self.model, {},
            )

    monkeypatch.setattr(runner, "GeminiPolzaClient", FakeClient)
    paths = runner.run("e2e", manifest, tmp_path / "out", Path(__file__).resolve().parents[1], workers=2)
    assert [path.stem for path in paths] == ["first", "second"]
    assert len(set(thread_ids)) == 1


def test_gigachat_rejects_parallel_workers() -> None:
    with pytest.raises(ValueError, match="exactly one worker"):
        runner._worker_count("gigachat", 2)
