from app.matching.bands import band_of, cover_required, match_score, shift_set
from app.matching.score import WATCHING_COPY, compare_job


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
