"""Create a local, secret-free reproducibility archive for final-80 v2.

The archive is deliberately gitignored: it copies licensed images and raw API
responses so the evaluator can be rerun offline without another paid request.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import zipfile


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ARCHIVE = ROOT / "experiment_archive" / "final80_v2_2026-10-10"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _copy(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_environment() -> dict[str, Any]:
    from nirs_llm.config import Settings

    settings = Settings.from_environment(ROOT / ".env")
    return {
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "python": sys.version,
        "platform": platform.platform(),
        "providers": {
            "polza_configured": bool(settings.polza_api_key),
            "gigachat_configured": bool(settings.gigachat_authorization_key),
            "polza_base_url": settings.polza_base_url,
            "gigachat_base_url": settings.gigachat_base_url,
        },
        "secrets_included": False,
    }


def snapshot(destination: Path) -> None:
    manifest = ROOT / "evaluator/manifests/final80_v2_four_routes_template.json"
    dataset_manifest = ROOT / "dataset/manifests/fermat_final_80_v2.json"
    gt = ROOT / "dataset/final_gt_v2.json"
    config = destination / "00_config"
    images = destination / "01_images"
    config.mkdir(parents=True, exist_ok=True)
    for source in (manifest, dataset_manifest, gt, ROOT / "docs/experiment_runbook.md"):
        _copy(source, config / source.name)
    for provider in ("gemini", "gigachat"):
        for mode, version in (("e2e", "v1"), ("assisted_extraction", "v2")):
            source = ROOT / "prompts" / provider / mode / version
            target = config / "prompt_snapshots" / provider / mode / version
            shutil.copytree(source, target, dirs_exist_ok=True)
    cases = _json(dataset_manifest)["cases"]
    image_hashes: list[dict[str, str]] = []
    for case in cases:
        source = (dataset_manifest.parent / case["image"]).resolve()
        target = images / source.name
        _copy(source, target)
        image_hashes.append({"id": case["id"], "file": target.name, "sha256": _sha256(source)})
    (config / "environment.json").write_text(json.dumps(_safe_environment(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (config / "provenance.json").write_text(json.dumps({
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": _git_commit(), "image_sha256": image_hashes,
        "archive_policy": "raw artifacts retained locally; API keys and authorization headers excluded",
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (destination / "05_logs").mkdir(exist_ok=True)
    _status(destination, "RUNNING", {"stage": "configuration_snapshot_complete", "expected_logical_requests": 320})


def _git_commit() -> str | None:
    import subprocess
    result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else None


def _status(destination: Path, status: str, detail: dict[str, Any]) -> None:
    payload = {"updated_at_utc": datetime.now(timezone.utc).isoformat(), "status": status, **detail}
    (destination / "05_logs" / "experiment_status.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def collect(destination: Path, status: str) -> Path:
    mapping = {
        ROOT / "outputs/final80_v2/gemini-e2e": destination / "02_raw_vlm/gemini_e2e",
        ROOT / "outputs/final80_v2/gigachat-e2e": destination / "02_raw_vlm/gigachat_e2e",
        ROOT / "outputs/final80_v2-assisted/gemini-assisted-extraction": destination / "02_raw_vlm/gemini_assisted",
        ROOT / "outputs/final80_v2-assisted/gigachat-assisted-extraction": destination / "02_raw_vlm/gigachat_assisted",
        ROOT / "reports/final80_v2/assisted/gemini-assisted-cas": destination / "03_cas/gemini_assisted",
        ROOT / "reports/final80_v2/assisted/gigachat-assisted-cas": destination / "03_cas/gigachat_assisted",
        ROOT / "reports/final80_v2/four-routes-evaluation": destination / "04_evaluator",
    }
    copied = []
    for source, target in mapping.items():
        if source.exists():
            shutil.copytree(source, target, dirs_exist_ok=True)
            copied.append(str(source.relative_to(ROOT)))
    # Preserve the exact local evaluation implementation alongside the raw
    # inputs.  This makes metric regeneration possible without any provider
    # call and without relying on a moving branch tip.  Secrets are not part
    # of these source directories.
    source_snapshot = destination / "00_config" / "source_snapshot"
    for relative in ("evaluator", "nirs_llm", "nirs_cas"):
        source = ROOT / relative
        if source.exists():
            shutil.copytree(source, source_snapshot / relative, dirs_exist_ok=True,
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    for relative in ("pyproject.toml", "requirements.txt"):
        source = ROOT / relative
        if source.exists():
            _copy(source, source_snapshot / relative)
    (source_snapshot / "provenance.json").write_text(json.dumps({
        "git_commit": _git_commit(),
        "purpose": "offline evaluator/CAS result reproduction; no API credentials included",
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _status(destination, status, {"stage": "collection_complete", "copied_sources": copied})
    readme = destination / "README.md"
    readme.write_text(
        "# final-80 v2 experiment archive\n\n"
        "This local archive contains raw VLM artifacts, task-aware CAS outputs, evaluator reports and a source snapshot. "
        "It excludes API keys, authorization headers and access tokens. Re-run evaluator offline using 00_config/source_snapshot, "
        "02_raw_vlm, 03_cas and 04_evaluator inputs.\n",
        encoding="utf-8",
    )
    sums: list[str] = []
    for path in sorted(item for item in destination.rglob("*") if item.is_file() and item.name != "SHA256SUMS.txt"):
        sums.append(f"{_sha256(path)}  {path.relative_to(destination).as_posix()}")
    (destination / "SHA256SUMS.txt").write_text("\n".join(sums) + "\n", encoding="utf-8")
    zip_path = destination.with_suffix(".zip")
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in sorted(item for item in destination.rglob("*") if item.is_file()):
            archive.write(path, path.relative_to(destination.parent))
    return zip_path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("snapshot", "collect"))
    parser.add_argument("--archive", type=Path, default=DEFAULT_ARCHIVE)
    parser.add_argument("--status", default="SUCCESS")
    args = parser.parse_args()
    destination = args.archive.resolve()
    if args.command == "snapshot":
        snapshot(destination)
        print(destination)
    else:
        print(collect(destination, args.status))


if __name__ == "__main__":
    main()
