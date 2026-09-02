from app.pipeline.align import align_skill, normalize_surface, split_composite
from app.pipeline.extract import brand_action_skill, classify_skill_candidate, coerce_extracted

VOCAB = [
    {"id": "s1", "name": "C", "synonyms": []},
    {"id": "s2", "name": "C++", "synonyms": []},
    {"id": "s3", "name": "Linux", "synonyms": ["linux系统"]},
]


def test_composite_splits_only_when_all_parts_hit_vocab():
    assert split_composite("C/C++", VOCAB) == ["C", "C++"]
    assert split_composite("Linux/linux系统", VOCAB) == ["Linux", "linux系统"]
    assert split_composite("R&D", VOCAB) == ["R&D"]
    assert split_composite("C/不存在", VOCAB) == ["C/不存在"]
    assert split_composite("单一技能", VOCAB) == ["单一技能"]


def test_surface_normalization_and_approved_prompt_synonym():
    assert normalize_surface("  Prompt　Engineering！") == "prompt engineering!"
    index = [{"id": "s1", "name": "Prompt Engineering", "synonyms": []}]
    assert align_skill("提示词工程", index, allow_embedding=False)["id"] == "s1"


def test_related_skills_are_not_semantically_merged():
    index = [{"id": "s1", "name": "LangChain", "synonyms": [], "embedding": [1.0, 0.0]}]
    assert align_skill("LangGraph", index, embed_fn=lambda _: [[1.0, 0.0]], allow_embedding=True) is None


def test_skill_type_policy_filters_generic_and_derives_brand_action():
    assert classify_skill_candidate("团队协作") == "generic"
    assert classify_skill_candidate("GPT") == "brand"
    assert brand_action_skill("GPT", "调用 GPT API 构建服务") == "API 集成"
    parsed = coerce_extracted({"job_name": "岗", "skills": [{"name": "GPT", "candidate_type": "brand", "action": "熟悉"}]})
    assert parsed["skills"][0]["candidate_type"] == "brand"
