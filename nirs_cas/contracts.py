"""Adapter between the canonical NIRS JSON contracts and the SymPy verifier."""

from __future__ import annotations

from datetime import datetime, timezone
from time import perf_counter
from typing import Any
from uuid import uuid4

import sympy as sp

from nirs_llm.contracts import validate_contract

from .verifier import verify_solution


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _validate_input(contract: dict[str, Any], repo_root) -> None:
    # GT is already a SolutionAnalysis; VLM extraction is MathCoreInput. Both
    # carry the same canonical id/steps representation consumed by CAS.
    name = "solution_analysis" if "verdict" in contract else "math_core_input"
    validate_contract(contract, name, repo_root)


def _pipeline_stage(input_contract: dict[str, Any]) -> dict[str, Any]:
    meta = input_contract.get("meta", {})
    return {
        "name": "transcribe",
        "backend": meta.get("model", "ground-truth"),
        "status": "ok",
        **({"duration_ms": meta["duration_ms"]} if "duration_ms" in meta else {}),
    }


def _indeterminate(input_contract: dict[str, Any], reason: str) -> dict[str, Any]:
    steps = input_contract["steps"]
    return {
        "schema_version": "1.0",
        "id": input_contract["id"],
        "pipeline": {
            "approach": "llm_ocr_plus_math_core",
            "stages": [_pipeline_stage(input_contract), {
                "name": "verify", "backend": f"sympy@{sp.__version__}", "status": "skipped", "error": reason,
            }],
        },
        **({"problem": input_contract["problem"]} if "problem" in input_contract else {}),
        "steps": steps,
        **({"reading": input_contract["reading"]} if "reading" in input_contract else {}),
        "verdict": "indeterminate",
        "is_correct": None,
        "first_error_step": None,
        "last_correct_step": None,
        "findings": [],
        "steps_reviewed": [{"step_id": step["step_id"], "verdict": "indeterminate", "note": reason} for step in steps],
        "meta": {
            "run_id": f"cas-{uuid4()}", "approach": "llm_ocr_plus_math_core", "stage": "verify",
            "model": f"sympy@{sp.__version__}", "duration_ms": 0, "created_at": _now(),
            "tool_versions": {"sympy": sp.__version__},
        },
    }


def analyze_contract(input_contract: dict[str, Any], repo_root) -> dict[str, Any]:
    """Build canonical ``SolutionAnalysis`` from canonical extraction or GT steps.

    The adapter deliberately does not reshape steps, infer a missing graph, or
    reinterpret unsupported mathematics. That preserves the VLM/GT contract and
    makes unsupported inputs explicit as ``indeterminate``.
    """
    _validate_input(input_contract, repo_root)
    steps = input_contract["steps"]
    ambiguous = set(input_contract.get("reading", {}).get("ambiguous_step_ids", []))
    if ambiguous:
        return _indeterminate(input_contract, "CAS skipped because transcription is ambiguous")
    if len(steps) < 2:
        return _indeterminate(input_contract, "CAS requires at least two mathematical steps")
    if any(step["kind"] in {"note", "crossed_out"} for step in steps):
        return _indeterminate(input_contract, "CAS does not verify notes or crossed-out steps")
    expected_links = [[]] + [[steps[index - 1]["step_id"]] for index in range(1, len(steps))]
    if [step.get("derives_from", []) for step in steps] != expected_links:
        return _indeterminate(input_contract, "CAS currently supports only one linear chain of steps")

    started = perf_counter()
    result = verify_solution([step["latex"] for step in steps])
    duration_ms = round((perf_counter() - started) * 1000)
    if result["status"] == "UNSUPPORTED":
        output = _indeterminate(input_contract, result["reason"])
        output["pipeline"]["stages"][-1] = {
            "name": "verify", "backend": f"sympy@{sp.__version__}", "status": "ok", "duration_ms": duration_ms,
        }
        output["meta"]["duration_ms"] = duration_ms
        return output

    transition_by_step = {transition["step"]: transition for transition in result["transitions"]}
    findings: list[dict[str, Any]] = []
    reviewed: list[dict[str, Any]] = []
    for index, step in enumerate(steps, start=1):
        transition = transition_by_step.get(index)
        if index == 1 and result["first_error_step"] == 1:
            status, reason = "INVALID", "The initial constant equation is false"
        elif transition is None:
            status, reason = "VALID", "Trusted initial premise"
        else:
            status, reason = transition["status"], transition["reason"]
        if status == "INVALID":
            finding_id = f"f{len(findings) + 1}"
            findings.append({
                "finding_id": finding_id, "step_id": step["step_id"], "error_code": "algebra", "severity": "error",
                "message": "Символьная проверка не подтверждает переход к этому шагу.",
                "explanation": reason, "confidence": 1.0, "detected_by": "math_core",
                "evidence": {"check": reason, "actual_latex": step["latex"], "engine": "sympy"},
            })
            reviewed.append({"step_id": step["step_id"], "verdict": "error", "finding_ids": [finding_id]})
        else:
            reviewed.append({"step_id": step["step_id"], "verdict": "correct"})

    first_index = result["first_error_step"]
    verdict = "incorrect" if first_index else "correct"
    return {
        "schema_version": "1.0",
        "id": input_contract["id"],
        "pipeline": {
            "approach": "llm_ocr_plus_math_core",
            "stages": [_pipeline_stage(input_contract), {
                "name": "verify", "backend": f"sympy@{sp.__version__}", "status": "ok", "duration_ms": duration_ms,
            }],
        },
        **({"problem": input_contract["problem"]} if "problem" in input_contract else {}),
        "steps": steps,
        **({"reading": input_contract["reading"]} if "reading" in input_contract else {}),
        "verdict": verdict,
        "is_correct": verdict == "correct",
        "first_error_step": steps[first_index - 1]["step_id"] if first_index else None,
        "last_correct_step": steps[first_index - 2]["step_id"] if first_index and first_index > 1 else None,
        "findings": findings,
        "steps_reviewed": reviewed,
        "meta": {
            "run_id": f"cas-{uuid4()}", "approach": "llm_ocr_plus_math_core", "stage": "verify",
            "model": f"sympy@{sp.__version__}", "duration_ms": duration_ms, "created_at": _now(),
            "tool_versions": {"sympy": sp.__version__},
        },
    }
