import copy
import ast
import hashlib
import json
from pathlib import Path
import pytest
from nirs_cas import analyze_assisted_contract, analyze_contract
from nirs_cas.graph_verifier import verify_graph
from nirs_cas.graph_verifier import _equivalence
from nirs_cas.task_spec import compile_task_spec
from nirs_cas.assisted_analysis import isolated_evidence

ROOT = Path(__file__).resolve().parents[1]


def test_auxiliary_equation_definition_is_not_a_false_transition_error():
    c = contract(
        [
            step(1, "x^2+1=x^2+1", role="initial", uses=("g1",)),
            step(2, "x^2+1=0", (1,), role="definition"),
            step(3, "x=0", (2,), role="answer"),
        ],
        givens=("x^2+1",),
        target="x^2+1",
        goal="simplify",
    )
    result = analyze_assisted_contract(c, ROOT, timeout=None)
    assert result["problem"]["graph_check"]["nodes"][1]["status"] == "UNSUPPORTED"
    assert result["first_error_step"] is None and result["verdict"] == "indeterminate"


@pytest.mark.parametrize(
    "bound,answer,status",
    [("x=1", "1", "correct"), ("x=1", "2", "incorrect"), ("x=0", "1", "indeterminate")],
)
def test_denominator_substitution_domain(bound, answer, status):
    c = contract(
        [step(1, r"\frac{1}{x}=" + answer, role="answer", uses=("g1",))],
        givens=(bound,),
        target=r"\frac{1}{x}",
        goal="evaluate",
    )
    assert analyze_assisted_contract(c, ROOT, timeout=None)["verdict"] == status


@pytest.mark.parametrize(
    "constraints,status",
    [
        (("x\\neq0",), "correct"),
        ((), "incorrect"),
        (("x\\neq\\mystery",), "indeterminate"),
    ],
)
def test_explicit_nonzero_constraint_preserves_domain(constraints, status):
    c = contract(
        [step(1, r"\frac{x}{x}=1", role="answer", uses=("g1",))],
        givens=(r"\frac{x}{x}",),
        target=r"\frac{x}{x}",
        goal="simplify",
        constraints=constraints,
    )
    assert analyze_assisted_contract(c, ROOT, timeout=None)["verdict"] == status


def contract(steps, *, givens=("x=2",), target="x", goal="solve", constraints=()):
    return {
        "schema_version": "1.0",
        "id": "case",
        "task": {
            "visibility": "visible",
            "raw_latex": givens[0] if givens else target,
            "givens": [
                {"given_id": f"g{i}", "latex": g} for i, g in enumerate(givens, 1)
            ],
            "goal": {"type": goal, "target_latex": target},
            "constraints": list(constraints),
        },
        "steps": steps,
        "meta": {"model": "test"},
    }


def step(
    i,
    latex,
    refs=(),
    role="transformation",
    *,
    uses=(),
    branch="main",
    exactness="exact",
):
    return {
        "step_id": f"s{i}",
        "latex": latex,
        "role": role,
        "derives_from": [f"s{j}" for j in refs],
        "uses_givens": list(uses),
        "branch": branch,
        "exactness": exactness,
    }


@pytest.mark.parametrize(
    "answer,expected,first",
    [
        ("x=2", "correct", None),
        ("x=3", "incorrect", "s2"),
        (r"x=\unknown", "indeterminate", None),
    ],
)
def test_graph_equation_triplet(answer, expected, first):
    c = contract(
        [
            step(1, "x=2", role="initial", uses=("g1",)),
            step(2, answer, (1,), role="answer"),
        ]
    )
    out = analyze_assisted_contract(c, ROOT, timeout=None)
    assert out["verdict"] == expected and out["first_error_step"] == first


@pytest.mark.parametrize(
    "tail,expected",
    [("=4", "correct"), ("=5", "incorrect"), (r"=\unknown", "indeterminate")],
)
def test_independent_continuations(tail, expected):
    c = contract(
        [
            step(1, "1+1=2", role="independent"),
            step(2, "3+1=4", role="independent", branch="independent"),
            step(3, tail, (2,), role="answer", branch="independent"),
        ],
        givens=(),
        target="4",
        goal="evaluate",
    )
    out = analyze_assisted_contract(c, timeout=None)
    assert out["verdict"] == expected
    graph = out["problem"]["graph_check"]
    assert graph["edges"][0]["from"] == "s2"


def test_unverified_ancestor_blocks_error_but_retains_final_evidence():
    c = contract(
        [
            step(1, r"\text{unreadable reasoning}", role="initial"),
            step(2, "x=3", (1,), role="answer"),
        ]
    )
    out = analyze_assisted_contract(c, ROOT, timeout=None)
    assert out["verdict"] == "indeterminate" and out["first_error_step"] is None
    assert out["problem"]["context_check"]["status"] == "invalid"
    assert out["problem"]["context_check"]["localization_blocked"]
    assert not out["problem"]["verified_solution_covered"]


def test_correct_final_does_not_cover_unknown_graph():
    c = contract(
        [
            step(1, r"\text{unreadable reasoning}", role="initial"),
            step(2, "x=2", (1,), role="answer"),
        ]
    )
    out = analyze_assisted_contract(c, timeout=None)
    assert out["verdict"] == "indeterminate"
    assert out["problem"]["context_check"]["status"] == "valid"
    assert not out["problem"]["verified_solution_covered"]


def test_unavailable_context_preserves_local_error_for_a_linear_chain():
    c = contract(
        [step(1, "x=2", role="initial"), step(2, "x=3", (1,), role="answer")],
        givens=(),
        target="",
        goal="unknown",
    )
    result = analyze_assisted_contract(c, ROOT, timeout=None)
    assert result["verdict"] == "incorrect" and result["first_error_step"] == "s2"
    assert result["problem"]["context_check"]["status"] == "unsupported"
    assert not result["problem"]["verified_solution_covered"]


@pytest.mark.parametrize(
    "refs,uses,exactness",
    [
        (("s9",), (), "exact"),
        (("s1",), (), "exact"),
        ((), ("g9",), "exact"),
        ((), (), "unknown"),
        ((), (), "approximate"),
    ],
)
def test_invalid_graph_and_uncertain_ocr_abstain(refs, uses, exactness):
    s = step(1, "x=2", role="answer", exactness=exactness)
    s["derives_from"] = list(refs)
    s["uses_givens"] = list(uses)
    out = analyze_assisted_contract(contract([s]), timeout=None)
    assert not out["problem"]["verified_solution_covered"]
    if exactness != "exact":
        assert out["verdict"] == "indeterminate"


@pytest.mark.parametrize(
    "definition,status",
    [("x=2", "VALID"), ("x=3", "INVALID"), (r"x=\mystery", "UNSUPPORTED")],
)
def test_definition_does_not_overwrite_given(definition, status):
    c = contract([step(1, definition, role="definition", uses=("g1",))])
    graph = verify_graph(compile_task_spec(c))
    assert graph["nodes"][0]["status"] == status


def test_missing_exactness_and_duplicate_givens_abstain():
    c = contract([step(1, "x=2", role="answer")])
    c["steps"][0].pop("exactness")
    assert analyze_assisted_contract(c, timeout=None)["verdict"] == "indeterminate"


@pytest.mark.parametrize(
    "definition,expected",
    [("t=x^2", "correct"), ("t=x^3", "incorrect"), (r"t=\mystery", "indeterminate")],
)
def test_polynomial_definition_substitution(definition, expected):
    c = contract(
        [
            step(1, "x^2=4", role="initial", uses=("g1",)),
            step(2, definition, (1,), role="definition"),
            step(3, "t=4", (1, 2), role="substitution"),
            step(4, r"x=\pm2", (3,), role="answer"),
        ],
        givens=("x^2=4",),
    )
    assert analyze_assisted_contract(c, ROOT, timeout=None)["verdict"] == expected


def test_definition_of_original_variable_checks_the_condition():
    c = contract(
        [
            step(1, "x^2=1", role="initial", uses=("g1",)),
            step(2, "x=2", (1,), role="definition"),
            step(3, "x=2", (2,), role="answer"),
        ],
        givens=("x^2=1",),
    )
    result = analyze_assisted_contract(c, ROOT, timeout=None)
    assert result["verdict"] == "incorrect" and result["first_error_step"] == "s2"


@pytest.mark.parametrize(
    "value,status", [("1", "VALID"), ("2", "INVALID"), (r"\mystery", "UNSUPPORTED")]
)
def test_definition_inside_explicit_branch(value, status):
    c = contract(
        [
            step(1, "x^2=1", role="initial", uses=("g1",)),
            step(2, "x=" + value, (1,), role="definition", branch="plus_minus_1"),
        ],
        givens=("x^2=1",),
    )
    assert verify_graph(compile_task_spec(c))["nodes"][1]["status"] == status
    c = contract([step(1, "x=2", role="answer")])
    c["task"]["givens"].append({"given_id": "g1", "latex": "x=3"})
    assert analyze_assisted_contract(c, timeout=None)["verdict"] == "indeterminate"


def test_definition_bindings_are_scoped_to_ancestors():
    c = contract(
        [
            step(1, "n=5", role="definition"),
            step(2, "n!=120", (1,), role="substitution"),
            step(3, "n!=120", role="independent", branch="independent"),
        ],
        givens=(),
        target="n!",
        goal="evaluate",
    )
    graph = verify_graph(compile_task_spec(c))
    assert graph["nodes"][1]["status"] == "VALID"
    assert graph["nodes"][2]["status"] == "UNSUPPORTED"


@pytest.mark.parametrize(
    "answer,status",
    [("120", "correct"), ("119", "incorrect"), (r"\mystery", "indeterminate")],
)
def test_scalar_goal_uses_verified_definition_scope(answer, status):
    c = contract(
        [
            step(1, "n=5", role="definition"),
            step(2, "n!=" + answer, (1,), role="substitution"),
            step(3, "n!=" + answer, (2,), role="answer"),
        ],
        givens=(),
        target="n!",
        goal="evaluate",
    )
    out = analyze_assisted_contract(c, ROOT, timeout=None)
    assert out["verdict"] == status
    if status != "indeterminate":
        assert out["problem"]["context_check"]["status"] in ("valid", "invalid")


def test_multiple_equalities_check_every_rhs():
    c = contract(
        [step(1, "2+2=4=5", role="answer")], givens=(), target="4", goal="evaluate"
    )
    out = analyze_assisted_contract(c, timeout=None)
    assert out["verdict"] == "incorrect" and out["first_error_step"] == "s1"


@pytest.mark.parametrize(
    "root,expected",
    [("x=1", "correct"), ("x=2", "incorrect"), (r"x=\mystery", "indeterminate")],
)
def test_explicit_plus_minus_branches(root, expected):
    c = contract(
        [
            step(1, "x^2=1", role="initial", uses=("g1",)),
            step(2, root, (1,), branch="plus_minus_1"),
            step(3, "x=-1", (1,), branch="plus_minus_2"),
            step(4, r"x=\pm1", (2, 3), role="answer"),
        ],
        givens=("x^2=1",),
    )
    out = analyze_assisted_contract(c, ROOT, timeout=None)
    assert out["verdict"] == expected


@pytest.mark.parametrize(
    "answer,expected",
    [("t>4", "correct"), ("t>=4", "incorrect"), (r"t>\mystery", "indeterminate")],
)
def test_exponential_definition_and_substitution(answer, expected):
    c = contract(
        [
            step(1, "2^x>4", role="initial", uses=("g1",)),
            step(2, "t=2^x", (1,), role="definition"),
            step(3, answer, (1, 2), role="substitution"),
            step(4, "x>2", (3,), role="answer"),
        ],
        givens=("2^x>4",),
    )
    out = analyze_assisted_contract(c, ROOT, timeout=None)
    assert out["verdict"] == expected


@pytest.mark.parametrize(
    "answer,status",
    [("x=2", "VALID"), ("y=2", "UNSUPPORTED"), (r"x=\bad", "UNSUPPORTED")],
)
def test_relation_variable_names_are_not_interchangeable(answer, status):
    c = contract(
        [
            step(1, "x=2", role="initial", uses=("g1",)),
            step(2, answer, (1,), role="answer"),
        ]
    )
    assert verify_graph(compile_task_spec(c))["nodes"][1]["status"] == status


@pytest.mark.parametrize(
    "answer,expected",
    [
        (r"x=100\pi; x=101\pi", "correct"),
        (r"x=100\pi", "incorrect"),
        (r"x=100\pi; x=\mystery", "indeterminate"),
    ],
)
def test_finite_periodic_selection_checks_completeness(answer, expected):
    c = contract(
        [
            step(1, r"\sin x=0", role="initial", uses=("g1",)),
            step(2, r"x=\pi k,k\in\mathbb{Z}", (1,)),
            step(3, answer, (2,), role="answer", uses=("g2",)),
        ],
        givens=(r"\sin x=0", r"x\in[100\pi;101\pi]"),
    )
    out = analyze_assisted_contract(c, ROOT, timeout=None)
    assert out["verdict"] == expected


def test_all_function_branches_and_domains_are_checked():
    rows = [
        r"(f+g)(x)=x^2+2x+1",
        r"(f-g)(x)=x^2-2x-1",
        r"(fg)(x)=2x^3+x^2",
        r"(\frac{f}{g})(x)=\frac{x^2}{2x+1}",
    ]
    c = contract(
        [step(i, r, role="answer", uses=("g1", "g2")) for i, r in enumerate(rows, 1)],
        givens=("f(x)=x^2", "g(x)=2x+1"),
        target="",
        goal="compute_function",
    )
    out = analyze_assisted_contract(c, ROOT, timeout=None)
    assert out["verdict"] == "correct" and out["problem"]["verified_solution_covered"]
    c["steps"][3]["latex"] = r"(\frac{f}{g})(x)=\frac{x^2}{2x+1},x\neq 0"
    out = analyze_assisted_contract(c, timeout=None)
    assert out["verdict"] == "incorrect" and out["first_error_step"] == "s4"
    c["steps"][3] = copy.deepcopy(c["steps"][0])
    c["steps"][3]["step_id"] = "s4"
    out = analyze_assisted_contract(c, timeout=None)
    assert not out["problem"]["verified_solution_covered"]


@pytest.mark.parametrize(
    "value,status",
    [
        (r"\begin{bmatrix}4\end{bmatrix}", "correct"),
        (r"\begin{bmatrix}5\end{bmatrix}", "incorrect"),
        (r"\begin{bmatrix}a\end{bmatrix}", "indeterminate"),
    ],
)
def test_matrix_graph_exact_environment(value, status):
    c = contract(
        [
            step(
                1, r"X=\begin{bmatrix}4\end{bmatrix}", role="answer", uses=("g1", "g2")
            ),
            step(2, "Y=" + value, role="answer", uses=("g1", "g2")),
        ],
        givens=(
            r"X+Y=\begin{bmatrix}8\end{bmatrix}",
            r"X-Y=\begin{bmatrix}0\end{bmatrix}",
        ),
        target="X,Y",
    )
    out = analyze_assisted_contract(c, ROOT, timeout=None)
    assert out["verdict"] == status


def test_fresh_definition_does_not_mask_initial_condition_error():
    c = contract([step(1, "x=3", role="initial"), step(2, "x=3", (1,), role="answer")])
    out = analyze_assisted_contract(c, timeout=None)
    assert out["verdict"] == "incorrect" and out["first_error_step"] == "s1"


@pytest.mark.parametrize(
    "before,after,status",
    [
        (
            r"\cos 2x-\sqrt{2}\sin(x+\pi)-1=0",
            r"1-2\sin^2 x+\sqrt{2}\sin x-1=0",
            "VALID",
        ),
        (r"\sin x=0", r"\sin x=1", "INVALID"),
        (r"\sin x=c", r"\sin x=0", "UNSUPPORTED"),
    ],
)
def test_trig_transition_exact_residual_or_complete_roots(before, after, status):
    assert _equivalence(before, after) == status


def test_ordinary_dev20_frozen_regression():
    items = json.loads(
        (ROOT / "dataset/artifacts/gemini_ordinary_fermat_dev_20.json").read_text(
            encoding="utf-8"
        )
    )["items"]
    expected = json.loads(
        (ROOT / "tests/fixtures/ordinary_dev20_baseline.json").read_text(
            encoding="utf-8"
        )
    )
    for item, before in zip(items, expected):
        actual = analyze_contract(item["contract"], timeout=None)
        assert {k: actual[k] for k in before} == before


def test_ordinary_implementation_is_unchanged():
    expected = json.loads(
        (ROOT / "tests/fixtures/ordinary_source_sha256.json").read_text(
            encoding="utf-8"
        )
    )
    for path, digest in expected.items():
        text = (ROOT / path).read_text(encoding="utf-8")
        if path.endswith("contracts.py"):
            function = next(
                node
                for node in ast.parse(text).body
                if isinstance(node, ast.FunctionDef) and node.name == "analyze_contract"
            )
            text = ast.get_source_segment(text, function)
        assert hashlib.sha256(text.encode()).hexdigest() == digest


def test_forbidden_labels_and_ids_cannot_influence_assisted_result():
    c = contract(
        [
            step(1, "x=2", role="initial", uses=("g1",)),
            step(2, "x=3", (1,), role="answer"),
        ]
    )
    before = analyze_assisted_contract(c, timeout=None)
    c.update(
        id="different",
        has_error=False,
        verdict="correct",
        orig_q="x=3",
        first_error_step="s1",
    )
    c["steps"][0]["verdict"] = "error"
    after = analyze_assisted_contract(c, timeout=None)
    assert (before["verdict"], before["first_error_step"]) == (
        after["verdict"],
        after["first_error_step"],
    )
    assert (
        "orig_q" not in after["problem"]["task_spec"]
        and "verdict" not in after["problem"]["task_spec"]["steps"][0]
    )


def test_assisted_worker_is_time_bounded():
    spec = compile_task_spec(contract([step(1, "x=2", role="answer")]))
    graph, context = isolated_evidence(spec, 0.0001)
    assert context["status"] == "UNSUPPORTED" and "TIMEOUT" in context["reason"]
    assert not graph["covered"]
