"""Experiment manifest: fixed ID list plus provenance-checked run declarations."""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .evaluator import EvaluationInputError

RUN_SYSTEMS = ("e2e", "extraction_cas", "assisted_cas")
RUN_MODES = ("e2e", "extraction", "assisted_extraction")
SOURCE_KINDS = ("solution_analysis_array", "runner_artifacts", "bundle", "json_key")


@dataclass(frozen=True)
class RunSpec:
    run_id: str
    system: str
    provider: str
    mode: str
    model: str | None
    prompt_version: str | None
    prompt_sha256: str | None
    git_commit: str | None
    timestamp: str | None
    simulated: bool
    source_kind: str
    source_path: Path
    source_key: str | None
    extraction_kind: str | None
    extraction_path: Path | None
    pricing: dict[str, float] | None


@dataclass(frozen=True)
class ExperimentManifest:
    manifest_version: str
    experiment_id: str
    evaluation_note: str
    split: str
    gt_paths: list[Path]
    ids: list[str]
    cas_on_gt_path: Path | None
    error_policy: dict[str, Any]
    runs: list[RunSpec]
    h1_pairs: list[dict[str, str]]
    path: Path


def _resolve(value: Any, repo_root: Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else (repo_root / path).resolve()


def _require_str(value: Any, field: str, where: str) -> str:
    if not isinstance(value, str) or not value:
        raise EvaluationInputError(f"{where}: {field} must be a nonempty string")
    return value


def _check_git_commit(commit: str, repo_root: Path) -> None:
    probe = subprocess.run(
        ["git", "cat-file", "-e", f"{commit}^{{commit}}"],
        cwd=repo_root, capture_output=True, text=True,
    )
    if probe.returncode != 0:
        raise EvaluationInputError(f"git_commit {commit} does not resolve in {repo_root}")


def _check_prompt_sha(spec_dict: dict[str, Any], where: str) -> None:
    from nirs_llm.prompts import load_prompt
    provider = spec_dict.get("provider")
    mode = spec_dict.get("mode")
    version = spec_dict.get("prompt_version")
    declared = spec_dict.get("prompt_sha256")
    if not declared:
        return
    if provider not in ("gemini", "gigachat") or mode not in RUN_MODES or not isinstance(version, str):
        raise EvaluationInputError(f"{where}: prompt_sha256 requires provider, mode and prompt_version")
    actual = load_prompt(mode, provider, version).sha256
    if actual != declared:
        raise EvaluationInputError(f"{where}: prompt_sha256 mismatch (recomputed {actual})")


def _source(raw: Any, field: str, where: str, repo_root: Path) -> tuple[str, Path, str | None]:
    if not isinstance(raw, dict):
        raise EvaluationInputError(f"{where}: {field} must be an object with kind and path")
    kind = _require_str(raw.get("kind"), f"{field}.kind", where)
    if kind not in SOURCE_KINDS:
        raise EvaluationInputError(f"{where}: unknown {field}.kind {kind}")
    path = _resolve(raw.get("path"), repo_root)
    if not path.exists():
        raise EvaluationInputError(f"{where}: {field} path does not exist: {path}")
    key = raw.get("key")
    if key is not None and (kind != "json_key" or not isinstance(key, str) or not key):
        raise EvaluationInputError(f"{where}: {field}.key is only valid for json_key sources")
    return kind, path, key


def _run_spec(raw: Any, index: int, repo_root: Path, manifest_path: Path) -> RunSpec:
    where = f"{manifest_path}: runs[{index}]"
    if not isinstance(raw, dict):
        raise EvaluationInputError(f"{where}: run must be an object")
    run_id = _require_str(raw.get("run_id"), "run_id", where)
    system = _require_str(raw.get("system"), "system", where)
    if system not in RUN_SYSTEMS:
        raise EvaluationInputError(f"{where}: unknown system {system}")
    provider = _require_str(raw.get("provider"), "provider", where)
    mode = _require_str(raw.get("mode"), "mode", where)
    if mode not in RUN_MODES:
        raise EvaluationInputError(f"{where}: unknown mode {mode}")
    expected_mode = {"e2e": "e2e", "extraction_cas": "extraction", "assisted_cas": "assisted_extraction"}[system]
    if mode != expected_mode:
        raise EvaluationInputError(f"{where}: system {system} requires mode {expected_mode}")
    _check_prompt_sha(raw, where)
    git_commit = raw.get("git_commit")
    if git_commit is not None:
        if not isinstance(git_commit, str) or not git_commit:
            raise EvaluationInputError(f"{where}: git_commit must be a nonempty string or null")
        _check_git_commit(git_commit, repo_root)
    source_kind, source_path, source_key = _source(raw.get("source"), "source", where, repo_root)
    extraction_kind = extraction_path = None
    extraction = raw.get("extraction_artifacts")
    if extraction is not None:
        extraction_kind, extraction_path, _ = _source(extraction, "extraction_artifacts", where, repo_root)
    pricing = raw.get("pricing")
    if pricing is not None:
        if not isinstance(pricing, dict) or set(pricing) != {"input_per_million", "output_per_million"}:
            raise EvaluationInputError(f"{where}: pricing needs input_per_million and output_per_million")
        pricing = {key: float(value) for key, value in pricing.items()}
    return RunSpec(
        run_id=run_id, system=system, provider=provider, mode=mode,
        model=raw.get("model"), prompt_version=raw.get("prompt_version"),
        prompt_sha256=raw.get("prompt_sha256"), git_commit=git_commit,
        timestamp=raw.get("timestamp"), simulated=bool(raw.get("simulated", False)),
        source_kind=source_kind, source_path=source_path, source_key=source_key,
        extraction_kind=extraction_kind, extraction_path=extraction_path, pricing=pricing,
    )


def load_manifest(path: Path, repo_root: Path | None = None) -> ExperimentManifest:
    repo_root = (repo_root or Path(__file__).resolve().parents[1]).resolve()
    path = path.resolve()
    payload = json.loads(path.read_bytes().decode("utf-8-sig"))
    if not isinstance(payload, dict):
        raise EvaluationInputError(f"{path}: manifest must be an object")
    if payload.get("manifest_version") != "1.0":
        raise EvaluationInputError(f"{path}: unsupported manifest_version")
    experiment_id = _require_str(payload.get("experiment_id"), "experiment_id", str(path))
    dataset = payload.get("dataset")
    if not isinstance(dataset, dict):
        raise EvaluationInputError(f"{path}: dataset section is required")
    ids = dataset.get("ids")
    if not isinstance(ids, list) or not ids or any(not isinstance(item, str) or not item for item in ids):
        raise EvaluationInputError(f"{path}: dataset.ids must be a nonempty list of strings")
    if len(ids) != len(set(ids)):
        raise EvaluationInputError(f"{path}: dataset.ids contains duplicates")
    gt_paths = dataset.get("gt_paths")
    if not isinstance(gt_paths, list) or not gt_paths:
        raise EvaluationInputError(f"{path}: dataset.gt_paths must be a nonempty list")
    gt_paths = [_resolve(item, repo_root) for item in gt_paths]
    for gt_path in gt_paths:
        if not gt_path.is_file():
            raise EvaluationInputError(f"{path}: GT file does not exist: {gt_path}")
    cas_on_gt = dataset.get("cas_on_gt")
    cas_on_gt_path = None
    if cas_on_gt is not None:
        cas_on_gt_path = _resolve(cas_on_gt.get("path"), repo_root)
        if not cas_on_gt_path.is_file():
            raise EvaluationInputError(f"{path}: cas_on_gt path does not exist: {cas_on_gt_path}")
    raw_runs = payload.get("runs")
    if not isinstance(raw_runs, list) or not raw_runs:
        raise EvaluationInputError(f"{path}: runs must be a nonempty list")
    runs = [_run_spec(raw, index, repo_root, path) for index, raw in enumerate(raw_runs)]
    run_ids = [spec.run_id for spec in runs]
    if len(run_ids) != len(set(run_ids)):
        raise EvaluationInputError(f"{path}: duplicate run_id")
    pairs = payload.get("h1_pairs")
    if not isinstance(pairs, list) or not pairs:
        raise EvaluationInputError(f"{path}: h1_pairs must be a nonempty list")
    by_id = {spec.run_id: spec for spec in runs}
    h1_pairs: list[dict[str, str]] = []
    for index, raw in enumerate(pairs):
        where = f"{path}: h1_pairs[{index}]"
        if not isinstance(raw, dict):
            raise EvaluationInputError(f"{where}: pair must be an object")
        provider = _require_str(raw.get("provider"), "provider", where)
        e2e_id = _require_str(raw.get("e2e_run"), "e2e_run", where)
        cas_id = _require_str(raw.get("cas_run"), "cas_run", where)
        if e2e_id not in by_id or cas_id not in by_id:
            raise EvaluationInputError(f"{where}: unknown run reference")
        e2e_spec, cas_spec = by_id[e2e_id], by_id[cas_id]
        if e2e_spec.system != "e2e":
            raise EvaluationInputError(f"{where}: e2e_run must have system=e2e")
        if cas_spec.system not in ("extraction_cas", "assisted_cas"):
            raise EvaluationInputError(f"{where}: cas_run must have system extraction_cas or assisted_cas")
        if e2e_spec.provider != provider or cas_spec.provider != provider:
            raise EvaluationInputError(f"{where}: both runs must belong to provider {provider}")
        h1_pairs.append({"provider": provider, "e2e_run": e2e_id, "cas_run": cas_id})
    return ExperimentManifest(
        manifest_version="1.0", experiment_id=experiment_id,
        evaluation_note=str(payload.get("evaluation_note", "")),
        split=str(dataset.get("split", "")), gt_paths=gt_paths, ids=list(ids),
        cas_on_gt_path=cas_on_gt_path,
        error_policy=payload.get("error_policy") if isinstance(payload.get("error_policy"), dict) else {},
        runs=runs, h1_pairs=h1_pairs, path=path,
    )
