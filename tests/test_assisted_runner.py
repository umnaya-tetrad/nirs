import json
from pathlib import Path

from nirs_cas.assisted_runner import run_assisted_oracle


ROOT = Path(__file__).resolve().parents[1]


def _contract(identifier: str) -> dict:
    return {
        "schema_version": "1.0",
        "id": identifier,
        "task": {
            "visibility": "visible",
            "raw_latex": "\\text{Solve }x=2",
            "givens": [{"given_id": "g1", "latex": "x=2"}],
            "goal": {"type": "solve", "target_latex": "x"},
        },
        "steps": [
            {"step_id": "s1", "latex": "x=2", "role": "initial", "derives_from": [], "uses_givens": ["g1"], "branch": "main", "exactness": "exact"},
            {"step_id": "s2", "latex": "x=2", "role": "answer", "derives_from": ["s1"], "uses_givens": ["g1"], "branch": "main", "exactness": "exact"},
        ],
        "meta": {"run_id": "test", "approach": "llm_assisted_extraction", "stage": "extract_context", "model": "test", "prompt_version": "test", "duration_ms": 0, "created_at": "2026-01-01T00:00:00Z"},
    }


def test_assisted_oracle_keeps_task_aware_result(tmp_path: Path):
    source = tmp_path / "artifact.json"
    source.write_text(json.dumps({"status": "ok", "case_id": "case-1", "contract": _contract("case-1")}), encoding="utf-8")
    report = run_assisted_oracle([source], tmp_path / "out", ROOT, timeout=None, split_name="test")
    prediction = json.loads((tmp_path / "out" / "predictions.json").read_text(encoding="utf-8"))[0]
    assert report["pipeline"] == "llm_assisted_extraction_plus_math_core"
    assert prediction["verdict"] == "correct"
    assert prediction["problem"]["task_spec"]["task"]["givens"][0]["raw_latex"] == "x=2"
    assert prediction["problem"]["context_check"]["status"] == "valid"


def test_assisted_oracle_preserves_successes_when_one_vlm_artifact_failed(tmp_path: Path):
    good = tmp_path / "good.json"
    bad = tmp_path / "bad.json"
    good.write_text(json.dumps({"status": "ok", "case_id": "case-1", "contract": _contract("case-1")}), encoding="utf-8")
    bad.write_text(json.dumps({"status": "error", "case_id": "case-2", "error_type": "PolzaInvalidResponseError", "error": "bad JSON"}), encoding="utf-8")

    report = run_assisted_oracle([good, bad], tmp_path / "out", ROOT, timeout=None, split_name="test")

    predictions = json.loads((tmp_path / "out" / "predictions.json").read_text(encoding="utf-8"))
    failed = json.loads((tmp_path / "out" / "failed_artifacts.json").read_text(encoding="utf-8"))
    assert [item["id"] for item in predictions] == ["case-1"]
    assert failed == [{"id": "case-2", "status": "api_failed", "source": bad.as_posix(),
                       "error_type": "PolzaInvalidResponseError", "error": "bad JSON"}]
    assert report["input_failure_count"] == 1
