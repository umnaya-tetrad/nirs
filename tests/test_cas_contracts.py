import json
from pathlib import Path

from nirs_cas import analyze_contract
from nirs_llm.contracts import build_math_core_input, validate_contract


ROOT = Path(__file__).resolve().parents[1]


def _input(*, steps, ambiguous_step_ids=None):
    return build_math_core_input(
        case_id="case-1",
        projection={
            "schema_version": "extraction_gemini_v1",
            "problem": {"kind": "linear_equation", "equations": [{"id": "e1", "relation": "eq", "latex": "2x+3=7"}], "goal": {"type": "solve"}, "source": "transcribed"},
            "steps": steps,
            "ambiguous_step_ids": ambiguous_step_ids or [],
            "notes": [],
        },
        model="gemini", prompt_version="extraction_gemini_v1", duration_ms=1, usage={},
    )


def test_cas_keeps_canonical_step_ids_and_returns_solution_analysis():
    output = analyze_contract(_input(steps=[{"step_id": "s1", "latex": "2x+3=7"}, {"step_id": "s2", "latex": "x=2"}]), ROOT)
    validate_contract(output, "solution_analysis", ROOT)
    assert output["verdict"] == "correct"
    assert [step["step_id"] for step in output["steps"]] == ["s1", "s2"]


def test_cas_maps_a_numeric_destination_index_back_to_the_contract_step_id():
    output = analyze_contract(_input(steps=[{"step_id": "s1", "latex": "2x+3=7"}, {"step_id": "s2", "latex": "x=3"}]), ROOT)
    validate_contract(output, "solution_analysis", ROOT)
    assert output["verdict"] == "incorrect"
    assert output["first_error_step"] == "s2"
    assert output["findings"][0]["step_id"] == "s2"


def test_ambiguous_or_unsupported_inputs_abstain_instead_of_becoming_incorrect():
    output = analyze_contract(_input(steps=[{"step_id": "s1", "latex": "2x+3=7"}, {"step_id": "s2", "latex": "x=2"}], ambiguous_step_ids=["s2"]), ROOT)
    validate_contract(output, "solution_analysis", ROOT)
    assert output["verdict"] == "indeterminate"
    assert output["first_error_step"] is None


def test_all_gt_items_can_be_fed_to_the_canonical_cas_adapter():
    gt = json.loads((ROOT / "dataset" / "test_gt.json").read_text(encoding="utf-8"))
    outputs = [analyze_contract(item, ROOT) for item in gt]
    for output in outputs:
        validate_contract(output, "solution_analysis", ROOT)
    assert len(outputs) == 20
