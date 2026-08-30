from app.eval.io import read_jsonl
from app.eval.paths import eval_dir
from app.eval.run import eval_jd, eval_match, eval_resume


def test_unmocked_three_items_read_freeze_not_env(monkeypatch, tmp_path):
    monkeypatch.setenv("ALIGN_THRESHOLD", "0.11")
    from app.eval import freeze as freeze_mod
    from app.eval import run as run_mod

    freeze_mod._cache = None
    monkeypatch.setattr(run_mod, "out_dir", lambda: tmp_path)
    items = list(read_jsonl(eval_dir() / "jd.jsonl"))

    def fake_complete_json(_schema, messages):
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
        return {"job_name": "岗", "domain": "ai", "skills": []}

    monkeypatch.setattr("app.llm.client.complete_json", fake_complete_json)
    jd = eval_jd(mock=False)
    resume = eval_resume(mock=False)
    match = eval_match(mock=False)
    assert jd["f1"] >= 0.90
    assert resume["f1"] >= 0.90
    assert match["f1"] >= 0.90
    assert not jd["mock"]


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
