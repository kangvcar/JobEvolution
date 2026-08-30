from app.eval.f1 import mean_f1, set_f1
from app.llm.embed import embed
from app.pipeline.align import align_skill


def test_set_f1_empty_vs_empty_is_one():
    row = set_f1(set(), set())
    assert row["f1"] == 1.0
    assert row["precision"] == 1.0
    assert row["recall"] == 1.0


def test_set_f1_one_side_empty_is_zero():
    assert set_f1({"a"}, set())["f1"] == 0.0
    assert set_f1(set(), {"a"})["f1"] == 0.0


def test_set_f1_overlap():
    row = set_f1({"a", "b", "c"}, {"a", "b"})
    assert abs(row["precision"] - 2 / 3) < 1e-9
    assert row["recall"] == 1.0


def test_mean_f1_averages_rows():
    rows = [set_f1({"a"}, {"a"}), set_f1({"a"}, {"b"})]
    out = mean_f1(rows)
    assert out["n"] == 2
    assert abs(out["f1"] - 0.5) < 1e-9


def test_align_skill_threshold_arg_not_env(monkeypatch):
    monkeypatch.setenv("ALIGN_THRESHOLD", "0.99")
    left = embed(["fastapi web framework"])[0]
    index = [
        {
            "id": "skill-a",
            "name": "FastAPI",
            "synonyms": [],
            "embedding": left,
        }
    ]
    # env must not leak into an explicit freeze threshold
    hit = align_skill("FastAPI service", index, embed_fn=embed, threshold=0.1)
    assert hit is not None and hit["id"] == "skill-a"
    miss = align_skill("FastAPI service", index, embed_fn=embed, threshold=0.999)
    assert miss is None
