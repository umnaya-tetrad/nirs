"""Reproducible, process-isolated 20-example feasibility check."""
import csv
from datetime import datetime, timezone
import hashlib
import json
import multiprocessing as mp
from pathlib import Path
import platform
import time

import sympy
from .verifier import verify_solution


def validate_dataset(data: dict) -> list[dict]:
    if not isinstance(data, dict) or data.get("kind") not in ("synthetic", "fermat_dev"):
        raise ValueError("Dataset kind must be synthetic or fermat_dev")
    examples = data.get("examples")
    if not isinstance(examples, list) or len(examples) != 20:
        raise ValueError("Freeze exactly 20 examples before running the feasibility experiment")
    ids, source_ids = set(), set()
    for example in examples:
        if not isinstance(example, dict):
            raise ValueError("Each example must be an object")
        identifier = example.get("id")
        if not isinstance(identifier, str) or not identifier or identifier in ids:
            raise ValueError("Example IDs must be nonempty, unique strings")
        ids.add(identifier)
        steps = example.get("steps")
        if not isinstance(steps, list) or len(steps) < 2:
            raise ValueError(f"{identifier}: supply at least two steps, including a trusted premise")
        if any(not isinstance(s, dict) or not isinstance(s.get("latex"), str) or not s["latex"].strip()
               for s in steps):
            raise ValueError(f"{identifier}: every step must contain a nonempty latex string")
        if data["kind"] == "fermat_dev":
            source_id = example.get("source_id")
            if example.get("split") != "dev" or not isinstance(source_id, str) or not source_id:
                raise ValueError(f"{identifier}: FERMAT requires source_id and split=dev")
            if source_id in source_ids:
                raise ValueError("Duplicate FERMAT source_id")
            source_ids.add(source_id)
        if "has_error" in example or "first_error_step" in example:
            if type(example.get("has_error")) is not bool or "first_error_step" not in example:
                raise ValueError(f"{identifier}: supply both has_error and first_error_step labels")
            first = example["first_error_step"]
            if example["has_error"]:
                if type(first) is not int or not 1 <= first <= len(steps):
                    raise ValueError(f"{identifier}: error label needs a one-based step index")
            elif first is not None:
                raise ValueError(f"{identifier}: correct solutions need first_error_step=null")
    return examples


def _worker(steps, connection):
    try:
        started = time.perf_counter()
        result = verify_solution(steps)
        result["latency_ms"] = round((time.perf_counter() - started) * 1000, 3)
        connection.send(result)
    except Exception as exc:
        connection.send({"status": "UNSUPPORTED", "covered": False, "parse_status": "NOT_MEASURED",
                         "has_error": None, "first_error_step": None, "parsed_steps": None,
                         "total_steps": len(steps), "transitions": [],
                         "reason": f"WORKER_ERROR: {type(exc).__name__}: {exc}", "latency_ms": None})
    finally:
        connection.close()


def run_isolated(steps: list[str], timeout: float = 10) -> dict:
    if timeout <= 0:
        raise ValueError("Timeout must be positive")
    context = mp.get_context("spawn")
    read, write = context.Pipe(duplex=False)
    process = context.Process(target=_worker, args=(steps, write))
    started = time.perf_counter()
    process.start()
    write.close()
    try:
        if read.poll(timeout):
            try:
                result = read.recv()
            except EOFError:
                result = None
        else:
            result = None
        if result is None:
            result = {"status": "UNSUPPORTED", "covered": False, "parse_status": "NOT_MEASURED",
                      "has_error": None, "first_error_step": None, "parsed_steps": None,
                      "total_steps": len(steps), "transitions": [], "reason": "TIMEOUT_OR_WORKER_EXIT",
                      "latency_ms": None}
    finally:
        if process.is_alive():
            process.terminate()
        process.join()
        read.close()
    result["wall_ms"] = round((time.perf_counter() - started) * 1000, 3)
    return result


def summarize(data: dict, rows: list[dict]) -> dict:
    total = len(rows)
    covered = sum(r["covered"] for r in rows)
    labelled = [r for r in rows if r["covered"] and "expected_has_error" in r]
    has_correct = sum(r["has_error"] == r["expected_has_error"] for r in labelled)
    first_correct = sum(r["first_error_step"] == r["expected_first_error_step"] for r in labelled)
    return {
        "examples": total, "covered_examples": covered, "coverage": covered / total,
        "parseable_examples": sum(r["parse_status"] == "OK" for r in rows),
        "parse_rate": sum(r["parse_status"] == "OK" for r in rows) / total,
        "threshold": 0.70, "required_covered": 14, "threshold_met": covered >= 14,
        "decision": ("GO" if covered >= 14 else "NO-GO") if data["kind"] == "fermat_dev" else "PRELIMINARY_ONLY",
        "labelled_covered_examples": len(labelled),
        "has_error_accuracy_on_covered": has_correct / len(labelled) if labelled else None,
        "first_error_accuracy_on_covered": first_correct / len(labelled) if labelled else None,
        "note": "Synthetic fixtures do not establish FERMAT feasibility. GO measures coverage, not grading accuracy.",
    }


def run_benchmark(dataset: Path, output: Path, timeout: float = 10) -> dict:
    raw = dataset.read_bytes()
    data = json.loads(raw.decode("utf-8-sig"))
    examples = validate_dataset(data)
    rows = []
    for example in examples:
        result = run_isolated([s["latex"] for s in example["steps"]], timeout)
        row = {"id": example["id"], **result}
        if "has_error" in example:
            row.update(expected_has_error=example["has_error"], expected_first_error_step=example["first_error_step"])
        rows.append(row)
    report = {"generated_at_utc": datetime.now(timezone.utc).isoformat(), "backend": "sympy",
              "sympy_version": sympy.__version__, "python_version": platform.python_version(),
              "dataset_kind": data["kind"], "dataset_name": data.get("name", dataset.name),
              "dataset_sha256": hashlib.sha256(raw).hexdigest(), "timeout_seconds": timeout,
              "summary": summarize(data, rows), "results": rows}
    output.mkdir(parents=True, exist_ok=True)
    (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    columns = ["id", "status", "parse_status", "covered", "has_error", "first_error_step", "latency_ms", "wall_ms"]
    with (output / "results.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    summary = report["summary"]
    lines = ["# Предварительная проверка CAS", "", f"Набор: {report['dataset_name']} ({data['kind']}).",
             f"Решение: **{summary['decision']}**.", "",
             f"Проверены: {summary['covered_examples']}/20; coverage: {summary['coverage']:.0%}.",
             f"Разобраны все шаги: {summary['parseable_examples']}/20. Порог: 14/20 (70%).", "",
             "Синтетический прогон проверяет реализацию. Итоговый GO/NO-GO требует 20 заранее выбранных dev-примеров FERMAT.",
             "Первое символьное равенство считается доверенным условием; правильность относительно текста задачи не проверяется.", "",
             "| ID | Разбор | Проверка | Первый ошибочный шаг |", "|---|---|---|---|"]
    lines += [f"| {r['id']} | {r['parse_status']} | {r['status']} | {r['first_error_step']} |" for r in rows]
    (output / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report
