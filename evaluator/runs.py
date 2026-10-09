"""Load declared run sources into per-ID records with explicit failure statuses."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from nirs_llm.contracts import ContractError, validate_contract

from .evaluator import EvaluationInputError
from .manifest import ExperimentManifest, RunSpec

STATUS_OK = "ok"
STATUS_API_FAILED = "api_failed"
STATUS_INVALID_CONTRACT = "invalid_contract"
SCHEMA_ROOT = Path(__file__).resolve().parents[1]


@dataclass
class RunRecord:
    id: str
    status: str
    contract: dict[str, Any] | None = None
    error_type: str | None = None
    note: str | None = None
    vlm_latency_ms: int | None = None
    vlm_tokens_in: int | None = None
    vlm_tokens_out: int | None = None
    cas_latency_ms: int | None = None


@dataclass
class RunData:
    spec: RunSpec
    records: dict[str, RunRecord]
    id_set: set[str]
    unmapped: list[dict[str, Any]] = field(default_factory=list)
    provenance: dict[str, Any] = field(default_factory=dict)
    extraction: dict[str, dict[str, Any]] | None = None


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source_provenance(spec: RunSpec) -> dict[str, Any]:
    source = {"kind": spec.source_kind, "path": str(spec.source_path), "key": spec.source_key}
    if spec.source_kind == "runner_artifacts" and spec.source_path.is_dir():
        files = [{"path": path.name, "sha256": _file_sha256(path)}
                 for path in sorted(spec.source_path.glob("*.json"))]
        canonical = json.dumps(files, sort_keys=True, separators=(",", ":")).encode("utf-8")
        source.update(files=files, sha256=hashlib.sha256(canonical).hexdigest())
    else:
        source["sha256"] = _file_sha256(spec.source_path)
    return source


def _contract_sha256(contract: dict[str, Any]) -> str:
    canonical = json.dumps(contract, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(canonical).hexdigest()


def _read_json(path: Path) -> Any:
    return json.loads(path.read_bytes().decode("utf-8-sig"))


def _dotted(payload: Any, key: str) -> Any:
    current = payload
    for part in key.split("."):
        if not isinstance(current, dict) or part not in current:
            raise EvaluationInputError(f"json_key {key}: missing part {part}")
        current = current[part]
    return current


def _validated_sa(contract: Any) -> tuple[str | None, str | None]:
    try:
        validate_contract(contract, "solution_analysis", SCHEMA_ROOT)
        return None, None
    except ContractError as error:
        return STATUS_INVALID_CONTRACT, str(error)


def _int_or_none(value: Any) -> int | None:
    return int(value) if isinstance(value, (int, float)) else None


def _meta_usage(meta: Any) -> tuple[int | None, int | None, int | None]:
    if not isinstance(meta, dict):
        return None, None, None
    return _int_or_none(meta.get("duration_ms")), _int_or_none(meta.get("tokens_in")), _int_or_none(meta.get("tokens_out"))


def _record_from_sa(record: Any, repo_root: Path, index: int, unmapped: list[dict[str, Any]]) -> RunRecord | None:
    if not isinstance(record, dict):
        unmapped.append({"index": index, "reason": "record is not an object"})
        return None
    record_id = record.get("id")
    if not isinstance(record_id, str) or not record_id:
        unmapped.append({"index": index, "reason": "record needs a nonempty string id"})
        return None
    status, note = _validated_sa(record)
    if status is None:
        latency, tokens_in, tokens_out = _meta_usage(record.get("meta"))
        return RunRecord(id=record_id, status=STATUS_OK, contract=record,
                         vlm_latency_ms=latency, vlm_tokens_in=tokens_in, vlm_tokens_out=tokens_out)
    return RunRecord(id=record_id, status=STATUS_INVALID_CONTRACT, contract=record, note=note)


def _record_from_artifact(artifact: Any, repo_root: Path, index: int, unmapped: list[dict[str, Any]]) -> RunRecord | None:
    if not isinstance(artifact, dict):
        unmapped.append({"index": index, "reason": "artifact is not an object"})
        return None
    record_id = artifact.get("case_id") or artifact.get("id")
    if not isinstance(record_id, str) or not record_id:
        unmapped.append({"index": index, "reason": "artifact needs case_id"})
        return None
    if artifact.get("status") == STATUS_OK:
        contract = artifact.get("contract")
        status, note = _validated_sa(contract)
        usage = artifact.get("usage") if isinstance(artifact.get("usage"), dict) else {}
        latency = _int_or_none(artifact.get("latency_ms"))
        tokens_in = _int_or_none(usage.get("prompt_tokens"))
        tokens_out = _int_or_none(usage.get("completion_tokens"))
        if status is None:
            return RunRecord(id=record_id, status=STATUS_OK, contract=contract,
                             vlm_latency_ms=latency, vlm_tokens_in=tokens_in, vlm_tokens_out=tokens_out)
        return RunRecord(id=record_id, status=STATUS_INVALID_CONTRACT, note=note,
                         vlm_latency_ms=latency, vlm_tokens_in=tokens_in, vlm_tokens_out=tokens_out)
    error_type = artifact.get("error_type") or "UnknownError"
    status = STATUS_INVALID_CONTRACT if "Contract" in str(error_type) else STATUS_API_FAILED
    return RunRecord(id=record_id, status=status, error_type=str(error_type), note=artifact.get("error"))


def _load_array(path: Path, repo_root: Path, unmapped: list[dict[str, Any]], artifact_style: bool) -> dict[str, RunRecord]:
    payload = _read_json(path)
    if isinstance(payload, dict):
        payload = [payload]
    if not isinstance(payload, list):
        raise EvaluationInputError(f"{path}: expected an array of records")
    records: dict[str, RunRecord] = {}
    for index, item in enumerate(payload):
        record = _record_from_artifact(item, repo_root, index, unmapped) if artifact_style else _record_from_sa(item, repo_root, index, unmapped)
        if record is None:
            continue
        if record.id in records:
            raise EvaluationInputError(f"{path}: duplicate id {record.id}")
        records[record.id] = record
    return records


def _load_bundle(path: Path, repo_root: Path) -> dict[str, RunRecord]:
    payload = _read_json(path)
    if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
        raise EvaluationInputError(f"{path}: expected a frozen bundle with items")
    declared = payload.get("ids")
    if not isinstance(declared, list) or len(declared) != len(set(declared)):
        raise EvaluationInputError(f"{path}: bundle ids must be a unique array")
    records: dict[str, RunRecord] = {}
    for index, item in enumerate(payload["items"]):
        if not isinstance(item, dict) or not isinstance(item.get("contract"), dict):
            raise EvaluationInputError(f"{path}: items[{index}] must wrap a contract")
        contract = item["contract"]
        record_id = item.get("id") or contract.get("id")
        if not isinstance(record_id, str) or not record_id:
            raise EvaluationInputError(f"{path}: items[{index}] needs an id")
        digest = item.get("contract_sha256")
        if digest is not None and digest != _contract_sha256(contract):
            raise EvaluationInputError(f"{path}: items[{index}] contract_sha256 mismatch")
        status, note = _validated_sa(contract)
        if status is None:
            latency, tokens_in, tokens_out = _meta_usage(contract.get("meta"))
            records[record_id] = RunRecord(id=record_id, status=STATUS_OK, contract=contract,
                                           vlm_latency_ms=latency, vlm_tokens_in=tokens_in, vlm_tokens_out=tokens_out)
        else:
            records[record_id] = RunRecord(id=record_id, status=STATUS_INVALID_CONTRACT, contract=contract, note=note)
    missing_declared = set(declared) - set(records)
    if missing_declared:
        raise EvaluationInputError(f"{path}: declared ids without items: {sorted(missing_declared)}")
    return records


def _load_extraction(spec: RunSpec, repo_root: Path) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    assert spec.extraction_path is not None
    from nirs_cas.adapter import extract_step_latex
    path = spec.extraction_path
    contracts: dict[str, dict[str, Any]] = {}
    provenance: dict[str, Any]
    if spec.extraction_kind == "bundle":
        payload = _read_json(path)
        if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
            raise EvaluationInputError(f"{path}: expected a frozen extraction bundle")
        for index, item in enumerate(payload["items"]):
            contract = item.get("contract") if isinstance(item, dict) else None
            record_id = (item.get("id") or (contract or {}).get("id")) if isinstance(item, dict) else None
            if not isinstance(contract, dict) or not isinstance(record_id, str) or not record_id:
                raise EvaluationInputError(f"{path}: items[{index}] must wrap a contract with id")
            digest = item.get("contract_sha256")
            if digest is not None and digest != _contract_sha256(contract):
                raise EvaluationInputError(f"{path}: items[{index}] contract_sha256 mismatch")
            extract_step_latex(contract)
            contracts[record_id] = contract
        provenance = {"path": str(path), "sha256": _file_sha256(path)}
    else:
        records = _load_array(path, repo_root, [], artifact_style=True)
        for record in records.values():
            if record.status != STATUS_OK or not isinstance(record.contract, dict):
                raise EvaluationInputError(f"{path}: extraction artifact {record.id} is not a valid contract")
            extract_step_latex(record.contract)
            contracts[record.id] = record.contract
        provenance = {"path": str(path), "sha256": _file_sha256(path)}
    return contracts, provenance


def load_run(spec: RunSpec, manifest: ExperimentManifest, repo_root: Path) -> RunData:
    unmapped: list[dict[str, Any]] = []
    if spec.source_kind == "solution_analysis_array":
        records = _load_array(spec.source_path, repo_root, unmapped, artifact_style=False)
    elif spec.source_kind == "runner_artifacts":
        if spec.source_path.is_dir():
            records = {}
            for path in sorted(spec.source_path.glob("*.json")):
                for record_id, record in _load_array(path, repo_root, unmapped, artifact_style=True).items():
                    if record_id in records:
                        raise EvaluationInputError(f"{spec.source_path}: duplicate id {record_id}")
                    records[record_id] = record
        else:
            records = _load_array(spec.source_path, repo_root, unmapped, artifact_style=True)
    elif spec.source_kind == "bundle":
        records = _load_bundle(spec.source_path, repo_root)
    else:
        payload = _read_json(spec.source_path)
        selected = _dotted(payload, spec.source_key or "")
        if not isinstance(selected, list) or not selected:
            raise EvaluationInputError(f"{spec.source_path}: json_key {spec.source_key} must select a nonempty array")
        records = _load_array_from_records(selected, repo_root, unmapped)

    manifest_ids = set(manifest.ids)
    unknown = set(records) - manifest_ids
    if unknown:
        raise EvaluationInputError(f"run {spec.run_id}: ids absent from the manifest: {sorted(unknown)}")

    extraction = None
    provenance: dict[str, Any] = {"source": _source_provenance(spec)}
    if spec.extraction_path is not None:
        extraction, extraction_provenance = _load_extraction(spec, repo_root)
        unknown = set(extraction) - manifest_ids
        if unknown:
            raise EvaluationInputError(f"run {spec.run_id}: extraction ids absent from the manifest: {sorted(unknown)}")
        provenance["extraction_artifacts"] = extraction_provenance

    for record_id, record in records.items():
        if extraction is not None and record_id in extraction:
            latency, tokens_in, tokens_out = _meta_usage(extraction[record_id].get("meta"))
            record.vlm_latency_ms = record.vlm_latency_ms if record.vlm_latency_ms is not None else latency
            record.vlm_tokens_in = record.vlm_tokens_in if record.vlm_tokens_in is not None else tokens_in
            record.vlm_tokens_out = record.vlm_tokens_out if record.vlm_tokens_out is not None else tokens_out
        if record.status == STATUS_OK and isinstance(record.contract, dict):
            meta = record.contract.get("meta")
            if isinstance(meta, dict) and record.vlm_latency_ms is None and isinstance(meta.get("duration_ms"), (int, float)):
                record.vlm_latency_ms = int(meta["duration_ms"])
            record.cas_latency_ms = _int_or_none((meta or {}).get("duration_ms")) if record.contract.get("pipeline") else None

    return RunData(spec=spec, records=records, id_set=set(records), unmapped=unmapped,
                   provenance=provenance, extraction=extraction)


def _load_array_from_records(payload: list[Any], repo_root: Path, unmapped: list[dict[str, Any]]) -> dict[str, RunRecord]:
    records: dict[str, RunRecord] = {}
    for index, item in enumerate(payload):
        record = _record_from_sa(item, repo_root, index, unmapped)
        if record is None:
            continue
        if record.id in records:
            raise EvaluationInputError(f"duplicate id {record.id}")
        records[record.id] = record
    return records


def load_cas_on_gt(path: Path, ids: list[str]) -> dict[str, dict[str, Any]]:
    payload = _read_json(path)
    if not isinstance(payload, list):
        raise EvaluationInputError(f"{path}: cas_on_gt must be an array of SolutionAnalysis")
    by_id: dict[str, dict[str, Any]] = {}
    for record in payload:
        if not isinstance(record, dict) or not isinstance(record.get("id"), str):
            continue
        if record.get("verdict") not in ("correct", "incorrect", "indeterminate"):
            continue
        by_id[record["id"]] = record
    missing = [record_id for record_id in ids if record_id not in by_id]
    if missing:
        raise EvaluationInputError(f"{path}: cas_on_gt lacks ids {missing}")
    return {record_id: by_id[record_id] for record_id in ids}
