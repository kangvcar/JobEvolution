import json

import pytest

from app.eval import adjudicate as adj


@pytest.fixture()
def eval_tmp(tmp_path, monkeypatch):
    skills = [
        {"id": "skill-a", "name": "Python", "synonyms": []},
        {"id": "skill-b", "name": "Docker", "synonyms": []},
        {"id": "skill-c", "name": "团队协作", "synonyms": []},
    ]
    (tmp_path / "skills.json").write_text(json.dumps(skills, ensure_ascii=False), encoding="utf-8")
    rows = [
        {
            "id": "jd-0001",
            "title": "Agent工程师",
            "text": "熟悉 Python，会用 Docker 部署。",
            "skills": [
                {"id": "skill-a", "kind": "required", "proficiency": None},
                {"id": "skill-c", "kind": "required", "proficiency": None},
            ],
            "notes": {"gold_draft": {"skills": ["Python", "Docker"]}},
        },
        {"id": "jd-0002", "title": "x", "text": "无", "skills": [], "notes": {"gold_draft": {"skills": []}}},
    ]
    (tmp_path / "jd.jsonl").write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8"
    )
    monkeypatch.setattr(adj, "eval_dir", lambda: tmp_path)
    adj._index_cache = None
    return tmp_path


def test_next_row_preps_suspects_and_proposals(eval_tmp):
    out = adj.next_row("jd")
    assert out["total"] == 2 and out["done"] == 0
    row = out["row"]
    assert [k["id"] for k in row["kept"]] == ["skill-a"]
    assert [s["id"] for s in row["suspects"]] == ["skill-c"]
    assert [p["skill_id"] for p in row["proposals"]] == ["skill-b"]
    assert row["unaligned"] == []


def test_next_row_keeps_full_source_text_and_path(eval_tmp):
    source = eval_tmp / "source.json"
    body = "原文 " * 500
    source.write_text(json.dumps({"body": body}, ensure_ascii=False), encoding="utf-8")
    rows = [
        {
            "id": "jd-source",
            "title": "官方岗位",
            "path": str(source),
            "skills": [],
            "notes": {"gold_draft": {"skills": []}},
        }
    ]
    (eval_tmp / "jd.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")

    row = adj.next_row("jd")["row"]

    assert row["text"] == body
    assert row["source_path"] == str(source)


def test_apply_decision_writes_row_and_advances(eval_tmp):
    out = adj.apply_decision(
        {
            "file": "jd",
            "row_id": "jd-0001",
            "deleted": ["skill-c"],
            "added": [{"skill_id": "skill-b", "span": "Docker"}],
        }
    )
    assert out["done"] == 1
    rows = [json.loads(line) for line in (eval_tmp / "jd.jsonl").read_text(encoding="utf-8").splitlines()]
    row = rows[0]
    assert [s["id"] for s in row["skills"]] == ["skill-a", "skill-b"]
    assert {"span": "Docker", "skill_id": "skill-b"} in row["mentions"]
    assert row["notes"]["adjudicated"]["deleted"] == ["skill-c"]
    assert adj.next_row("jd")["row"]["id"] == "jd-0002"


def test_apply_decision_skip_marks_done_without_changes(eval_tmp):
    adj.apply_decision({"file": "jd", "row_id": "jd-0001", "skip": True})
    rows = [json.loads(line) for line in (eval_tmp / "jd.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [s["id"] for s in rows[0]["skills"]] == ["skill-a", "skill-c"]
    assert rows[0]["notes"]["adjudicated"]["skipped"] is True
