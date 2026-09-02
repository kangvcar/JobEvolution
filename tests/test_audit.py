import json

from app.pipeline import audit


def test_audit_cli_writes_schema(tmp_path, monkeypatch):
    monkeypatch.setattr(audit, "build_audit", lambda: {"schema_version": "jobevolution.audit.v1", "jobs": []})
    output = tmp_path / "audit.json"
    assert audit.main(["--output", str(output)]) == 0
    assert json.loads(output.read_text(encoding="utf-8")) == {"schema_version": "jobevolution.audit.v1", "jobs": []}
