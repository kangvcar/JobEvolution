from app.matching.bands import band_of, cover_required, match_score, shift_set
from app.matching.score import WATCHING_COPY, compare_job
from app.matching.report import direction_report, evidence_map, market_signal_radar, migration_map, recommend_jobs, resume_analysis, simulate_job


def test_band_thresholds():
    assert band_of(85) == "高度匹配"
    assert band_of(60) == "基本匹配"
    assert band_of(35) == "有明显差距"
    assert band_of(34.9) == "不匹配"
    assert band_of(0) == "不匹配"


def test_score_formula_and_empty_denom():
    assert match_score(req_cover=2, bonus_cover=0, req_full=2, bonus_full=0) == 100
    assert match_score(req_cover=1, bonus_cover=0, req_full=2, bonus_full=0) == 50
    assert match_score(req_cover=0, bonus_cover=0, req_full=0, bonus_full=0) == 0
    mixed = match_score(req_cover=1, bonus_cover=1, req_full=1, bonus_full=1)
    assert abs(mixed - 100 * (1 + 0.3) / (1 + 0.3)) < 1e-9


def test_half_band_only_when_resume_marks_proficiency():
    assert cover_required(None, "expert", True) == 1.0
    assert cover_required("able", "expert", True) == 0.5
    assert cover_required("expert", "able", True) == 1.0
    assert cover_required("able", "able", False) == 0.0


def test_gap_set_includes_half_and_missing():
    report = compare_job(
        [
            {"skill_id": "a", "name": "A", "kind": "required", "proficiency": "expert"},
            {"skill_id": "b", "name": "B", "kind": "required", "proficiency": "able"},
            {"skill_id": "c", "name": "C", "kind": "bonus", "proficiency": "aware"},
        ],
        [
            {"skill_id": "a", "name": "A", "proficiency": "able"},
        ],
    )
    gap_ids = {row["skill_id"] for row in report["gaps"]}
    half_ids = {row["skill_id"] for row in report["half"]}
    assert gap_ids == {"a", "b"}
    assert half_ids == {"a"}
    assert report["req_cover"] == 0.5
    assert report["band"] == "不匹配"


def test_bonus_missing_does_not_hurt_required():
    only_req = compare_job(
        [{"skill_id": "a", "name": "A", "kind": "required", "proficiency": "able"}],
        [{"skill_id": "a", "name": "A"}],
    )
    with_bonus_gap = compare_job(
        [
            {"skill_id": "a", "name": "A", "kind": "required", "proficiency": "able"},
            {"skill_id": "c", "name": "C", "kind": "bonus", "proficiency": "able"},
        ],
        [{"skill_id": "a", "name": "A"}],
    )
    assert only_req["req_cover"] == with_bonus_gap["req_cover"] == 1
    assert only_req["band"] == "高度匹配"


def test_shift_set_puts_single_lift_first():
    # 2 required, cover 0 → score 0, one fill → 50 still 有明显差距, two → 100
    items = [
        {"id": "x", "delta": 1.0},
        {"id": "y", "delta": 1.0},
    ]
    order = shift_set(
        items,
        req_cover=0,
        bonus_cover=0,
        req_full=2,
        bonus_full=0,
        score=0,
    )
    assert set(order[:2]) == {"x", "y"}
    # 3 required, cover 1 (33% → 不匹配), one more → 66% 基本匹配
    order2 = shift_set(
        [{"id": "p", "delta": 1.0}, {"id": "q", "delta": 1.0}],
        req_cover=1,
        bonus_cover=0,
        req_full=3,
        bonus_full=0,
        score=match_score(req_cover=1, bonus_cover=0, req_full=3, bonus_full=0),
    )
    assert order2[0] in {"p", "q"}


def test_path_max_five_and_watching_copy():
    requires = [
        {"skill_id": f"s{i}", "name": f"S{i}", "kind": "required", "proficiency": "able"}
        for i in range(8)
    ]
    report = compare_job(requires, [])
    assert len(report["path"]) == 5
    assert report["watching_copy"] == WATCHING_COPY


def test_path_why_shift_and_excerpt():
    requires = [
        {"skill_id": "p", "name": "P", "kind": "required", "proficiency": "able", "excerpt": "need P"},
        {"skill_id": "q", "name": "Q", "kind": "required", "proficiency": "able", "excerpt": "need Q"},
        {"skill_id": "r", "name": "R", "kind": "required", "proficiency": "able", "excerpt": "need R"},
    ]
    report = compare_job(requires, [{"skill_id": "r", "name": "R"}])
    assert report["path"][0]["why"] == "换档"
    assert report["path"][0]["excerpt"]
    assert {step["why"] for step in report["path"]} <= {"换档", "半档", "缺口"}


def test_requirement_group_counts_minimum_and_one_gap():
    report = compare_job(
        [
            {"skill_id": "torch", "name": "PyTorch", "kind": "required", "group_id": "dl", "min_required": 1},
            {"skill_id": "tf", "name": "TensorFlow", "kind": "required", "group_id": "dl", "min_required": 1},
        ],
        [{"skill_id": "torch", "name": "PyTorch"}],
    )
    assert report["req_full"] == 1
    assert report["req_cover"] == 1
    assert report["gaps"] == []

    two = compare_job(
        [
            {"skill_id": "aws", "name": "AWS", "kind": "required", "group_id": "cloud", "min_required": 2},
            {"skill_id": "ali", "name": "阿里云", "kind": "required", "group_id": "cloud", "min_required": 2},
            {"skill_id": "tencent", "name": "腾讯云", "kind": "required", "group_id": "cloud", "min_required": 2},
        ],
        [{"skill_id": "aws", "name": "AWS"}],
    )
    assert two["req_full"] == 2
    assert two["req_cover"] == 0.5
    assert len(two["gaps"]) == 1


def test_requirement_group_member_is_not_counted_again_as_standalone():
    report = compare_job(
        [
            {"skill_id": "python", "name": "Python", "kind": "required", "group_id": "lang", "min_required": 1},
            {"skill_id": "go", "name": "Go", "kind": "required", "group_id": "lang", "min_required": 1},
            {"skill_id": "python", "name": "Python", "kind": "required"},
        ],
        [{"skill_id": "python", "name": "Python"}],
    )
    assert report["req_full"] == 1


def test_recommendation_is_structured_and_direction_can_be_indistinguishable():
    resume = {"skills": [{"skill_id": "python", "name": "Python"}], "evidence_fragments": [{"skill_id": "python"}], "experience": "3年", "education": "本科"}
    jobs = [
        {"id": "a", "name": "后端", "status": "formed", "requires": [{"skill_id": "python", "name": "Python", "kind": "required", "proficiency": "able"}]},
        {"id": "b", "name": "服务端", "status": "formed", "requires": [{"skill_id": "python", "name": "Python", "kind": "required", "proficiency": "able"}]},
    ]
    recommendations = recommend_jobs(jobs, resume)
    assert len(recommendations) == 2
    assert len(recommendations[0]["reasons"]) == 2
    report = direction_report(jobs, resume)
    assert report["direction"] == "无法区分方向"
    assert len(report["jobs"][0]["shift_set"]) <= 5
    assert report["jobs"][0]["minimum_shift_skill_count"] == 0


def test_recommendation_uses_job_specific_evidence_before_freshness():
    resume = {
        "skills": [
            {"skill_id": "domain", "name": "领域能力"},
            {"skill_id": "eng", "name": "工程能力"},
        ],
        "evidence_fragments": [{"skill_id": "domain", "text": "交付领域项目"}],
    }
    jobs = [
        {"id": "generic", "name": "通用岗", "sources": ["甲", "乙", "丙"], "latest_observed_at": "2099-01-01", "requires": [{"skill_id": "eng", "name": "工程能力", "kind": "required", "category": "engineering"}]},
        {"id": "specific", "name": "领域岗", "sources": ["甲"], "latest_observed_at": "2020-01-01", "requires": [{"skill_id": "domain", "name": "领域能力", "kind": "required", "category": "domain"}]},
    ]
    assert recommend_jobs(jobs, resume, limit=2)[0]["job_id"] == "specific"


def test_resume_analysis_cites_only_resume_evidence_and_limits_actions():
    resume = {
        "skills": [{"skill_id": "python", "name": "Python"}],
        "evidence_fragments": [
            {"id": "ev-python", "skill_id": "python", "text": "使用 Python 构建服务", "evidence_level": "use", "section": "project"},
        ],
        "projects": [],
    }
    requires = [
        {"skill_id": "python", "name": "Python", "kind": "required", "proficiency": "able"},
        *[
            {"skill_id": f"s{i}", "name": f"S{i}", "kind": "required", "proficiency": "able"}
            for i in range(6)
        ],
    ]
    analysis = resume_analysis(job={"name": "大模型应用工程师"}, requires=requires, resume=resume)
    assert analysis["one_sentence"]
    assert analysis["strengths"][0]["evidence_fragment_id"] == "ev-python"
    assert len(analysis["risks"]) == 3
    assert len(analysis["actions"]["capability"]) == 3
    assert len(analysis["actions"]["rewrite"]) <= 5
    assert analysis["project_evidence_prompts"][0]["evidence_fragment_id"] == "ev-python"
    assert "87" not in str(analysis)


def test_simulation_uses_only_formal_gap_and_keeps_watching_out_of_score():
    requires = [{"skill_id": "rag", "name": "RAG", "kind": "required", "proficiency": "able"}]
    resume = {"skills": [], "evidence_fragments": []}
    original = simulate_job(requires, resume, [])
    simulated = simulate_job(requires, resume, ["rag"])
    assert original["original_band"] == original["simulated_band"]
    assert original["allowed_skill_ids"] == ["rag"]
    assert simulated["simulated_band"] == "高度匹配"
    assert market_signal_radar([{"skill_id": "watch", "name": "Watch"}], [{"id": "j", "requires": [], "sources": []}], "j")[0]["sample_occurrence_ratio"] == 0


def test_evidence_map_and_migration_map_are_bounded_and_traceable():
    resume = {"skills": [{"skill_id": "python", "name": "Python"}], "evidence_fragments": [{"id": "ev-1", "skill_id": "python", "text": "用 Python"}, {"id": "ev-2", "skill_id": "python", "text": "维护 Python"}]}
    requires = [{"skill_id": "python", "name": "Python", "kind": "required"}, {"skill_id": "rag", "name": "RAG", "kind": "required"}]
    mapped = evidence_map(requires, resume)
    assert [row["evidence_fragment_id"] for row in mapped[:2]] == ["ev-1", "ev-2"]
    assert mapped[-1]["evidence_level"] == "未提及"
    jobs = [{"id": str(i), "name": f"岗位{i}", "requires": requires} for i in range(5)]
    assert len(migration_map(jobs, resume)) == 3
