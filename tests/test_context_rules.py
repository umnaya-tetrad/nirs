import pytest

from nirs_cas.context_rules import check_context


def spec(task_class, raw, steps, *, givens=(), constraints=()):
    return {
        "task": {
            "raw_latex": raw,
            "givens": [{"raw_latex": item} for item in givens],
            "constraints": [{"raw_latex": item} for item in constraints],
        },
        "steps": steps,
        "compilation": {"status": "supported", "task_class": task_class, "reasons": []},
    }


def steps(*latex):
    return [{"step_id": f"s{i}", "latex": value} for i, value in enumerate(latex, 1)]


@pytest.mark.parametrize(
    "raw,recorded,status",
    [
        (r"\begin{vmatrix}2&4\\-1&2\end{vmatrix}", r"D=8", "VALID"),
        (r"\begin{vmatrix}2&4\\-1&2\end{vmatrix}", r"D=0", "INVALID"),
        (r"\begin{vmatrix}a&b\\c&d\end{vmatrix}", r"D=8", "UNSUPPORTED"),
    ],
)
def test_determinant_context_rule(raw, recorded, status):
    assert check_context(spec("determinant", raw, steps(recorded))).status == status


@pytest.mark.parametrize(
    "recorded,status",
    [
        (
            (
                r"X=\begin{bmatrix}4&4\\0&4\end{bmatrix}",
                r"Y=\begin{bmatrix}1&-2\\0&5\end{bmatrix}",
            ),
            "VALID",
        ),
        (
            (
                r"X=\begin{bmatrix}4&4\\0&4\end{bmatrix}",
                r"Y=\begin{bmatrix}1&2\\0&5\end{bmatrix}",
            ),
            "INVALID",
        ),
        ((r"X=\begin{bmatrix}4&4\\0&4\end{bmatrix}",), "UNSUPPORTED"),
    ],
)
def test_matrix_context_rule(recorded, status):
    raw = r"X+Y=\begin{bmatrix}5&2\\0&9\end{bmatrix} \text{ and } X-Y=\begin{bmatrix}3&6\\0&-1\end{bmatrix}"
    assert check_context(spec("matrix_system", raw, steps(*recorded))).status == status


@pytest.mark.parametrize(
    "recorded,status",
    [(r"I=\frac{4\sqrt{2}}{3}", "VALID"), (r"I=4", "INVALID"), (r"I=x", "UNSUPPORTED")],
)
def test_integral_context_rule(recorded, status):
    raw = r"\int_{-1}^{1}5x^4\sqrt{x^5+1}\,dx"
    assert (
        check_context(spec("definite_integral", raw, steps(recorded))).status == status
    )


@pytest.mark.parametrize(
    "recorded,status",
    [(r"x\ge 2", "VALID"), (r"x>2", "INVALID"), (r"x\in(2;+\infty)", "INVALID")],
)
def test_inequality_context_rule(recorded, status):
    assert (
        check_context(
            spec("inequality", "", steps(recorded), givens=(r"x+1\ge 3",))
        ).status
        == status
    )


@pytest.mark.parametrize(
    "recorded,status",
    [(r"x=0", "VALID"), (r"x=\pi", "INVALID"), (r"x=\pi k", "UNSUPPORTED")],
)
def test_trigonometric_context_rule(recorded, status):
    assert (
        check_context(
            spec(
                "trigonometric",
                "",
                steps(recorded),
                givens=(r"\sin x=0",),
                constraints=(r"x\in\left[0;0\right]",),
            )
        ).status
        == status
    )


@pytest.mark.parametrize(
    "recorded,status",
    [
        (r"\left(\frac{2}{3}\right)^{-2}=\frac{9}{4}", "VALID"),
        (r"\left(\frac{2}{3}\right)^{-2}=\frac{27}{4}", "INVALID"),
        (r"x=1", "INVALID"),
    ],
)
def test_scalar_task_rule(recorded, status):
    data = spec("expression", "", steps(recorded))
    data["task"]["goal"] = {"target_latex": r"\left(\frac{2}{3}\right)^{-2}"}
    assert check_context(data).status == status


def test_function_operation_rule():
    data = spec(
        "function_operation",
        "",
        steps(
            r"(f+g)(x)=x^2+2x+1",
            r"(f-g)(x)=x^2-2x-1",
            r"(fg)(x)=2x^3+x^2",
            r"\left(\frac{f}{g}\right)(x)=\frac{x^2}{2x+1}",
        ),
        givens=(r"f(x)=x^2", r"g(x)=2x+1"),
    )
    assert check_context(data).status == "VALID"


def test_interval_answer_is_compared_as_a_set():
    data = spec("inequality", "", steps(r"x\in[2;+\infty)"), givens=(r"x+1\ge3",))
    assert check_context(data).status == "VALID"


def test_quadrant_substitution_checks_trig_value():
    data = spec(
        "trigonometric",
        "",
        steps(r"\sin(x+y)=-\frac{16}{65}"),
        givens=(r"\sin x=\frac{3}{5}", r"\cos y=-\frac{12}{13}"),
        constraints=(r"\frac{\pi}{2}<x<\pi", r"\frac{\pi}{2}<y<\pi"),
    )
    data["task"]["goal"] = {"type": "evaluate", "target_latex": r"\sin(x+y)"}
    assert check_context(data).status == "INVALID"
