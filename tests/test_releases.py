"""发布快照读取：按 release id 缓存解析结果，指针切换才重新加载。"""
import json

import pytest

from app import graph, releases


class _Result:
    def __init__(self, row):
        self._row = row

    def single(self):
        return self._row


class _Session:
    def __init__(self, store):
        self.store = store

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def run(self, query, **params):
        self.store["queries"].append(query)
        if "GraphPointer" in query:
            return _Result({"id": params.get("id") or self.store["pointer"]})
        return _Result({"snapshot": self.store["releases"].get(params["id"])})


class _Driver:
    def __init__(self, store):
        self.store = store

    def session(self):
        return _Session(self.store)


@pytest.fixture
def store(monkeypatch):
    data = {
        "pointer": "r1",
        "releases": {"r1": json.dumps({"list_jobs": [{"id": "a"}]}), "r2": json.dumps({"list_jobs": [{"id": "b"}]})},
        "queries": [],
    }
    monkeypatch.setattr(graph, "_driver", _Driver(data))
    releases._cache.clear()
    yield data
    releases._cache.clear()


def _snapshot_queries(store):
    return [q for q in store["queries"] if "r.snapshot" in q]


def test_load_parses_once_per_release_and_follows_pointer(store):
    assert releases.load()["list_jobs"] == [{"id": "a"}]
    assert releases.load()["list_jobs"] == [{"id": "a"}]
    assert len(_snapshot_queries(store)) == 1
    store["pointer"] = "r2"
    assert releases.load()["list_jobs"] == [{"id": "b"}]
    assert len(_snapshot_queries(store)) == 2
    # 绑定旧版本的会话仍能读到旧快照，且不再触发解析
    assert releases.load("r1")["list_jobs"] == [{"id": "a"}]
    assert len(_snapshot_queries(store)) == 2


def test_load_missing_snapshot_is_not_cached(store):
    store["pointer"] = "gone"
    assert releases.load() is None
    assert releases.load() is None
    assert len(_snapshot_queries(store)) == 2
    assert "gone" not in releases._cache


def test_snapshot_read_returns_copies_without_touching_cache(monkeypatch):
    snapshot = {"list_skills": [{"id": "s1", "name": "Py", "synonyms": ["python"], "embedding": [0.1, 0.2]}]}
    token = releases.view.set(snapshot)
    try:
        @releases.snapshot_read
        def list_skills(*, with_embed=True):
            raise AssertionError("should read snapshot")

        slim = list_skills(with_embed=False)
        assert slim == [{"id": "s1", "name": "Py", "synonyms": ["python"]}]
        slim[0]["synonyms"].append("x")
        full = list_skills()
        assert full[0]["embedding"] == [0.1, 0.2] and full[0]["synonyms"] == ["python"]
        assert snapshot["list_skills"][0]["synonyms"] == ["python"]
    finally:
        releases.view.reset(token)
