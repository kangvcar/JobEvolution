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
    expected = float(json.loads((_eval() / "freeze.json").read_text(encoding="utf-8"))["align_threshold"])
    data = load_freeze()
    assert data["align_threshold"] == expected
    assert align_threshold() == expected
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
    assert by_domain.get("iot", 0) >= 10
    names = [row.get("job_name") for row in rows]
    assert "Agent 工程师" in names
    assert "大模型应用工程师" in names
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


def test_deliver_has_real_graph_fields():
    root = _eval() / "deliver"
    agent = (root / "agent" / "io.md").read_text(encoding="utf-8")
    llm = (root / "llm-app" / "io.md").read_text(encoding="utf-8")
    assert "job_id" in agent and "Skill.id" in agent
    assert "valid_from" in agent or "REQUIRES" in agent
    assert "EvolutionEvent" in agent and "EvolutionEvent" in llm
    job = json.loads((root / "llm-app" / "job.json").read_text(encoding="utf-8"))
    assert job.get("id") and job.get("name") == "大模型应用工程师"
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


def test_gold_gap_set_counts_half_level_shortfall():
    from app.eval.gold import _gap_ids

    requires = [
        {"skill_id": "s1", "kind": "required", "proficiency": "expert"},
        {"skill_id": "s2", "kind": "required", "proficiency": "able"},
        {"skill_id": "s3", "kind": "required", "proficiency": "able"},
        {"skill_id": "s4", "kind": "bonus", "proficiency": "aware"},
        {"skill_id": "s5", "kind": "required", "proficiency": "able"},
        {"skill_id": "s1", "kind": "required", "proficiency": "expert"},
    ]
    resume = [
        {"skill_id": "s1", "proficiency": "able"},
        {"skill_id": "s2", "proficiency": None},
        {"skill_id": "s3", "proficiency": "able"},
        {"skill_id": "s4", "proficiency": "aware"},
    ]
    assert _gap_ids(requires, resume) == ["s1", "s5"]
    assert _gap_ids(requires, []) == ["s1", "s2", "s3", "s5"]


def test_gold_build_does_not_call_compare_job(monkeypatch, tmp_path):
    from app.eval import gold

    assert not hasattr(gold, "compare_job")
    monkeypatch.setattr(gold, "eval_dir", lambda: tmp_path)
    monkeypatch.setattr(gold, "compare_job", lambda *_: (_ for _ in ()).throw(AssertionError("not gold")), raising=False)
    gold.build_gold(
        index=[
            {"id": "s1", "name": "Python", "synonyms": []},
            {"id": "s2", "name": "FastAPI", "synonyms": []},
            {"id": "s3", "name": "Neo4j", "synonyms": []},
            {"id": "s4", "name": "RAG", "synonyms": []},
        ],
        jobs=[
            {
                "id": "job-1",
                "name": "测试岗",
                "requires": [{"skill_id": "s1", "name": "Python", "kind": "required", "proficiency": "able"}],
            }
        ],
    )
    rows = read_jsonl(tmp_path / "match_pairs.jsonl")
    assert len(rows) == 100


def test_eval_dir_honors_isolated_directory(monkeypatch, tmp_path):
    from app.eval import paths

    monkeypatch.setenv("EVAL_DIR", str(tmp_path))
    assert paths.eval_dir() == tmp_path


def test_default_jd_dir_follows_official_data_dir(monkeypatch, tmp_path):
    from app.pipeline.__main__ import default_jd_dir

    monkeypatch.delenv("JD_DIR", raising=False)
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    assert default_jd_dir() == tmp_path / "jd"


def test_gold_mention_scan_excludes_non_formal_candidates():
    from app.eval.scan import mention_skill_ids

    rows = mention_skill_ids(
        "熟悉 Python、GPT，具备良好的沟通能力和问题解决能力",
        [
            {"id": "python", "name": "Python", "synonyms": []},
            {"id": "gpt", "name": "GPT", "synonyms": []},
            {"id": "talk", "name": "沟通能力", "synonyms": []},
            {"id": "solve", "name": "问题解决", "synonyms": []},
        ],
        threshold=0.7,
    )
    assert [row["id"] for row in rows] == ["python"]
