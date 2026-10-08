import pytest
import sympy as sp

from nirs_cas import parse_latex, verify_solution


@pytest.mark.parametrize('latex,expected', [
    (r'\sin\frac{\pi}{6}', sp.Rational(1, 2)),
    (r'\cos(-90^\circ)', 0),
    (r'\frac{6!}{3!(6-3)!}', 20),
    (r'\begin{vmatrix} 3 & 2 \\ -1 & 4 \end{vmatrix}', 14),
    ('(-1)^{2+3}', -1),
    (r'16\div4\div2', 2),
    (r'8\sqrt{15}\div2\sqrt{3}', 4 * sp.sqrt(5)),
])
def test_extended_expressions(latex, expected):
    result = parse_latex(latex)
    assert result.status == 'OK', result.reason
    assert sp.simplify(result.value.sides[0] - expected) == 0


@pytest.mark.parametrize('steps,error', [
    (['2+3=5=5', '=10/2=5'], None),
    (['2+3=6=6'], 1),
    (['8/4', '=3/1=3'], 2),
    ([r'\begin{vmatrix} 3 & 2 \\ -1 & 4 \end{vmatrix}=3(4)-2(-1)=14'], None),
    ([r'\begin{vmatrix} 3 & 2 \\ -1 & 4 \end{vmatrix}=3(4)+2(-1)=10'], 1),
    ([r'\begin{array}{r} 4x^2+3x \\ -(x^2+x) \\ \hline 3x^2+2x \\ \end{array}'], None),
    ([r'\begin{array}{r} 4x^2+3x \\ -(x^2+x) \\ \hline 2x^2+2x \\ \end{array}'], 1),
    ([r'\begin{enumerate}\item $2+2=4$\item $3+3=7$\end{enumerate}'], 1),
    ([r'\frac{2x}{3}\leq 4', r'2x\leq 12', r'x\leq 6'], None),
    ([r'\frac{2x}{3}\leq 4', r'2x\leq 8'], 2),
])
def test_written_chains_and_layouts(steps, error):
    result = verify_solution(steps)
    assert result['covered'], result
    assert result['first_error_step'] == error, result
    assert result['has_error'] == (error is not None)


def test_unknown_prose_is_not_silently_deleted_to_claim_coverage():
    result = verify_solution([r'\text{Assume x is positive} x^2=4', 'x=2'])
    assert not result['covered']
    assert result['first_error_step'] is None


def test_partial_chain_retains_independently_false_arithmetic():
    result = verify_solution([r'\unknown{x}=2+3=6'])
    assert not result['covered']
    assert result['has_error'] is True


def test_unrelated_substitutions_are_not_guessed():
    result = verify_solution(['a^2+1=2', 'b^2+1=5'])
    assert not result['covered']
