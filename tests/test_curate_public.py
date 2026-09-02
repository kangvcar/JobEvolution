from app.pipeline.curate_public import canonical_name, rank_requirements


def test_rank_requirements_filters_noise_deduplicates_and_caps():
    rows = [
        {"skill_id": "python", "name": "Python", "kind": "required", "confidence": 0.9, "sources": ["a", "b"]},
        {"skill_id": "prompt-en", "name": "Prompt Engineering", "kind": "required", "confidence": 0.9, "sources": ["a", "b", "c"]},
        {"skill_id": "prompt-zh", "name": "提示词工程", "kind": "required", "confidence": 0.8, "sources": ["a"]},
        {"skill_id": "gpt", "name": "GPT", "kind": "required", "confidence": 1, "sources": ["a", "b"]},
        {"skill_id": "team", "name": "团队协作", "kind": "required", "confidence": 1, "sources": ["a", "b"]},
        {"skill_id": "cv", "name": "CV", "kind": "required", "confidence": 0.7, "sources": ["a", "b"]},
        {"skill_id": "stale", "name": "Rust", "kind": "required", "confidence": 1, "sources": ["missing"]},
    ]
    result = rank_requirements(rows, {"a", "b", "c"}, max_required=1, max_formal=2)
    assert canonical_name("Prompt Engineering") == "提示词工程"
    assert result["counts"] == {"required": 1, "formal": 2}
    assert [row["name"] for row in result["selected"]] == ["提示词工程", "Python"]
    assert {row["skill_id"] for row in result["expired"]} >= {"gpt", "team", "stale"}
