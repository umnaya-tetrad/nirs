"""Compose local, graph and task evidence without conflating their coverage."""

from __future__ import annotations
import copy
from dataclasses import asdict
import multiprocessing as mp
from time import perf_counter

from .contracts import analyze_contract
from .context_rules import check_context, ContextResult
from .graph_verifier import verify_graph
from .task_spec import compile_task_spec


def _evidence(spec):
    graph = verify_graph(spec)
    # Only proven definitions in the final answer's ancestor scope may
    # augment computational conditions. Sibling branches never contribute.
    context_spec = copy.deepcopy(spec)
    final = next(
        (s for s in reversed(spec["steps"]) if s.get("role") == "answer"),
        spec["steps"][-1],
    )
    source = {s["step_id"]: s for s in spec["steps"]}
    ancestors = set()
    pending = list(final.get("derives_from", []))
    while pending:
        sid = pending.pop()
        if sid in ancestors or sid not in source:
            continue
        ancestors.add(sid)
        pending.extend(source[sid].get("derives_from", []))
    statuses = {n["step_id"]: n["status"] for n in graph["nodes"]}
    for sid in ancestors:
        step = source[sid]
        if (
            step.get("role") == "definition"
            and statuses[sid] == "VALID"
            and step.get("branch", "main") in ("main", final.get("branch", "main"))
        ):
            context_spec["task"]["givens"].append(
                {"given_id": f"def_{sid}", "raw_latex": step["latex"], "parse": {}}
            )
    return graph, asdict(check_context(context_spec))


def _worker(spec, connection):
    try:
        connection.send(_evidence(spec))
    except Exception as exc:
        connection.send({"error": f"WORKER_ERROR: {type(exc).__name__}: {exc}"})
    finally:
        connection.close()


def isolated_evidence(spec, timeout):
    if timeout is None:
        return _evidence(spec)
    if timeout <= 0:
        raise ValueError("Timeout must be positive")
    ctx = mp.get_context("spawn")
    read, write = ctx.Pipe(duplex=False)
    process = ctx.Process(target=_worker, args=(spec, write))
    process.start()
    write.close()
    payload = None
    try:
        if read.poll(timeout):
            try:
                payload = read.recv()
            except EOFError:
                pass
    finally:
        read.close()
        if process.is_alive():
            process.terminate()
        process.join()
        process.close()
    if isinstance(payload, tuple):
        return payload
    reason = (
        payload.get("error") if isinstance(payload, dict) else "TIMEOUT_OR_WORKER_EXIT"
    )
    graph = {
        "covered": False,
        "first_error_step": None,
        "localization_blocked": True,
        "invalid_steps": [],
        "unsupported_steps": [s["step_id"] for s in spec["steps"]],
        "nodes": [
            {"step_id": s["step_id"], "status": "UNSUPPORTED", "reason": reason}
            for s in spec["steps"]
        ],
        "edges": [],
    }
    return graph, asdict(ContextResult("UNSUPPORTED", reason, rule="assisted_worker"))


def analyze_assisted(input_contract, repo_root=None, *, timeout=10, result=None):
    started = perf_counter()
    source = input_contract.get("contract", input_contract)
    spec = compile_task_spec(source)
    local = analyze_contract(source, timeout=timeout, result=result)
    graph, context = isolated_evidence(spec, timeout)
    output = copy.deepcopy(local)
    ids = [s["step_id"] for s in spec["steps"]]
    uncertain = any(s.get("exactness", "unknown") != "exact" for s in spec["steps"])
    uncertain = uncertain or any(
        c["parse"].get("status") != "OK" for c in spec["task"].get("constraints", [])
    )
    invalid_graph = any(
        any(
            token in r["reason"]
            for token in (
                "Dependency is missing",
                "given reference",
                "Unknown assisted role",
                "Unknown assisted branch",
                "Duplicate given IDs",
            )
        )
        for r in graph["nodes"]
    )
    context_invalid = context["status"] == "INVALID"
    undefined_input = any(
        "Substitution violates the expression domain" in r["reason"]
        or "Undefined substituted value" in r["reason"]
        for r in graph["nodes"]
    )
    context_valid = context["status"] == "VALID"
    candidates = list(graph["invalid_steps"])
    if context_invalid and context["step_id"] in ids:
        candidates.append(context["step_id"])
    first = min(candidates, key=ids.index) if candidates else None
    blocked = bool(
        first
        and any(ids.index(u) < ids.index(first) for u in graph["unsupported_steps"])
    )
    if uncertain or invalid_graph or undefined_input:
        blocked = True
    localized = first if first and not blocked else None
    full = graph["covered"] and not uncertain and not invalid_graph
    # Preserve proven ordinary evidence when context is merely unavailable.
    # A linear verdict across independent branches is not a graph proof.
    linear = all(
        s.get("branch", "main") == "main"
        and s.get("role") not in {"independent", "definition"}
        and s.get("derives_from") == [ids[i - 1]]
        for i, s in enumerate(spec["steps"])
        if i > 0
    )
    if uncertain or invalid_graph or undefined_input:
        verdict = "indeterminate"
    elif localized:
        verdict = "incorrect"
    elif (
        context["status"] == "UNSUPPORTED"
        and linear
        and local["verdict"] != "indeterminate"
    ):
        verdict = local["verdict"]
        localized = local["first_error_step"]
    elif candidates:
        verdict = "indeterminate"
    elif full and context_valid:
        verdict = "correct"
    elif local["verdict"] == "correct" and (linear or full):
        verdict = "correct"
    elif (
        local["verdict"] == "incorrect"
        and linear
        and context["status"] == "UNSUPPORTED"
    ):
        verdict = "incorrect"
        localized = local["first_error_step"]
    else:
        verdict = "indeterminate"
    output.update(
        verdict=verdict,
        is_correct=None if verdict == "indeterminate" else verdict == "correct",
        first_error_step=localized if verdict == "incorrect" else None,
        last_correct_step=ids[ids.index(localized) - 1]
        if verdict == "incorrect" and ids.index(localized) > 0
        else None,
    )
    output["findings"] = []
    output["steps_reviewed"] = []
    for review in graph["nodes"]:
        sid = review["step_id"]
        status = review["status"]
        if verdict == "incorrect" and sid == localized:
            reason = (
                review["reason"] if sid in graph["invalid_steps"] else context["reason"]
            )
            if not candidates and localized == local["first_error_step"]:
                reason = next(
                    (
                        f["explanation"]
                        for f in local["findings"]
                        if f["step_id"] == sid
                    ),
                    reason,
                )
            output["findings"].append(
                {
                    "finding_id": "f1",
                    "step_id": sid,
                    "error_code": "algebra",
                    "severity": "error",
                    "message": "Точная проверка обнаружила неверный шаг.",
                    "explanation": reason,
                    "confidence": 1.0,
                    "detected_by": "math_core",
                    "evidence": {
                        "check": reason,
                        "actual_latex": next(
                            s["latex"] for s in spec["steps"] if s["step_id"] == sid
                        ),
                        "engine": "sympy",
                    },
                }
            )
            output["steps_reviewed"].append(
                {"step_id": sid, "verdict": "error", "finding_ids": ["f1"]}
            )
        else:
            output["steps_reviewed"].append(
                {
                    "step_id": sid,
                    "verdict": "correct" if status == "VALID" else "indeterminate",
                    "note": review["reason"],
                }
            )
    context_check = {
        **context,
        "status": context["status"].lower(),
        "localization_blocked": blocked if context_invalid else False,
    }
    output["problem"] = {
        "task_spec": spec,
        "local_evidence": {
            k: local[k]
            for k in ("verdict", "first_error_step", "findings", "steps_reviewed")
        },
        "context_check": context_check,
        "graph_check": graph,
        "verified_solution_covered": full,
        "task_verified_solution_covered": full and context["status"] != "UNSUPPORTED",
        "fallback_reasons": [
            r["reason"] for r in graph["nodes"] if r["status"] == "UNSUPPORTED"
        ]
        + ([context["reason"]] if context["status"] == "UNSUPPORTED" else []),
    }
    approach = "llm_assisted_extraction_plus_math_core"
    output["pipeline"]["approach"] = approach
    output["pipeline"]["stages"].insert(
        0,
        {
            "name": "compile_task_spec",
            "backend": "nirs_cas.task_spec@1.0",
            "status": "ok",
        },
    )
    output["meta"].update(
        approach=approach,
        stage="verify",
        duration_ms=round((perf_counter() - started) * 1000),
    )
    if repo_root is not None:
        from nirs_llm.contracts import validate_contract

        validate_contract(output, "solution_analysis", repo_root)
    return output
