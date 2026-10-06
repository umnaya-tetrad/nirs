from pathlib import Path

import pytest

from nirs_llm.contracts import ContractError, build_math_core_input, build_solution_analysis, validate_contract


ROOT = Path(__file__).resolve().parents[1]


def test_lifts_minimal_e2e_projection_to_existing_contract() -> None:
    contract = build_solution_analysis(
        case_id="dev-1",
        projection={"schema_version": "e2e_gemini_v1", "steps": [{"step_id": "s1", "latex": "2x=4"}, {"step_id": "s2", "latex": "x=3"}], "has_error": True, "first_error_step": "s2"},
        model="google/gemini-3.7-flash", prompt_version="e2e_gemini_v1", duration_ms=100, usage={"prompt_tokens": 12, "completion_tokens": 8},
    )
    validate_contract(contract, "solution_analysis", ROOT)
    assert contract["findings"] == []
    assert contract["first_error_step"] == "s2"
    assert contract["last_correct_step"] == "s1"


def test_lifts_extraction_without_normalized_latex() -> None:
    projection = {
        "schema_version": "extraction_gemini_v1",
        "problem": {"kind": "linear_equation", "equations": [{"id": "e1", "relation": "eq", "latex": "2x=4"}], "goal": {"type": "solve"}, "source": "transcribed"},
        "steps": [{"step_id": "s1", "kind": "initial", "latex": "2x=4"}, {"step_id": "s2", "kind": "step", "latex": "x=2"}],
        "ambiguous_step_ids": ["s2"], "notes": ["Знак на s2 нечёткий."],
    }
    contract = build_math_core_input(case_id="dev-1", projection=projection, model="google/gemini-3.7-flash", prompt_version="extraction_gemini_v1", duration_ms=100, usage={})
    validate_contract(contract, "math_core_input", ROOT)
    assert "normalized_latex" not in contract["steps"][0]
    assert contract["reading"]["ambiguous_step_ids"] == ["s2"]


def test_rejects_error_pointer_not_in_steps() -> None:
    with pytest.raises(ContractError):
        build_solution_analysis(case_id="dev-1", projection={"schema_version": "e2e_gemini_v1", "steps": [{"step_id": "s1", "latex": "x=1"}], "has_error": True, "first_error_step": "s2"}, model="m", prompt_version="p", duration_ms=1, usage={})

