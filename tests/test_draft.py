import json
import threading
import time


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


def test_draft_continues_after_one_row_failure(monkeypatch, tmp_path):
    from app.eval import draft

    rows = [{"id": "jd-1", "text": "失败"}, {"id": "jd-2", "text": "成功"}]
    (tmp_path / "jd.jsonl").write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    monkeypatch.setattr(draft, "eval_dir", lambda: tmp_path)

    def fake_draft(row):
        if row["id"] == "jd-1":
            raise TimeoutError("temporary")
        return {**row, "notes": {"gold_draft": {"prompt": draft.PROMPT_VERSION, "skills": []}}}

    monkeypatch.setattr(draft, "_draft_one", fake_draft)
    result = draft._draft_file("jd.jsonl")

    assert result["failed"] == 1
    saved = [json.loads(line) for line in (tmp_path / "jd.jsonl").read_text(encoding="utf-8").splitlines()]
    assert "notes" not in saved[0]
    assert saved[1]["notes"]["gold_draft"]["prompt"] == draft.PROMPT_VERSION


def test_draft_runs_pending_rows_concurrently(monkeypatch, tmp_path):
    from app.eval import draft

    rows = [{"id": f"jd-{index}", "text": "待处理"} for index in range(4)]
    (tmp_path / "jd.jsonl").write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    monkeypatch.setattr(draft, "eval_dir", lambda: tmp_path)
    lock = threading.Lock()
    active = 0
    peak = 0

    def fake_draft(row):
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
        time.sleep(0.02)
        with lock:
            active -= 1
        return {**row, "notes": {"gold_draft": {"prompt": draft.PROMPT_VERSION, "skills": []}}}

    monkeypatch.setattr(draft, "_draft_one", fake_draft)
    result = draft._draft_file("jd.jsonl", workers=2)

    assert result["failed"] == 0
    assert peak == 2
