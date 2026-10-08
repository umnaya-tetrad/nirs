from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from jsonschema import Draft202012Validator
from referencing import Registry, Resource


class ContractError(ValueError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _run_meta(*, approach: str, stage: str, model: str, prompt_version: str, duration_ms: int, usage: dict[str, int | float]) -> dict[str, Any]:
    meta: dict[str, Any] = {
        "run_id": f"run-{uuid4()}",
        "approach": approach,
        "stage": stage,
        "model": model,
        "prompt_version": prompt_version,
        "temperature": 0,
        "duration_ms": duration_ms,
        "created_at": _now(),
    }
    for source, target in (("prompt_tokens", "tokens_in"), ("completion_tokens", "tokens_out")):
        if (value := _int_usage(usage, source)) is not None:
            meta[target] = value
    return meta


def _int_usage(usage: dict[str, int | float], name: str) -> int | None:
    value = usage.get(name)
    return int(value) if isinstance(value, (int, float)) else None


def _steps(raw_steps: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_steps, list) or not raw_steps:
        raise ContractError("Model response must contain a non-empty steps array.")
    steps: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_steps, start=1):
        if not isinstance(raw, dict) or not isinstance(raw.get("latex"), str) or not raw["latex"].strip():
            raise ContractError(f"steps[{index - 1}] must have non-empty latex.")
        expected_id = f"s{index}"
        step_id = raw.get("step_id", expected_id)
        if step_id != expected_id:
            raise ContractError(f"steps[{index - 1}].step_id must equal {expected_id}.")
        kind = raw.get("kind")
        if kind not in {"initial", "step", "conclusion", "answer", "note", "crossed_out"}:
            kind = "initial" if index == 1 else "step"
        step: dict[str, Any] = {"step_id": step_id, "kind": kind, "latex": raw["latex"].strip()}
        if index == 1:
            step["derives_from"] = []
        else:
            step["derives_from"] = [f"s{index - 1}"]
        steps.append(step)
    return steps


def build_solution_analysis(
    *,
    case_id: str,
    projection: dict[str, Any],
    model: str,
    prompt_version: str,
    duration_ms: int,
    usage: dict[str, int | float],
) -> dict[str, Any]:
    """Lift the deliberately small E2E projection into SolutionAnalysis."""
    if projection.get("schema_version") != prompt_version:
        raise ContractError("Unexpected E2E projection schema_version.")
    if not isinstance(projection.get("has_error"), bool):
        raise ContractError("has_error must be boolean.")
    steps = _steps(projection.get("steps"))
    first_error = projection.get("first_error_step")
    valid_ids = {step["step_id"] for step in steps}
    if projection["has_error"]:
        if first_error not in valid_ids:
            raise ContractError("first_error_step must name a returned step when has_error=true.")
        verdict, is_correct = "incorrect", False
    else:
        if first_error is not None:
            raise ContractError("first_error_step must be null when has_error=false.")
        verdict, is_correct, first_error = "correct", True, None
    position = next((i for i, step in enumerate(steps) if step["step_id"] == first_error), None)
    last_correct = steps[position - 1]["step_id"] if position and position > 0 else None
    stage: dict[str, Any] = {"name": "verify", "backend": model, "status": "ok", "duration_ms": duration_ms}
    for source, target in (("prompt_tokens", "tokens_in"), ("completion_tokens", "tokens_out")):
        if (value := _int_usage(usage, source)) is not None:
            stage[target] = value
    return {
        "schema_version": "1.0",
        "id": case_id,
        "pipeline": {"approach": "llm_end_to_end", "stages": [stage]},
        "steps": steps,
        "verdict": verdict,
        "is_correct": is_correct,
        "first_error_step": first_error,
        "last_correct_step": last_correct,
        # We intentionally do not ask the VLM for a narrative error report in P0.
        "findings": [],
        "meta": _run_meta(approach="llm_end_to_end", stage="verify", model=model, prompt_version=prompt_version, duration_ms=duration_ms, usage=usage),
    }


def build_math_core_input(
    *,
    case_id: str,
    projection: dict[str, Any],
    model: str,
    prompt_version: str,
    duration_ms: int,
    usage: dict[str, int | float],
) -> dict[str, Any]:
    """Lift a strictly visual transcription into MathCoreInput 2.0.

    The VLM may only return ordered LaTeX lines and IDs it could not read
    confidently.  The linear graph is deterministic orchestration metadata,
    not an inference made by the VLM.
    """
    if projection.get("schema_version") != prompt_version:
        raise ContractError("Unexpected extraction projection schema_version.")
    allowed_keys = {"schema_version", "steps", "ambiguous_step_ids"}
    unexpected = set(projection) - allowed_keys
    if unexpected:
        raise ContractError(f"Extraction response contains unsupported semantic fields: {', '.join(sorted(unexpected))}.")
    raw_steps = projection.get("steps")
    if not isinstance(raw_steps, list) or not raw_steps:
        raise ContractError("Model response must contain a non-empty steps array.")
    steps: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_steps, start=1):
        if not isinstance(raw, dict) or set(raw) != {"latex"}:
            raise ContractError(f"steps[{index - 1}] may only contain latex.")
        if not isinstance(raw.get("latex"), str) or not raw["latex"].strip():
            raise ContractError(f"steps[{index - 1}] must have non-empty latex.")
        expected_id = f"s{index}"
        steps.append({
            "step_id": expected_id,
            "kind": "initial" if index == 1 else "step",
            "latex": raw["latex"].strip(),
            "derives_from": [] if index == 1 else [f"s{index - 1}"],
        })
    ambiguous = projection.get("ambiguous_step_ids", [])
    valid_ids = {step["step_id"] for step in steps}
    if not isinstance(ambiguous, list) or any(item not in valid_ids for item in ambiguous):
        raise ContractError("ambiguous_step_ids must only contain returned step IDs.")
    return {
        "schema_version": "2.0",
        "id": case_id,
        "steps": steps,
        "reading": {"ambiguous_step_ids": ambiguous},
        "meta": _run_meta(approach="llm_ocr_plus_math_core", stage="transcribe", model=model, prompt_version=prompt_version, duration_ms=duration_ms, usage=usage),
    }


def validate_contract(contract: dict[str, Any], name: str, repo_root: Path) -> None:
    """Validate against the unmodified repository schemas with local reference resolution."""
    schemas_dir = repo_root / "data_contracts" / "schemas"
    math_schema = json.loads((schemas_dir / "math_core_input.schema.json").read_text(encoding="utf-8"))
    solution_schema = json.loads((schemas_dir / "solution_analysis.schema.json").read_text(encoding="utf-8"))
    schema = {"math_core_input": math_schema, "solution_analysis": solution_schema}[name]
    registry = Registry().with_resources([
        (math_schema["$id"], Resource.from_contents(math_schema)),
        (solution_schema["$id"], Resource.from_contents(solution_schema)),
    ])
    errors = sorted(Draft202012Validator(schema, registry=registry).iter_errors(contract), key=str)
    if errors:
        raise ContractError(f"{name} schema validation failed: {errors[0].message}")
