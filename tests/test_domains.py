import json
from pathlib import Path

import pytest

from evaluator.domains import validate, write_csv_template


def _manifest(path: Path) -> Path:
    path.write_text(json.dumps({"cases": [{"id": "a", "image": "a.png"}, {"id": "b", "image": "b.png"}]}), encoding="utf-8")
    return path


def test_domain_sidecar_is_optional_and_validates_ids(tmp_path):
    manifest = _manifest(tmp_path / "manifest.json")
    sidecar = tmp_path / "domains.json"
    sidecar.write_text(json.dumps({"records": [{"solution_id": "a", "domain": "equation", "features": ["fractions"]}]}), encoding="utf-8")
    result = validate(sidecar, manifest)
    assert result["annotated"] == 1 and result["missing_ids"] == ["b"]
    with pytest.raises(ValueError, match="incomplete"):
        validate(sidecar, manifest, require_complete=True)
    write_csv_template(manifest, tmp_path / "template.csv")
    assert "solution_id" in (tmp_path / "template.csv").read_text(encoding="utf-8-sig")


def test_domain_sidecar_rejects_unknown_ids_and_features(tmp_path):
    manifest = _manifest(tmp_path / "manifest.json")
    sidecar = tmp_path / "domains.json"
    sidecar.write_text(json.dumps({"records": [{"solution_id": "missing", "domain": "equation", "features": ["bad"]}]}), encoding="utf-8")
    with pytest.raises(ValueError, match="not in the final manifest"):
        validate(sidecar, manifest)
