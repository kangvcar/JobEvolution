import os

from app.eval.run import eval_jd, eval_match, eval_resume


def test_unmocked_three_items_read_freeze_not_env(monkeypatch):
    monkeypatch.setenv("ALIGN_THRESHOLD", "0.11")
    from app.eval import freeze as freeze_mod

    freeze_mod._cache = None
    jd = eval_jd(mock=False)
    resume = eval_resume(mock=False)
    match = eval_match(mock=False)
    assert jd["f1"] >= 0.90
    assert resume["f1"] >= 0.90
    assert match["f1"] >= 0.90
    assert not jd["mock"]


def test_mock_three_items_pass_and_ignore_env(monkeypatch):
    monkeypatch.setenv("ALIGN_THRESHOLD", "0.11")
    from app.eval import freeze as freeze_mod

    freeze_mod._cache = None
    jd = eval_jd(mock=True)
    resume = eval_resume(mock=True)
    match = eval_match(mock=True)
    assert jd["f1"] >= 0.90
    assert resume["f1"] >= 0.90
    assert match["f1"] >= 0.90
    assert jd["n"] >= 100
    assert resume["n"] >= 100
    assert match["n"] >= 100
