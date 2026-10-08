import pytest
from nirs_cas import verify_step, verify_solution


@pytest.mark.parametrize("left,right,status", [
    ("2x+3=7", "x=2", "VALID"),
    ("2x+3=7", "x=3", "INVALID"),
    ("x^2=4", "x=2", "INVALID"),
    ("x(x-1)=0", "x=1", "INVALID"),
    ("x=1", "x^2=1", "INVALID"),
    (r"\frac{x}{x}", "1", "INVALID"),
    (r"\frac{x}{x}=1", "1=1", "INVALID"),
    (r"\frac{x}{x-1}=2", "x=2", "VALID"),
    (r"\sqrt{x}=2", "x=4", "VALID"),
    (r"\sqrt{x}=-2", "x=4", "INVALID"),
    (r"\sqrt{x^2}", "x", "UNSUPPORTED"),
    (r"\frac{x^2-1}{x-1}", "x+1", "INVALID"),
    ("0.1+0.2", "0.3", "VALID"),
    ("2(x+y)", "2x+2y", "VALID"),
    ("2(x+y)", "2x+y", "INVALID"),
    ("2x+2y=4", "x+y=2", "VALID"),
    ("x+y=2", "x-y=2", "UNSUPPORTED"),
    (r"\frac{x}{y}=1", "x=y", "UNSUPPORTED"),
    ("x=2", "2", "UNSUPPORTED"),
    (r"\sin{x}", "x", "UNSUPPORTED"),
])
def test_transition_semantics(left, right, status):
    result = verify_step(left, right)
    assert result.status == status, result


def test_first_error_is_one_based_destination():
    result = verify_solution(["2x+3=7", "2x=4", "x=3"])
    assert result["has_error"] is True
    assert result["first_error_step"] == 3


def test_unknown_does_not_become_invalid_or_correct():
    result = verify_solution([r"\sin{x}", "x"])
    assert result["status"] == "UNSUPPORTED"
    assert result["parse_status"] == "PARSE_FAILED"
    assert result["has_error"] is None
    assert result["first_error_step"] is None


def test_earlier_unknown_blocks_first_error_localization():
    result = verify_solution([r"\text{unknown}", "x=2", "x=3"])
    assert result["has_error"] is True
    assert result["first_error_step"] is None
    assert not result["covered"]


def test_false_constant_first_step():
    result = verify_solution(["1+1=3", "2=2"])
    assert result["first_error_step"] == 1


def test_single_symbolic_step_is_not_a_verified_solution():
    assert not verify_solution(["x=2"])["covered"]
