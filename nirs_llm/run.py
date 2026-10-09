from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import re
import random
import subprocess

from .client import GeminiPolzaClient, PolzaInvalidResponseError, PolzaProviderError, PolzaUnavailableError
from .config import Settings
from .contracts import ContractError, build_llm_assisted_extraction, build_math_core_input, build_solution_analysis, validate_contract
from .gigachat import GigaChatDirectClient, GigaChatProviderError, GigaChatUnavailableError
from .prompts import load_prompt


class RunFailedError(RuntimeError):
    """A fail-fast run stopped after saving the diagnostic artifact for its first failure."""


DEFAULT_GEMINI_WORKERS = 2
DEFAULT_MAX_ATTEMPTS = 3
RETRY_BASE_DELAY_SECONDS = 1.0
RETRY_MAX_DELAY_SECONDS = 30.0
PROVIDER_COOLDOWN_AFTER_CONSECUTIVE_FAILURES = 3
PROVIDER_COOLDOWN_SECONDS = 60.0


def _cases(manifest_path: Path) -> list[dict[str, Any]]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    cases = manifest["cases"] if isinstance(manifest, dict) else manifest
    if not isinstance(cases, list):
        raise ValueError("Manifest must be an array or an object with a cases array.")
    result: list[dict[str, Any]] = []
    for case in cases:
        if not isinstance(case, dict):
            raise ValueError("Each case must be an object.")
        # The generic DevSet format uses id/image; the current llmJsonTest
        # manifest carries dataset metadata under case_id/filename.
        case_id = case.get("id", case.get("case_id"))
        filename = case.get("image", case.get("filename"))
        if not isinstance(case_id, str) or not isinstance(filename, str):
            raise ValueError("Each case needs id/image or case_id/filename string fields.")
        image_path = (manifest_path.parent / filename).resolve()
        if not image_path.is_file():
            raise ValueError(f"Image does not exist: {image_path}")
        result.append({"id": case_id, "path": image_path, "mime_type": case.get("mime_type")})
    return result


def _client_for(provider: str, settings: Settings):
    if provider == "gemini":
        return GeminiPolzaClient(settings)
    if provider == "gigachat":
        return GigaChatDirectClient(settings)
    raise ValueError(f"Unknown provider: {provider}")


def _load_case_ids(path: Path) -> set[str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    ids = payload.get("ids") if isinstance(payload, dict) else payload
    if not isinstance(ids, list) or not all(isinstance(case_id, str) and case_id for case_id in ids):
        raise ValueError("Case-ID file must be a JSON array of non-empty strings or an object with an ids array.")
    if len(ids) != len(set(ids)):
        raise ValueError("Case-ID file contains duplicate IDs.")
    return set(ids)


def _select_cases(cases: list[dict[str, Any]], case_ids: set[str] | None) -> list[dict[str, Any]]:
    if case_ids is None:
        return cases
    found = {case["id"] for case in cases}
    unknown = sorted(case_ids - found)
    if unknown:
        raise ValueError(f"Case-ID file contains IDs absent from the manifest: {', '.join(unknown)}")
    return [case for case in cases if case["id"] in case_ids]


def _worker_count(provider: str, requested: int | None) -> int:
    if requested is not None and requested < 1:
        raise ValueError("workers must be at least 1.")
    if provider == "gigachat":
        if requested not in (None, 1):
            raise ValueError("GigaChat runs must use exactly one worker.")
        return 1
    if provider == "gemini":
        return requested or DEFAULT_GEMINI_WORKERS
    raise ValueError(f"Unknown provider: {provider}")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_commit(repo_root: Path) -> str | None:
    result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo_root, capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 and result.stdout.strip() else None


def _validate_saved(path: Path, case_id: str, provider: str, mode: str, prompt_version: str) -> None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Cannot resume: invalid saved artifact {path}") from error
    if not isinstance(payload, dict) or payload.get("case_id") != case_id:
        raise ValueError(f"Cannot resume: {path} does not belong to {case_id}")
    if (payload.get("provider"), payload.get("mode"), payload.get("prompt_version")) != (provider, mode, prompt_version):
        raise ValueError(f"Cannot resume: {path} belongs to a different provider, mode, or prompt version")


def _is_retryable(error: Exception) -> bool:
    """Retry transport failures and transient HTTP statuses, never bad model JSON or contracts."""
    if isinstance(error, (PolzaProviderError, GigaChatProviderError)):
        return error.status_code == 408 or error.status_code == 429 or error.status_code >= 500
    if isinstance(error, (PolzaUnavailableError, GigaChatUnavailableError)):
        message = str(error).lower()
        return "not configured" not in message and "empty image" not in message
    return False


def _retry_delay(error: Exception, attempt: int) -> float:
    """Bounded exponential backoff with provider Retry-After and jitter."""
    requested = getattr(error, "retry_after_seconds", None)
    base = requested if isinstance(requested, (int, float)) else RETRY_BASE_DELAY_SECONDS * (2 ** (attempt - 1))
    return round(min(RETRY_MAX_DELAY_SECONDS, max(0.0, base)) + random.uniform(0.0, 0.25), 3)


def _run_case(
    case: dict[str, Any], *, client: Any, mode: str, provider: str, prompt: Any, repo_root: Path,
    max_attempts: int,
) -> dict[str, Any]:
    response = None
    duration_ms = None
    retry_errors: list[dict[str, Any]] = []
    try:
        mime_type = case["mime_type"] or mimetypes.guess_type(case["path"].name)[0] or "application/octet-stream"
        image_bytes = case["path"].read_bytes()
        for attempt in range(1, max_attempts + 1):
            started = time.perf_counter()
            try:
                response = client.analyze(image_bytes, mime_type, mode, prompt.version)
                duration_ms = round((time.perf_counter() - started) * 1000)
                break
            except (PolzaUnavailableError, PolzaProviderError, GigaChatUnavailableError, GigaChatProviderError) as error:
                duration_ms = round((time.perf_counter() - started) * 1000)
                if not _is_retryable(error) or attempt == max_attempts:
                    raise
                delay = _retry_delay(error, attempt)
                retry_errors.append({"attempt": attempt, "error_type": type(error).__name__, "error": str(error), "retry_delay_seconds": delay})
                time.sleep(delay)
        if response is None:
            raise RuntimeError("Retry loop completed without a response.")
        if mode == "e2e":
            contract = build_solution_analysis(case_id=case["id"], projection=response.content, model=response.provider_model or client.model, prompt_version=prompt.schema_version, duration_ms=duration_ms, usage=response.usage)
            schema_name = "solution_analysis"
        elif mode == "assisted_extraction":
            contract = build_llm_assisted_extraction(case_id=case["id"], projection=response.content, model=response.provider_model or client.model, prompt_version=prompt.schema_version, duration_ms=duration_ms, usage=response.usage)
            schema_name = "llm_assisted_extraction"
        else:
            contract = build_math_core_input(case_id=case["id"], projection=response.content, model=response.provider_model or client.model, prompt_version=prompt.schema_version, duration_ms=duration_ms, usage=response.usage)
            schema_name = "math_core_input"
        validate_contract(contract, schema_name, repo_root)
        return {"status": "ok", "case_id": case["id"], "mode": mode, "prompt_version": prompt.version, "provider": provider, "prompt": prompt.artifact(), "provider_model": response.provider_model, "usage": response.usage, "latency_ms": duration_ms, "attempts": len(retry_errors) + 1, **({"retry_errors": retry_errors} if retry_errors else {}), "raw_response": response.raw_content, "contract": contract}
    except (PolzaUnavailableError, PolzaProviderError, PolzaInvalidResponseError, ContractError, GigaChatUnavailableError, GigaChatProviderError) as error:
        artifact: dict[str, Any] = {
            "status": "error", "case_id": case["id"], "mode": mode, "prompt_version": prompt.version,
            "provider": provider, "prompt": prompt.artifact(), "error_type": type(error).__name__, "error": str(error),
            "attempts": len(retry_errors) + 1, **({"retry_errors": retry_errors} if retry_errors else {}),
        }
        if isinstance(error, PolzaInvalidResponseError) and error.raw_content is not None:
            artifact["raw_response"] = error.raw_content
        # A contract failure happens after a successful model response. Preserve it
        # for one-case diagnostics rather than losing the evidence that caused a stop.
        if response is not None:
            artifact["provider_model"] = response.provider_model
            artifact["usage"] = response.usage
            artifact["latency_ms"] = duration_ms
            artifact["raw_response"] = response.raw_content
        return artifact


def run(
    mode: str,
    manifest: Path,
    output_dir: Path,
    repo_root: Path,
    *,
    provider: str = "gemini",
    prompt_version: str | None = None,
    case_ids: set[str] | None = None,
    workers: int | None = None,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    fail_fast: bool = False,
    max_cases: int | None = None,
    skip_cases: int = 0,
    run_name: str | None = None,
    resume: bool = False,
) -> list[Path]:
    prompt = load_prompt(mode, provider, prompt_version)
    settings = Settings.from_environment(repo_root / ".env")
    client = _client_for(provider, settings)
    resolved_workers = _worker_count(provider, workers)
    if fail_fast and resolved_workers != 1:
        raise ValueError("fail_fast requires workers=1 because parallel requests cannot be cancelled safely.")
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1.")
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    if run_name is not None and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", run_name):
        raise ValueError("run_name must contain only letters, digits, dot, underscore or hyphen.")
    if resume and run_name is None:
        raise ValueError("resume requires an explicit run_name.")
    run_dir = output_dir / (run_name or f"{timestamp}_{provider}_{mode}_{prompt.schema_version}")
    cases = _select_cases(_cases(manifest), case_ids)
    if skip_cases < 0:
        raise ValueError("skip_cases cannot be negative.")
    cases = cases[skip_cases:]
    if max_cases is not None:
        if max_cases < 1:
            raise ValueError("max_cases must be at least 1.")
        cases = cases[:max_cases]
    if not cases:
        raise ValueError("Manifest contains no cases to run.")
    metadata_path = run_dir / "run_metadata.json"
    if run_dir.exists():
        if not resume:
            raise FileExistsError(f"Run directory already exists: {run_dir}. Use --resume to avoid duplicate requests.")
        if not metadata_path.is_file():
            raise ValueError(f"Cannot resume: missing {metadata_path}")
    else:
        run_dir.mkdir(parents=True, exist_ok=False)
        metadata_path.write_text(json.dumps({
            "artifact_version": "1.0", "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "provider": provider, "mode": mode, "model": client.model, "prompt": prompt.artifact(),
            "git_commit": _git_commit(repo_root),
            "dataset_manifest": {"path": str(manifest), "sha256": _sha256(manifest), "ids": [case["id"] for case in cases]},
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    completed: dict[str, Path] = {}
    prior_failures: dict[str, list[dict[str, Any]]] = {}
    if resume:
        for case in cases:
            path = run_dir / f"{case['id']}.json"
            if path.is_file():
                _validate_saved(path, case["id"], provider, mode, prompt.version)
                saved = json.loads(path.read_text(encoding="utf-8"))
                if saved.get("status") == "ok":
                    completed[case["id"]] = path
                else:
                    prior_failures[case["id"]] = [{
                        "error_type": saved.get("error_type"), "error": saved.get("error"),
                        "attempts": saved.get("attempts"), "retry_errors": saved.get("retry_errors", []),
                    }]
    pending = [case for case in cases if case["id"] not in completed]
    outputs: list[Path] = list(completed.values())
    def save(case: dict[str, Any], artifact: dict[str, Any]) -> Path:
        if case["id"] in prior_failures:
            artifact["prior_failures"] = prior_failures[case["id"]]
        path = run_dir / f"{case['id']}.json"
        path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        outputs.append(path)
        return path

    def finalize_metadata() -> None:
        artifacts: list[dict[str, Any]] = []
        for case in cases:
            path = run_dir / f"{case['id']}.json"
            if not path.is_file():
                artifacts.append({"case_id": case["id"], "status": "not_attempted"})
                continue
            try:
                saved = json.loads(path.read_text(encoding="utf-8"))
                artifacts.append({"case_id": case["id"], "status": saved.get("status", "invalid_artifact"),
                                  "error_type": saved.get("error_type"), "error": saved.get("error")})
            except (OSError, json.JSONDecodeError):
                artifacts.append({"case_id": case["id"], "status": "invalid_artifact"})
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        metadata["last_updated_utc"] = datetime.now(timezone.utc).isoformat()
        metadata["completion"] = {
            "expected": len(cases), "successful": sum(item["status"] == "ok" for item in artifacts),
            "failed": sum(item["status"] == "error" for item in artifacts),
            "not_attempted": sum(item["status"] == "not_attempted" for item in artifacts), "artifacts": artifacts,
        }
        metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # Serial persistence is intentional: every completed request is durable before
    # another potentially billable request starts.  ``workers`` is retained for
    # compatibility but experiments use one worker to make resume unambiguous.
    consecutive_transient_failures = 0
    for case in pending:
        if consecutive_transient_failures >= PROVIDER_COOLDOWN_AFTER_CONSECUTIVE_FAILURES:
            time.sleep(PROVIDER_COOLDOWN_SECONDS)
            consecutive_transient_failures = 0
        artifact = _run_case(case, client=client, mode=mode, provider=provider, prompt=prompt,
                             repo_root=repo_root, max_attempts=max_attempts)
        path = save(case, artifact)
        if artifact["status"] == "error":
            transient = artifact.get("error_type") in {"PolzaUnavailableError", "PolzaProviderError", "GigaChatUnavailableError", "GigaChatProviderError"}
            consecutive_transient_failures = consecutive_transient_failures + 1 if transient else 0
            if fail_fast:
                finalize_metadata()
                raise RunFailedError(f"Stopped after {case['id']}: {artifact['error']}. Diagnostic: {path}")
        else:
            consecutive_transient_failures = 0
    finalize_metadata()
    return [run_dir / f"{case['id']}.json" for case in cases]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a fixed NIRS VLM baseline on a local manifest.")
    parser.add_argument("--provider", choices=("gemini", "gigachat"), default="gemini")
    parser.add_argument("--mode", choices=("e2e", "extraction", "assisted_extraction"), required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("outputs"))
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--prompt-version", help="Prompt artifact version, for example v1 or v2.")
    parser.add_argument("--case-ids-file", type=Path, help="JSON list (or {ids: [...]}) limiting the run to selected manifest IDs.")
    parser.add_argument("--workers", type=int, help="Gemini parallel requests (default: 2). GigaChat requires 1.")
    parser.add_argument("--max-attempts", type=int, default=DEFAULT_MAX_ATTEMPTS, help="Attempts for temporary network/5xx/429 failures (default: 3).")
    parser.add_argument("--fail-fast", action="store_true", help="Stop with a non-zero exit after the first HTTP, JSON, or contract failure.")
    parser.add_argument("--max-cases", type=int, help="Run only this many manifest cases; use 1 for a paid smoke request.")
    parser.add_argument("--skip-cases", type=int, default=0, help="Skip already validated leading cases when resuming an interrupted run.")
    parser.add_argument("--run-name", help="Stable subdirectory name for a reproducible run; must not already exist.")
    parser.add_argument("--resume", action="store_true", help="Reuse saved artifacts under --run-name and request only missing IDs.")
    args = parser.parse_args()
    paths = run(
        args.mode, args.manifest.resolve(), args.output_dir.resolve(), args.repo_root.resolve(),
        provider=args.provider, prompt_version=args.prompt_version,
        case_ids=_load_case_ids(args.case_ids_file.resolve()) if args.case_ids_file else None,
        workers=args.workers,
        max_attempts=args.max_attempts,
        fail_fast=args.fail_fast, max_cases=args.max_cases, skip_cases=args.skip_cases,
        run_name=args.run_name,
        resume=args.resume,
    )
    print(f"Saved {len(paths)} result(s) to {paths[0].parent if paths else args.output_dir}")


if __name__ == "__main__":
    main()
