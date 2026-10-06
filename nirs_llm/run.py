from __future__ import annotations

import argparse
import json
import mimetypes
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .client import GeminiPolzaClient
from .config import Settings
from .contracts import build_math_core_input, build_solution_analysis, validate_contract
from .prompts import prompt_for


def _cases(manifest_path: Path) -> list[dict[str, Any]]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    cases = manifest["cases"] if isinstance(manifest, dict) else manifest
    if not isinstance(cases, list):
        raise ValueError("Manifest must be an array or an object with a cases array.")
    result: list[dict[str, Any]] = []
    for case in cases:
        if not isinstance(case, dict) or not isinstance(case.get("id"), str) or not isinstance(case.get("image"), str):
            raise ValueError("Each case needs string id and image fields.")
        image_path = (manifest_path.parent / case["image"]).resolve()
        if not image_path.is_file():
            raise ValueError(f"Image does not exist: {image_path}")
        result.append({"id": case["id"], "path": image_path, "mime_type": case.get("mime_type")})
    return result


def run(mode: str, manifest: Path, output_dir: Path, repo_root: Path) -> list[Path]:
    prompt_version, _ = prompt_for(mode)
    settings = Settings.from_environment(repo_root / ".env")
    client = GeminiPolzaClient(settings)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = output_dir / f"{timestamp}_{mode}_{prompt_version}"
    run_dir.mkdir(parents=True, exist_ok=False)
    outputs: list[Path] = []
    for case in _cases(manifest):
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
        artifact = {"case_id": case["id"], "mode": mode, "prompt_version": prompt_version, "provider_model": response.provider_model, "usage": response.usage, "latency_ms": duration_ms, "raw_response": response.raw_content, "contract": contract}
        path = run_dir / f"{case['id']}.json"
        path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        outputs.append(path)
    return outputs


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the fixed Gemini NIRS baseline on a local manifest.")
    parser.add_argument("--mode", choices=("e2e", "extraction"), required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("outputs"))
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    paths = run(args.mode, args.manifest.resolve(), args.output_dir.resolve(), args.repo_root.resolve())
    print(f"Saved {len(paths)} result(s) to {paths[0].parent if paths else args.output_dir}")


if __name__ == "__main__":
    main()

