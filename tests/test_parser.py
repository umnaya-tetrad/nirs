import pytest
import sympy as sp

from nirs_cas import parse_latex


@pytest.mark.parametrize("latex,expected", [
    ("2+3*4", 14), ("-2^2", -4), ("(-2)^2", 4),
    ("0.1+0.2", sp.Rational(3, 10)),
    (r"\frac{1+\frac{1}{2}}{3}", sp.Rational(1, 2)),
    (r"\sqrt{16}+\sqrt{9}", 7), (r"\sqrt[3]{-8}", -2),
    (r"(-8)^{1/3}", -2), (r"4^{-1/2}", sp.Rational(1, 2)),
    (r"$\left(2+3\right)\times 4$", 20),
    (r"\[\dfrac{2}{4}\]", sp.Rational(1, 2)),
    (r"\(\displaystyle 2\,x\)", 2 * sp.Symbol("x", real=True)),
    ("2−3", -1), (r"2\div4", sp.Rational(1, 2)),
    (r"2\alpha+\alpha", 3 * sp.Symbol("alpha", real=True)),
    (r"\pi+\pi", 2 * sp.pi),
])
def test_supported_values(latex, expected):
    result = parse_latex(latex)
    assert result.status == "OK", result.reason
    assert sp.simplify(result.value.sides[0] - expected) == 0


@pytest.mark.parametrize("latex", [
    "", "x-", "x+", "x=", "=x", "x=1=2", "(x+1]", "{x+1", "x**2", "x^2^3",
    r"\frac{1}", r"\frac{1}{}", r"\sqrt{}", r"\sqrt{-1}", r"\sqrt[0]{2}",
    r"\sqrt[13]{2}", r"\frac{1}{0}", r"\frac{1}{x-x}", r"\unknown{x}",
    r"\text{hello}", "sin(x)", "sqrt(4)", "x<2",
    "x^23", "x^-2", "x^{21}", "x^{1/0}", "x^{1/13}", "x^{y}",
    "2 3", "0^0", "x;1", "__import__('os')", "x" * 2050,
    "(" * 25 + "x" + ")" * 25, "((9^9)^9)^9",
])
def test_fail_closed(latex):
    result = parse_latex(latex)
    assert result.status == "PARSE_FAILED", latex
    assert result.value is None
    assert result.reason


def test_equation_does_not_evaluate_to_boolean():
    result = parse_latex("x=x")
    assert result.value.is_equation
    assert len(result.value.sides) == 2


def test_denominator_and_original_symbols_survive_cancellation():
    parsed = parse_latex(r"\frac{x}{x}").value
    assert [(kind, str(expr)) for kind, expr in parsed.constraints] == [("nonzero", "x")]
    assert [str(x) for x in parsed.symbols] == ["x"]


def test_multiple_variables_and_implicit_multiplication():
    value = parse_latex("2xy+z(x+y)").value
    x, y, z = sp.symbols("x y z", real=True)
    assert sp.expand(value.sides[0] - (2*x*y + z*(x+y))) == 0
