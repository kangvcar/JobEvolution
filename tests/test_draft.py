import json


def test_draft_writes_each_row_and_resumes(monkeypatch, tmp_path):
    from app.eval import draft

    rows = [
        {"id": "jd-1", "text": "已有", "notes": {"gold_draft": {"prompt": draft.PROMPT_VERSION, "skills": []}}},
        {"id": "jd-2", "text": "待处理"},
    ]
    (tmp_path / "jd.jsonl").write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8"
    )
    monkeypatch.setattr(draft, "eval_dir", lambda: tmp_path)
    monkeypatch.setattr(
        draft,
        "_draft_one",
        lambda row: {**row, "notes": {"gold_draft": {"prompt": draft.PROMPT_VERSION, "skills": ["Python"]}}},
    )

    result = draft._draft_file("jd.jsonl")

    assert result["rows"] == 2
    saved = [json.loads(line) for line in (tmp_path / "jd.jsonl").read_text(encoding="utf-8").splitlines()]
    assert all(row["notes"]["gold_draft"]["prompt"] == draft.PROMPT_VERSION for row in saved)
    checkpoint = json.loads((tmp_path / draft.CHECKPOINT_FILE).read_text(encoding="utf-8"))
    assert checkpoint["status"] == "done"
    assert checkpoint["completed"] == 2
