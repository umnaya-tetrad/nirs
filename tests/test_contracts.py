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


def test_lifts_visual_extraction_without_semantic_inference() -> None:
    projection = {
        "schema_version": "extraction_gemini_v2",
        "steps": [{"latex": "2x=4"}, {"latex": "x=2"}],
        "ambiguous_step_ids": ["s2"],
    }
    contract = build_math_core_input(case_id="dev-1", projection=projection, model="google/gemini-3.7-flash", prompt_version="extraction_gemini_v2", duration_ms=100, usage={})
    validate_contract(contract, "math_core_input", ROOT)
    assert contract["schema_version"] == "2.0"
    assert "problem" not in contract
    assert contract["steps"][1]["derives_from"] == ["s1"]
    assert contract["reading"]["ambiguous_step_ids"] == ["s2"]


def test_rejects_semantic_fields_in_visual_extraction() -> None:
    with pytest.raises(ContractError, match="unsupported semantic fields"):
        build_math_core_input(
            case_id="dev-1",
            projection={
                "schema_version": "extraction_gemini_v2",
                "problem": {"kind": "linear_equation"},
                "steps": [{"latex": "2x=4"}],
                "ambiguous_step_ids": [],
            },
            model="m", prompt_version="extraction_gemini_v2", duration_ms=1, usage={},
        )


def test_rejects_vlm_supplied_step_ids() -> None:
    with pytest.raises(ContractError, match="may only contain latex"):
        build_math_core_input(
            case_id="dev-1",
            projection={
                "schema_version": "extraction_gemini_v2",
                "steps": [{"step_id": "s1", "latex": "2x=4"}],
                "ambiguous_step_ids": [],
            },
            model="m", prompt_version="extraction_gemini_v2", duration_ms=1, usage={},
        )


def test_rejects_error_pointer_not_in_steps() -> None:
    with pytest.raises(ContractError):
        build_solution_analysis(case_id="dev-1", projection={"schema_version": "e2e_gemini_v1", "steps": [{"step_id": "s1", "latex": "x=1"}], "has_error": True, "first_error_step": "s2"}, model="m", prompt_version="p", duration_ms=1, usage={})
