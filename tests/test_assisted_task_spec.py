import json
from pathlib import Path

from nirs_cas import analyze_assisted_contract
from nirs_cas.task_spec import compile_task_spec
from nirs_llm.contracts import validate_contract


ROOT = Path(__file__).resolve().parents[1]


def _items(name):
    return json.loads((ROOT / "dataset" / "artifacts" / name).read_text(encoding="utf-8"))["items"]


def test_frozen_assisted_artifacts_are_unique_and_label_free():
    items = _items("gemini_assisted_fermat_dev_20.json")
    assert len(items) == 20
    assert len({item["id"] for item in items}) == 20
    forbidden = {"orig_q", "orig_a", "pert_a", "pert_reasoning", "has_error", "verdict"}
    for item in items:
        assert item["prompt_sha256"]
        assert item["contract_sha256"]
        assert not (forbidden & set(item["contract"]))
        validate_contract(item["contract"], "llm_assisted_extraction", ROOT)


def test_task_spec_compiles_every_frozen_engineering_case():
    for item in _items("gemini_assisted_mixed_20.json") + _items("gemini_assisted_fermat_dev_20.json"):
        spec = compile_task_spec(item["contract"])
        assert spec["id"] == item["id"]
        assert spec["compilation"]["task_class"] != "unknown"
        assert all("orig_" not in str(value) for value in spec.values())


def test_assisted_analysis_preserves_exact_local_error():
    contract = {
        "schema_version": "1.0", "id": "case", "task": {"visibility": "visible", "raw_latex": "x=2", "givens": [{"given_id": "g1", "latex": "x=2"}], "goal": {"type": "solve", "target_latex": "x"}},
        "steps": [
            {"step_id": "s1", "latex": "x=2", "role": "initial", "derives_from": [], "branch": "main", "exactness": "exact"},
            {"step_id": "s2", "latex": "x=3", "role": "answer", "derives_from": ["s1"], "branch": "main", "exactness": "exact"},
        ], "meta": {"run_id": "test", "approach": "llm_assisted_extraction", "stage": "extract_context", "model": "test", "prompt_version": "v2", "duration_ms": 0, "created_at": "2026-01-01T00:00:00Z"},
    }
    result = analyze_assisted_contract(contract, ROOT, timeout=None)
    assert result["verdict"] == "incorrect"
    assert result["first_error_step"] == "s2"
    assert result["pipeline"]["approach"] == "llm_assisted_extraction_plus_math_core"


def test_unsupported_context_does_not_downgrade_local_verdict():
    contract = {
        "schema_version": "1.0", "id": "case", "task": {"visibility": "visible", "raw_latex": "\\log_2 x > 1", "givens": [{"given_id": "g1", "latex": "\\log_2 x > 1"}], "goal": {"type": "solve", "target_latex": "x"}},
        "steps": [
            {"step_id": "s1", "latex": "2+2=4", "role": "initial", "derives_from": [], "branch": "main", "exactness": "exact"},
            {"step_id": "s2", "latex": "4=4", "role": "answer", "derives_from": ["s1"], "branch": "main", "exactness": "exact"},
        ], "meta": {"run_id": "test", "approach": "llm_assisted_extraction", "stage": "extract_context", "model": "test", "prompt_version": "v2", "duration_ms": 0, "created_at": "2026-01-01T00:00:00Z"},
    }
    result = analyze_assisted_contract(contract, ROOT, timeout=None)
    assert result["verdict"] == "correct"
    assert result["problem"]["context_check"]["status"] == "unsupported"
