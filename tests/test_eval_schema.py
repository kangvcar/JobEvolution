import json
from pathlib import Path

from app.eval.freeze import align_threshold, load_freeze
from app.eval.io import read_jsonl
from app.eval.paths import eval_dir

JD_MIN = 100
RESUME_MIN = 100
PAIR_MIN = 100
DOMAINS = {"ai", "data", "system", "iot"}


def _eval() -> Path:
    return eval_dir()


def test_freeze_json_and_ignores_env(monkeypatch):
    monkeypatch.setenv("ALIGN_THRESHOLD", "0.11")
    from app.eval import freeze as freeze_mod

    freeze_mod._cache = None
    data = load_freeze()
    assert data["align_threshold"] == 0.85
    assert align_threshold() == 0.85
    freeze_mod._cache = None


def test_jd_jsonl_schema_and_mix():
    rows = read_jsonl(_eval() / "jd.jsonl")
    assert len(rows) >= JD_MIN
    domains = {row.get("domain") for row in rows}
    assert DOMAINS <= domains
    by_domain = {}
    for row in rows:
        by_domain[row.get("domain")] = by_domain.get(row.get("domain"), 0) + 1
    assert by_domain.get("ai", 0) >= 40
    assert by_domain.get("data", 0) >= 12
    assert by_domain.get("system", 0) >= 12
    assert by_domain.get("iot", 0) >= 12
    names = [row.get("job_name") for row in rows]
    assert names.count("Agent 工程师") >= 8
    assert names.count("大模型应用工程师") >= 8
    for row in rows:
        assert "id" in row and "skills" in row and "text" in row
        for skill in row["skills"]:
            assert "id" in skill
        for mention in row.get("mentions") or []:
            assert mention.get("skill_id")
            assert mention.get("span")


def test_resume_jsonl_schema():
    rows = read_jsonl(_eval() / "resume.jsonl")
    assert len(rows) >= RESUME_MIN
    layouts = {row.get("layout") for row in rows}
    assert "split" in layouts
    for row in rows:
        assert row.get("text")
        assert isinstance(row.get("skills"), list)
        for skill in row["skills"]:
            assert "id" in skill


def test_deliver_has_real_fields_and_alias():
    root = _eval() / "deliver"
    agent = (root / "agent" / "io.md").read_text(encoding="utf-8")
    llm = (root / "llm-app" / "io.md").read_text(encoding="utf-8")
    assert "job_id" in agent and "Skill.id" in agent
    assert "valid_from" in agent or "REQUIRES" in agent
    assert "LLM 业务工程师" in llm
    assert "ALIAS_OF" in llm
    job = json.loads((root / "llm-app" / "job.json").read_text(encoding="utf-8"))
    assert job.get("id")
    assert (root / "agent" / "sources.jsonl").exists()
    assert (root / "llm-app" / "diagnose.example.json").exists()


def test_match_pairs_schema():
    rows = read_jsonl(_eval() / "match_pairs.jsonl")
    assert len(rows) >= PAIR_MIN
    for row in rows:
        assert "gap_ids" in row
        assert "requires" in row
        assert "resume_skills" in row
        assert isinstance(row["gap_ids"], list)
