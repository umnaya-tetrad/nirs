"""Deterministic and deliberately conservative assisted-extraction compiler.

It consumes only the assisted contract itself.  In particular, no FERMAT
columns, GT verdicts, or hidden reference answer can enter this module.
"""

from __future__ import annotations

import re
from typing import Any

from .exact_math import math
from .answers import parse_answer


def _parsed(raw: str) -> dict[str, Any]:
    try:
        return {"status": "OK", "value": math(raw).to_dict(), "reason": None}
    except (ValueError, TypeError, NotImplementedError) as exc:
        answer = parse_answer(raw)
        return (
            answer.to_dict()
            if answer.status == "OK"
            else {"status": "PARSE_FAILED", "value": None, "reason": str(exc)}
        )


def _classify(raw: str, givens: list[str]) -> str:
    text = " ".join([raw, *givens]).lower()
    if "\\int_" in text:
        return "definite_integral"
    if "\\begin{vmatrix}" in text or "\\det" in text:
        return "determinant"
    if "\\begin{bmatrix}" in text or "\\begin{pmatrix}" in text:
        return "matrix_system"
    if re.search(r"\bf\([a-z]\)", text) and re.search(r"\bg\([a-z]\)", text):
        return "function_operation"
    if re.search(r"\\(?:geq|leq|ge|le)(?![A-Za-z])|>=|<=|[<>]", text):
        return "inequality"
    if any(token in text for token in (r"\sin", r"\cos", r"\tan")) and "=" in text:
        return "trigonometric"
    if "=" in text:
        return "equation"
    if text.strip():
        return "expression"
    return "unknown"


def compile_task_spec(contract: dict[str, Any]) -> dict[str, Any]:
    """Compile an LLM assisted extraction into a serializable TaskSpec 1.0.

    Parsing failures are data, not an exception: an assisted CAS run must
    abstain rather than silently infer a task from prose.
    """
    source = contract.get("contract", contract)
    if not isinstance(source, dict) or source.get("schema_version") != "1.0":
        raise ValueError("Expected LLM Assisted Extraction 1.0")
    task = source.get("task")
    if not isinstance(task, dict) or task.get("visibility") not in {
        "visible",
        "not_visible",
    }:
        raise ValueError("Assisted contract has no valid task")
    visibility = task["visibility"]
    raw = task.get("raw_latex") if visibility == "visible" else None
    raw = raw.strip() if isinstance(raw, str) else None
    givens_out: list[dict[str, Any]] = []
    reasons: list[str] = []
    for given in task.get("givens", []) if visibility == "visible" else []:
        latex = given["latex"]
        parsed = _parsed(latex)
        givens_out.append(
            {"given_id": given["given_id"], "raw_latex": latex, "parse": parsed}
        )
        if parsed["status"] != "OK":
            reasons.append(
                f"given {given['given_id']} is not in the exact SymPy subset: {parsed['reason']}"
            )
    constraints_out: list[dict[str, Any]] = []
    for latex in task.get("constraints", []) if visibility == "visible" else []:
        parsed = _parsed(latex)
        constraints_out.append({"raw_latex": latex, "parse": parsed})
        if parsed["status"] != "OK":
            reasons.append(
                f"constraint is not in the exact SymPy subset: {parsed['reason']}"
            )
    goal_raw = task.get("goal") or {"type": "unknown"}
    goal = {
        "type": goal_raw.get("type", "unknown"),
        "target_latex": goal_raw.get("target_latex"),
    }
    task_class = _classify(raw or "", [g["raw_latex"] for g in givens_out])
    if visibility == "not_visible":
        reasons.append("task is not visible in the image")
    if goal["type"] == "unknown":
        reasons.append("goal is unknown")
    # These families have dedicated checkers, but they intentionally only run
    # after their exact parser says that the particular instance is supported.
    # Generic algebra parsing is not a prerequisite for a specialised exact
    # rule (matrix, determinant, integral, inequality, trigonometry).  Its
    # failure remains explicit provenance and the selected rule decides if it
    # can independently construct an exact representation.
    supported = (
        visibility == "visible"
        and goal["type"] != "unknown"
        and task_class != "unknown"
    )
    return {
        "schema_version": "1.0",
        "id": source["id"],
        "task": {
            "visibility": visibility,
            "raw_latex": raw,
            "givens": givens_out,
            "constraints": constraints_out,
            "goal": goal,
        },
        "steps": [
            {
                k: v
                for k, v in step.items()
                if k
                in {
                    "step_id",
                    "latex",
                    "role",
                    "derives_from",
                    "branch",
                    "uses_givens",
                    "exactness",
                }
            }
            for step in source["steps"]
        ],
        "compilation": {
            "status": "supported" if supported else "unsupported",
            "task_class": task_class,
            "reasons": reasons,
        },
    }
