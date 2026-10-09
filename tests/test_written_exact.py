from copy import deepcopy

import pytest
import sympy as sp

from nirs_cas.adapter import extract_step_latex
from nirs_cas.exact_math import expression
from nirs_cas.written_exact import verify_exact_written, run_exact_isolated
from nirs_cas.written_layout import written_layout


@pytest.mark.parametrize(
    "steps,status,first",
    [
        (["2x=x+5", "x=5"], "VALID", None),
        (["2x=x+5", "x=6"], "INVALID", 2),
    (["x^2=1", r"x=\pm1"], "VALID", None),
    ([r"\sin(2x)=0", r"x=\pi k/2,k\in\mathbb{Z}"], "VALID", None),
    ([r"\sin(2x)=0", r"x=\pi k,k\in\mathbb{Z}"], "INVALID", 2),
    ([r"\sin(2x)=0", r"x=\pi k/2"], "UNSUPPORTED", None),
        (["x^2=1", "x=1"], "INVALID", 2),
        (["x=1", "x^2=1", r"x=\pm1"], "INVALID", 3),
        (["x^2=1", r"x=\pm2"], "INVALID", 2),
        (["x^2=1", r"x=\unknown"], "UNSUPPORTED", None),
        (
            [r"\frac{5-2x}{3}\leq\frac{x}{6}-5", r"x\geq8", r"x\in[8;\infty)"],
            "VALID",
            None,
        ),
        ([r"\frac{5-2x}{3}\leq\frac{x}{6}-5", r"x\leq8"], "INVALID", 2),
        ([r"\frac{x}{x}=1"], "INVALID", 1),
        ([r"\frac{x}{x}=1, x\neq0"], "VALID", None),
        (["1+1=2", "=3"], "INVALID", 2),
        (["1+1=2", "=2"], "VALID", None),
        (["=2+2=4"], "VALID", None),
        (["=2+2=5"], "INVALID", 1),
        ([r"(-5i)(\frac{1}{8}i)=\frac{5}{8}"], "VALID", None),
        ([r"(-5i)(\frac{1}{8}i)=\frac{7}{8}"], "INVALID", 1),
        ([r"\frac{dy}{dx}=1", "1+1=3"], "UNSUPPORTED", None),
        (["a(a-3)+2=a^2-3a+2", "a^2-3a+2=1-3+2=0"], "UNSUPPORTED", None),
        ([r"\text{second quadrant} x=1", "1+1=3"], "UNSUPPORTED", None),
        (
            [r"\sin x=\sin x+1"],
            "UNSUPPORTED",
            None,
        ),  # no proof beyond an initial premise
    ],
)
def test_written_exact_proofs_and_abstentions(steps, status, first):
    result = verify_exact_written(steps)
    assert result["status"] == status, result
    assert result["first_error_step"] == first


def test_subtraction_comment_is_not_a_new_equation():
    steps = [
        "2x=x+5",
        r"2x-x=x+5-x \quad (\text{subtracting } x \text{ from both sides})",
        "x=5",
    ]
    assert verify_exact_written(steps)["covered"]


@pytest.mark.parametrize(
    "answer,status",
    [("2x^2+3x+1", "VALID"), ("2x+3x+1", "INVALID"), (r"\mystery", "UNSUPPORTED")],
)
def test_vertical_layout_is_an_identity_not_a_trusted_equation(answer, status):
    source = (
        r"\begin{array}{r}3x^2+5x+2\\-(x^2+2x+1)\\\hline " + answer + r"\\\end{array}"
    )
    result = verify_exact_written([source])
    assert result["status"] == status, result


def test_partial_parse_keeps_exact_arithmetic_error_evidence():
    result = verify_exact_written([r"\mystery=2+2=5"])
    assert result["has_error"] is True
    assert result["known_error_steps"] == [1]
    assert result["first_error_step"] == 1
    assert not result["covered"]


def test_gt_fields_cannot_influence_exact_verifier():
    original = {
        "id": "a",
        "steps": [{"latex": "2x=4"}, {"latex": "x=3"}],
        "verdict": "incorrect",
    }
    changed = deepcopy(original)
    changed.update(
        verdict="correct", findings=[{"latex": "x=2"}], first_error_step=None
    )
    changed["steps"][1].update(
        kind="note", derives_from=[], transformation={"rule_hint": "assume x=3"}
    )
    assert verify_exact_written(extract_step_latex(original)) == verify_exact_written(
        extract_step_latex(changed)
    )


@pytest.mark.parametrize(
    "raw", [r"\frac{d}{dx}(x^2)", r"\frac{d^2 y}{dx^2}", r"\frac{d x}{d\theta}"]
)
def test_differentials_are_never_products_of_letter_variables(raw):
    assert verify_exact_written([raw])["has_error"] is None


@pytest.mark.parametrize(
    "raw,expected",
    [
        (r"\sin^{-1}x", sp.asin(sp.Symbol("x", real=True))),
        (r"\sin^-1 x", sp.asin(sp.Symbol("x", real=True))),
        (r"2^-2", sp.Rational(1, 4)),
    ],
)
def test_signed_unbraced_exponent(raw, expected):
    assert sp.simplify(expression(raw) - expected) == 0


def test_exact_worker_is_bounded():
    result = run_exact_isolated(["2x=4", "x=2"], timeout=0.001)
    assert result["reason"] == "TIMEOUT_OR_WORKER_EXIT"
    assert not result["covered"] and result["has_error"] is None


@pytest.mark.parametrize("steps", [["x=1"], ["2x^2+3x+1"], ["x>1"], ["1+1"]])
def test_reading_a_premise_or_final_expression_is_not_verified_coverage(steps):
    result = verify_exact_written(steps)
    assert result["covered"] is False
    assert result["has_error"] is None


def test_whole_input_consumption_after_presentation_label():
    assert written_layout(r"\text{Note that } 3^2=9 \text{ and } 2^3=8").fragments == (
        "3^2=9",
        "2^3=8",
    )
    assert not verify_exact_written([r"\text{Note that } 3^2=9 trailing"])["covered"]


def test_exact_contract_retains_known_error_without_fabricating_firstness():
    from pathlib import Path
    from nirs_cas import analyze_exact_contract

    record = {
        "schema_version": "1.0",
        "id": "case",
        "steps": [
            {"step_id": "s1", "latex": r"\mystery"},
            {"step_id": "s2", "latex": "1+1=3"},
        ],
    }
    output = analyze_exact_contract(
        record, Path(__file__).resolve().parents[1], timeout=None
    )
    assert output["verdict"] == "indeterminate"
    assert output["first_error_step"] is None
    assert output["problem"]["known_error_step_ids"] == ["s2"]


def test_comparison_metrics_distinguish_error_detection_and_localization():
    from nirs_cas.improvement_report import _metrics

    rows = [
        {
            "id": "a",
            "covered": False,
            "verdict": "indeterminate",
            "first_error_step_id": None,
            "has_error": True,
            "parse_status": "OK",
        },
        {
            "id": "b",
            "covered": True,
            "verdict": "correct",
            "first_error_step_id": None,
            "has_error": False,
            "parse_status": "OK",
        },
    ]
    labels = {
        "a": {"verdict": "incorrect", "first_error_step": "s2"},
        "b": {"verdict": "correct"},
    }
    result = _metrics(rows, labels)
    assert result["verdict_accuracy_all"] == 0.5
    assert result["verdict_accuracy_decided"] == 1
    assert result["first_error_accuracy_incorrect"] == 0
    assert result["error_signals_on_gt_correct"] == 0
