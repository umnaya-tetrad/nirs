from __future__ import annotations

import argparse
import json
import mimetypes
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .client import GeminiPolzaClient, PolzaInvalidResponseError, PolzaProviderError, PolzaUnavailableError
from .config import Settings
from .contracts import ContractError, build_math_core_input, build_solution_analysis, validate_contract
from .gigachat import GigaChatDirectClient, GigaChatProviderError, GigaChatUnavailableError
from .prompts import prompt_for


class RunFailedError(RuntimeError):
    """A fail-fast run stopped after saving the diagnostic artifact for its first failure."""


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


def run(
    mode: str,
    manifest: Path,
    output_dir: Path,
    repo_root: Path,
    *,
    provider: str = "gemini",
    fail_fast: bool = False,
    max_cases: int | None = None,
    skip_cases: int = 0,
) -> list[Path]:
    prompt_version, _ = prompt_for(mode, provider)
    settings = Settings.from_environment(repo_root / ".env")
    client = _client_for(provider, settings)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = output_dir / f"{timestamp}_{provider}_{mode}_{prompt_version}"
    run_dir.mkdir(parents=True, exist_ok=False)
    outputs: list[Path] = []
    cases = _cases(manifest)
    if skip_cases < 0:
        raise ValueError("skip_cases cannot be negative.")
    cases = cases[skip_cases:]
    if max_cases is not None:
        if max_cases < 1:
            raise ValueError("max_cases must be at least 1.")
        cases = cases[:max_cases]
    if not cases:
        raise ValueError("Manifest contains no cases to run.")
    for case in cases:
        response = None
        duration_ms = None
        try:
            mime_type = case["mime_type"] or mimetypes.guess_type(case["path"].name)[0] or "application/octet-stream"
            started = time.perf_counter()
            response = client.analyze(case["path"].read_bytes(), mime_type, mode)
            duration_ms = round((time.perf_counter() - started) * 1000)
            if mode == "e2e":
                contract = build_solution_analysis(case_id=case["id"], projection=response.content, model=response.provider_model or client.model, prompt_version=prompt_version, duration_ms=duration_ms, usage=response.usage)
                schema_name = "solution_analysis"
            else:
                contract = build_math_core_input(case_id=case["id"], projection=response.content, model=response.provider_model or client.model, prompt_version=prompt_version, duration_ms=duration_ms, usage=response.usage)
                schema_name = "math_core_input"
            validate_contract(contract, schema_name, repo_root)
            artifact = {"status": "ok", "case_id": case["id"], "mode": mode, "prompt_version": prompt_version, "provider_model": response.provider_model, "usage": response.usage, "latency_ms": duration_ms, "raw_response": response.raw_content, "contract": contract}
        except (PolzaUnavailableError, PolzaProviderError, PolzaInvalidResponseError, ContractError, GigaChatUnavailableError, GigaChatProviderError) as error:
            artifact = {
                "status": "error", "case_id": case["id"], "mode": mode, "prompt_version": prompt_version,
                "error_type": type(error).__name__, "error": str(error),
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
        path = run_dir / f"{case['id']}.json"
        path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        outputs.append(path)
        if artifact["status"] == "error" and fail_fast:
            raise RunFailedError(f"Stopped after {case['id']}: {artifact['error']}. Diagnostic: {path}")
    return outputs


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a fixed NIRS VLM baseline on a local manifest.")
    parser.add_argument("--provider", choices=("gemini", "gigachat"), default="gemini")
    parser.add_argument("--mode", choices=("e2e", "extraction"), required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("outputs"))
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--fail-fast", action="store_true", help="Stop with a non-zero exit after the first HTTP, JSON, or contract failure.")
    parser.add_argument("--max-cases", type=int, help="Run only this many manifest cases; use 1 for a paid smoke request.")
    parser.add_argument("--skip-cases", type=int, default=0, help="Skip already validated leading cases when resuming an interrupted run.")
    args = parser.parse_args()
    paths = run(
        args.mode, args.manifest.resolve(), args.output_dir.resolve(), args.repo_root.resolve(),
        provider=args.provider, fail_fast=args.fail_fast, max_cases=args.max_cases, skip_cases=args.skip_cases,
    )
    print(f"Saved {len(paths)} result(s) to {paths[0].parent if paths else args.output_dir}")


if __name__ == "__main__":
    main()

