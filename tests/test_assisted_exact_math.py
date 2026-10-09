import pytest
import sympy as sp
from nirs_cas.answers import parse_answer, parse_answer_parts
from nirs_cas.exact_math import expression, equal_sets, finite_restriction
from nirs_cas.assisted_rules import inequality_set, trig_solutions
from nirs_cas.environment import exact_scalar


@pytest.mark.parametrize(
    "raw,expected",
    [
        (
            r"x\in(0;1]\cup[2;+\infty)",
            sp.Union(sp.Interval.Lopen(0, 1), sp.Interval(2, sp.oo)),
        ),
        (r"x\in\{-1;0;1\}", sp.FiniteSet(-1, 0, 1)),
        (r"x=\pm\frac{1}{2}", sp.FiniteSet(-sp.Rational(1, 2), sp.Rational(1, 2))),
        (r"x=1; x=2", sp.FiniteSet(1, 2)),
    ],
)
def test_answers_exact(raw, expected):
    answer = parse_answer(raw)
    assert answer.status == "OK", answer.reason
    assert answer.value == expected


@pytest.mark.parametrize(
    "raw",
    [
        r"(0;1]\cup rubbish",
        r"x=\pi k",
        r"x=1; nonsense",
        r"[-\infty;1]",
        r"x\in[0;1] extra",
    ],
)
def test_answers_do_not_accept_prefixes(raw):
    answer = parse_answer(raw)
    assert answer.status == "PARSE_FAILED"
    assert answer.raw_latex == raw and answer.reason


def test_root_answer_mismatch_and_independent_parts():
    assert equal_sets(parse_answer("1;2").value, sp.FiniteSet(1, 3)) is False
    parts = parse_answer_parts(["1;2", "3;4"])
    assert [p.value for p in parts] == [sp.FiniteSet(1, 2), sp.FiniteSet(3, 4)]


def test_family_restriction_uses_exact_bounds_beyond_twenty():
    family = parse_answer(r"x=\pi k, k\in\mathbb{Z}")
    assert family.status == "OK", family.reason
    assert finite_restriction(
        family.value, sp.Interval(100 * sp.pi, 102 * sp.pi)
    ) == sp.FiniteSet(100 * sp.pi, 101 * sp.pi, 102 * sp.pi)


def test_multiple_periodic_declarations_and_ambiguous_parts():
    answer = parse_answer(
        r"x=\pi k,k\in\mathbb{Z};x=\frac{\pi}{2}+\pi n,n\in\mathbb{Z}"
    )
    assert answer.status == "OK", answer.reason
    assert parse_answer("x=1;y=2").status == "PARSE_FAILED"
    assert parse_answer("y=2", sp.Symbol("x", real=True)).status == "PARSE_FAILED"


@pytest.mark.parametrize(
    "raw,ok",
    [
        (r"\text{Ответ: } (1;31]", True),
        (r"\text{Answer: } x=1", True),
        (r"\text{when x is positive} x=1", False),
        (r"\text{Ответ: а) } x=1;\text{б) } x=2", False),
    ],
)
def test_only_presentation_labels_can_be_ignored(raw, ok):
    assert (parse_answer(raw).status == "OK") is ok


@pytest.mark.parametrize(
    "equation,answer,status",
    [
        (r"\sin x=0", r"x=\pi k,k\in\mathbb{Z}", True),
        (r"\cos x=0", r"x=\pi k,k\in\mathbb{Z}", False),
        (r"\sin x=\frac{1}{2}", r"x=\frac{\pi}{6}+2\pi k;k\in\mathbb{Z}", False),
    ],
)
def test_trig_periodic_solution_completeness(equation, answer, status):
    actual = parse_answer(answer)
    assert actual.status == "OK", actual.reason
    expected, _ = trig_solutions(equation)
    assert equal_sets(expected, actual.value) is status


def test_noncanonical_trig_is_unsupported():
    with pytest.raises(ValueError):
        trig_solutions(r"\sin(2x)+\cos x=0")


@pytest.mark.parametrize("raw,answer", [
    (r"\sin(2x)=0", r"x=\frac{\pi}{2} k,k\in\mathbb{Z}"),
    (r"\sin(2x+\pi/3)=0", r"x=-\pi/6+\pi k/2,k\in\mathbb{Z}"),
    (r"\cos(3x)=1", r"x=2\pi k/3,k\in\mathbb{Z}"),
    (r"\sin(-2x)=0", r"x=\pi k/2,k\in\mathbb{Z}"),
    (r"\sin^2 x=1", r"x=\pi/2+\pi k,k\in\mathbb{Z}"),
    (r"\sin^2 x-\sin x=0", r"x=\pi k,k\in\mathbb{Z}; x=\pi/2+2\pi k,k\in\mathbb{Z}"),
    (r"\cos(2x)-\sqrt{2}\sin(x+\pi)-1=0", r"x=\pi k,k\in\mathbb{Z}; x=\pi/4+2\pi k,k\in\mathbb{Z}; x=3\pi/4+2\pi k,k\in\mathbb{Z}"),
])
def test_affine_and_polynomial_trig_families(raw, answer):
    roots, _ = trig_solutions(raw)
    actual = parse_answer(answer)
    assert actual.status == "OK", actual.reason
    assert equal_sets(roots, actual.value) is True


def test_affine_trig_wrong_spacing_and_exact_interval():
    roots, _ = trig_solutions(r"\sin(2x)=0")
    assert equal_sets(roots, parse_answer(r"x=\pi k,k\in\mathbb{Z}").value) is False
    roots, _ = trig_solutions(r"\sin(2x)=0", sp.Interval(100*sp.pi, 101*sp.pi))
    assert roots == sp.FiniteSet(100*sp.pi, sp.Rational(201, 2)*sp.pi, 101*sp.pi)


@pytest.mark.parametrize("equation,expected", [(r"\sin^2x+\cos^2x=1", sp.S.Reals), (r"\sin^2x+\cos^2x=0", sp.S.EmptySet)])
def test_trig_identity_solution_sets(equation, expected):
    assert trig_solutions(equation)[0] == expected


@pytest.mark.parametrize("raw", [r"\sin(x^2)=0", r"\sin(ax)=0", r"\sin^5 x=0"])
def test_new_trig_rules_abstain_outside_bounded_class(raw):
    with pytest.raises(ValueError):
        trig_solutions(raw)


@pytest.mark.parametrize(
    "raw,answer,status",
    [
        (r"\frac{x-1}{x-2}\ge0", r"(-\infty;1]\cup(2;+\infty)", True),
        (r"\frac{x-1}{x-2}\ge0", r"(-\infty;1]\cup[2;+\infty)", False),
        (r"2^x>4", r"(2;+\infty)", True),
        (r"2^x>4", r"[2;+\infty)", False),
        (r"\left(\frac{1}{2}\right)^x>4", r"(-\infty;-2)", True),
        (r"\log_2(x)>1", r"(2;+\infty)", True),
        (r"\log_2(x)>1", r"[2;+\infty)", False),
        (r"\log_{8}(x^3-3x^2+3x-1)\ge\log_2(x^2-1)-5", r"(1;31]", True),
    ],
)
def test_inequality_classes(raw, answer, status):
    expected, x = inequality_set(raw)
    actual = parse_answer(answer, x)
    assert actual.status == "OK", actual.reason
    assert equal_sets(expected, actual.value) is status


@pytest.mark.parametrize("raw", [r"a^x>1", r"\log_a x>1", r"\sin x>0", r"(-2)^x>1"])
def test_inequality_unsupported(raw):
    with pytest.raises((ValueError, NotImplementedError)):
        inequality_set(raw)


@pytest.mark.parametrize(
    "raw,answer,status",
    [
        ("x+1>2", "(1;+\\infty)", True),
        ("x+1>2", "[1;+\\infty)", False),
        ("x^2<=1", "[-1;1]", True),
        ("x^2<=1", "(-1;1)", False),
        (r"\frac{x-1}{x-1}\ge0", r"(-\infty;1)\cup(1;+\infty)", True),
        (r"\frac{x-1}{x-1}\ge0", r"\mathbb{R}", False),
    ],
)
def test_linear_quadratic_and_cancelled_poles(raw, answer, status):
    result, x = inequality_set(raw)
    assert equal_sets(result, parse_answer(answer, x).value) is status


@pytest.mark.parametrize("raw", ["a*x+1>0", "x^2>a", r"\frac{x-a}{x-2}>0"])
def test_each_rational_class_rejects_unbound_parameters(raw):
    with pytest.raises(ValueError):
        inequality_set(raw)


@pytest.mark.parametrize(
    "target,givens,expected",
    [
        (r"\frac{n!}{r!(n-r)!}", ("n=5", "r=2"), 10),
        ("x^2", ("x=-2",), 4),
        ("1.5+2.25", (), sp.Rational(15, 4)),
    ],
)
def test_exact_bindings(target, givens, expected):
    assert exact_scalar(target, givens) == expected


def test_invalid_and_missing_bindings():
    assert exact_scalar("x^2", ("x=-2",)) != -4
    with pytest.raises(ValueError):
        exact_scalar("n!", ())
    with pytest.raises(ValueError):
        exact_scalar("n!", ("n=-2",))
    with pytest.raises(ValueError):
        exact_scalar("x", ("x=1", "x=2"))


@pytest.mark.parametrize("bound", ["n=101", "n=100000000000", "n=1.5"])
def test_symbolic_factorial_bounds_are_checked_before_evaluation(bound):
    with pytest.raises(ValueError, match="bounded nonnegative integer"):
        exact_scalar("n!", (bound,))


@pytest.mark.parametrize(
    "answer,status", [(r"-\frac{56}{65}", True), (r"-\frac{16}{65}", False)]
)
def test_quadrant_signs_exact(answer, status):
    expected = exact_scalar(
        r"\sin(x+y)",
        (r"\sin x=\frac{3}{5}", r"\cos y=-\frac{12}{13}"),
        (r"\frac{\pi}{2}<x<\pi", r"\frac{\pi}{2}<y<\pi"),
    )
    assert (sp.simplify(expected - expression(answer)) == 0) is status


def test_quadrant_prose_is_unsupported():
    with pytest.raises(ValueError):
        exact_scalar(
            r"\sin(x+y)",
            (r"\sin x=\frac{3}{5}", r"\cos y=-\frac{12}{13}"),
            (r"x\in\text{second quadrant}", r"y\in\text{second quadrant}"),
        )


@pytest.mark.parametrize(
    "raw,expected",
    [
        (r"\sin(x)^2", sp.sin(sp.Symbol("x", real=True)) ** 2),
        (r"\log_2(x)^2", (sp.log(sp.Symbol("x", real=True)) / sp.log(2)) ** 2),
        (r"\sin(x^2)", sp.sin(sp.Symbol("x", real=True) ** 2)),
    ],
)
def test_grouped_function_power_has_correct_scope(raw, expected):
    assert sp.simplify(expression(raw) - expected) == 0
