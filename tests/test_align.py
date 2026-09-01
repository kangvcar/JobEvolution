from app.pipeline.align import split_composite

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
