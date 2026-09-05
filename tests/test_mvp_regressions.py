from app.matching.score import compare_job
from app.matching.report import direction_report, recommend_jobs, simulate_job


def test_groups_minimal_shift_and_real_category_payload():
    group = [{"skill_id": s, "name": s, "kind": "required", "group_id": "g", "min_required": 2}
             for s in ("a", "b", "c")]
    result = compare_job(group, [{"skill_id": "a"}, {"skill_id": "b"}])
    assert result["score"] == 100 and not result["gaps"]
    assert {row["skill_id"] for row in result["covered"]} == {"a", "b"}
    requirements = [{"skill_id": str(i), "kind": "required"} for i in range(4)]
    result = compare_job(requirements, [])
    assert len(result["shift_ids"]) == 2
    assert compare_job(requirements, [{"skill_id": sid} for sid in result["shift_ids"]])["score"] == 50
    assert len(simulate_job(requirements, {"skills": []}, ["3"])["allowed_skill_ids"]) == 4
    assert simulate_job([{"skill_id": "a", "proficiency": "expert"}],
                        {"skills": [{"skill_id": "a", "proficiency": "aware"}]}, ["a"])["simulated_score"] == 100
    assert compare_job([{"skill_id": "a"}], [{"skill_id": "a", "proficiency": "aware"}])["score"] == 100
    jobs = [{"id": "a", "name": "A", "requires": [{"skill_id": str(i)} for i in range(10)]},
            {"id": "b", "name": "B", "requires": [{"skill_id": str(i)} for i in range(4)] + [{"skill_id": "z"}]}]
    resume = {"skills": [{"skill_id": str(i)} for i in range(7)]}
    assert recommend_jobs(jobs, resume)[0]["name"] == direction_report(jobs, resume)["direction"] == "B"
    jobs[0]["requires"] = [{"skill_id": "0", "category_id": "engineering", "category": "工程"}]
    assert direction_report(jobs, resume)["jobs"][0]["transferable_engineering"] == 1
