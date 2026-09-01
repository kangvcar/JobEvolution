from app.eval.io import read_jsonl
from app.eval.paths import eval_dir
from app.eval.freeze import load_freeze
from app.eval.run import eval_jd, eval_match, eval_resume, write_summary


def test_unmocked_three_items_read_freeze_not_env(monkeypatch, tmp_path):
    monkeypatch.setenv("ALIGN_THRESHOLD", "0.11")
    from app.eval import freeze as freeze_mod
    from app.eval import run as run_mod

    freeze_mod._cache = None
    monkeypatch.setattr(run_mod, "out_dir", lambda: tmp_path)
    items = list(read_jsonl(eval_dir() / "jd.jsonl"))
    resumes = list(read_jsonl(eval_dir() / "resume.jsonl"))
    names = {row["id"]: row["name"] for row in run_mod._index()}

    def fake_complete_json(messages):
        content = (messages or [{}])[-1].get("content") or ""
        for item in items:
            text = item.get("text") or ""
            if text and text in content:
                title = item.get("title") or item.get("job_name") or "岗"
                skills = [
                    {
                        "name": row.get("name") or row.get("id"),
                        "kind": "required",
                        "section": "requirement",
                        "proficiency": "able",
                        "confidence": 0.9,
                        "excerpt": row.get("name") or "",
                    }
                    for row in (item.get("skills") or [])
                    if isinstance(row, dict)
                ]
                return {
                    "job_name": title,
                    "domain": item.get("domain") or "ai",
                    "skills": skills,
                }
        for item in resumes:
            if item.get("text") and item["text"] in content:
                if "experience" in messages[0]["content"]:
                    return {"experience": item["experience"], "education": item["education"]}
                return {"skills": [{"name": names[row["id"]]} for row in item["skills"]]}
        return {"job_name": "岗", "domain": "ai", "skills": []}

    monkeypatch.setattr("app.llm.client.complete_json", fake_complete_json)
    seen_thresholds = []
    real_align = run_mod.align_skill

    def spy_align(name, index, **kwargs):
        seen_thresholds.append(kwargs.get("threshold"))
        return real_align(name, index, **kwargs)

    monkeypatch.setattr(run_mod, "align_skill", spy_align)
    jd = eval_jd(mock=False)
    resume = eval_resume(mock=False)
    match = eval_match(mock=False)
    assert jd["f1"] >= 0.90
    assert resume["f1"] >= 0.90
    assert match["f1"] >= 0.90
    assert not jd["mock"]
    assert set(seen_thresholds) == {load_freeze()["align_threshold"]}


def test_mock_three_items_pass_and_ignore_env(monkeypatch, tmp_path):
    monkeypatch.setenv("ALIGN_THRESHOLD", "0.11")
    from app.eval import freeze as freeze_mod
    from app.eval import run as run_mod

    freeze_mod._cache = None
    monkeypatch.setattr(run_mod, "out_dir", lambda: tmp_path)
    jd = eval_jd(mock=True)
    resume = eval_resume(mock=True)
    match = eval_match(mock=True)
    assert jd["f1"] >= 0.90
    assert resume["f1"] >= 0.90
    assert match["f1"] >= 0.90
    assert jd["n"] >= 100
    assert resume["n"] >= 100
    assert match["n"] >= 100


def test_resume_eval_passes_frozen_threshold_to_parser(monkeypatch, tmp_path):
    from app.eval import freeze as freeze_mod
    from app.eval import run as run_mod

    calls = []

    def fake_parse(text, index, *, threshold=None, strict=False):
        calls.append(threshold)
        item = next(row for row in read_jsonl(eval_dir() / "resume.jsonl") if row["text"] == text)
        return {"skills": [{"skill_id": row["id"]} for row in item["skills"]]}

    freeze_mod._cache = None
    monkeypatch.setattr(run_mod, "out_dir", lambda: tmp_path)
    monkeypatch.setattr(run_mod, "parse_resume", fake_parse)
    assert eval_resume(mock=False)["f1"] == 1.0
    assert set(calls) == {load_freeze()["align_threshold"]}


def test_summary_records_unavailable_unmocked_tasks(monkeypatch, tmp_path):
    from app.eval import run as run_mod

    monkeypatch.setattr(run_mod, "out_dir", lambda: tmp_path)
    dest = write_summary(
        coverage=82.9,
        mock=False,
        results={"match": {"f1": 0.998, "n": 100}},
        errors={"jd": "APIStatusError: 402"},
        lows={"resume": "F1 0.477 < 0.90"},
    )
    text = dest.read_text(encoding="utf-8")
    assert "JD 未得真数" in text
    assert "RESUME 低于线  F1 0.477 < 0.90" in text
    assert "匹配 0.998" in text


def test_report_removes_stale_result_after_task_failure(monkeypatch, tmp_path):
    from app.eval import __main__ as cli
    from app.eval import run as run_mod

    (tmp_path / "jd.json").write_text('{"mock": true}', encoding="utf-8")
    monkeypatch.setattr(run_mod, "out_dir", lambda: tmp_path)
    monkeypatch.setattr(run_mod, "eval_jd", lambda **_: (_ for _ in ()).throw(RuntimeError("offline")))
    monkeypatch.setattr(run_mod, "eval_resume", lambda **_: {"f1": 1.0, "n": 1})
    monkeypatch.setattr(run_mod, "eval_match", lambda **_: {"f1": 1.0, "n": 1})
    monkeypatch.setattr(run_mod, "path_spotcheck", lambda: {"n": 0, "with_url": 0})
    assert cli.main(["report", "--coverage", "60"]) == 1
    assert not (tmp_path / "jd.json").exists()


def test_mock_eval_writes_checkpoints(monkeypatch, tmp_path):
    from app.eval import run as run_mod

    writes = []
    monkeypatch.setattr(run_mod, "out_dir", lambda: tmp_path)
    monkeypatch.setattr(run_mod, "write_json", lambda _path, payload: writes.append(payload.copy()))
    assert eval_jd(mock=True)["n"] == 100
    assert len(writes) > 1
    assert writes[0]["n"] < writes[-1]["n"] == 100


def test_single_eval_command_fails_for_low_f1(monkeypatch):
    from app.eval import __main__ as cli
    from app.eval import run as run_mod

    monkeypatch.setattr(run_mod, "eval_jd", lambda **_: {"f1": 0.5})
    assert cli.main(["jd"]) == 1
