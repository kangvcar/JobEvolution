import json


def test_parse_json_content_accepts_provider_wrappers():
    from app.llm.client import _parse_json_content

    assert _parse_json_content("```json\n{\"ok\": true}\n```") == {"ok": True}
    assert _parse_json_content("前置说明\n{\"ok\": true}\n") == {"ok": True}


def test_complete_json_compacts_after_truncated_response(monkeypatch):
    from app.llm import client

    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    calls = []

    class FakeCompletions:
        def create(self, **kwargs):
            calls.append(kwargs)
            content = "{\"skills\": [" if len(calls) == 1 else json.dumps({"skills": []})
            return type("Response", (), {"choices": [type("Choice", (), {"message": type("Message", (), {"content": content})()})()]})()

    monkeypatch.setattr(client, "_cached", type("FakeClient", (), {"chat": type("Chat", (), {"completions": FakeCompletions()})()})())
    monkeypatch.setattr(client, "_cached_signature", ("deepseek", "", "https://api.deepseek.com"))
    client._usage.update(day=client.date.today(), calls=0, cost=0.0)
    assert client.complete_json([{"role": "user", "content": "test"}]) == {"skills": []}
    assert len(calls) == 2
    assert "压缩输出" in calls[1]["messages"][-1]["content"]
    assert calls[0]["max_tokens"] == 4096 and calls[1]["max_tokens"] == 2048


def test_bai_provider_uses_compatible_defaults(monkeypatch):
    from app.llm.client import _provider_config

    monkeypatch.setenv("LLM_PROVIDER", "bai")
    monkeypatch.delenv("BAI_BASE_URL", raising=False)
    monkeypatch.delenv("BAI_MODEL", raising=False)
    provider, _, base_url, model = _provider_config()
    assert (provider, base_url, model) == ("bai", "https://api.b.ai/v1", "deepseek-v4-flash-vision-exp")


def test_bai_request_disables_thinking_by_default(monkeypatch):
    from app.llm import client

    calls = []

    class FakeCompletions:
        def create(self, **kwargs):
            calls.append(kwargs)
            return type("Response", (), {"choices": [type("Choice", (), {"message": type("Message", (), {"content": "{}"})()})()]})()

    monkeypatch.setenv("LLM_PROVIDER", "bai")
    monkeypatch.setenv("BAI_API_KEY", "test")
    monkeypatch.delenv("BAI_DISABLE_THINKING", raising=False)
    monkeypatch.setattr(client, "_cached", type("FakeClient", (), {"chat": type("Chat", (), {"completions": FakeCompletions()})()})())
    monkeypatch.setattr(client, "_cached_signature", ("bai", "test", "https://api.b.ai/v1"))
    client._usage.update(day=client.date.today(), calls=0, cost=0.0)
    assert client.complete_json([{"role": "user", "content": "test"}]) == {}
    assert calls[0]["extra_body"] == {"thinking": {"type": "disabled"}}


def test_tuzi_provider_uses_compatible_defaults(monkeypatch):
    from app.llm.client import _provider_config

    monkeypatch.setenv("LLM_PROVIDER", "tuzi")
    monkeypatch.delenv("TUZI_BASE_URL", raising=False)
    monkeypatch.delenv("TUZI_MODEL", raising=False)
    provider, _, base_url, model = _provider_config()
    assert (provider, base_url, model) == ("tuzi", "https://api.tu-zi.com/v1", "gpt-5.6-luna")


def test_tuzi_request_uses_no_provider_extension(monkeypatch):
    from app.llm import client

    calls = []

    class FakeCompletions:
        def create(self, **kwargs):
            calls.append(kwargs)
            return type("Response", (), {"choices": [type("Choice", (), {"message": type("Message", (), {"content": "{}"})()})()]})()

    monkeypatch.setenv("LLM_PROVIDER", "tuzi")
    monkeypatch.setenv("TUZI_API_KEY", "test")
    monkeypatch.delenv("TUZI_REASONING_EFFORT", raising=False)
    monkeypatch.setattr(client, "_cached", type("FakeClient", (), {"chat": type("Chat", (), {"completions": FakeCompletions()})()})())
    monkeypatch.setattr(client, "_cached_signature", ("tuzi", "test", "https://api.tu-zi.com/v1"))
    client._usage.update(day=client.date.today(), calls=0, cost=0.0)
    assert client.complete_json([{"role": "user", "content": "test"}]) == {}
    assert calls[0]["reasoning_effort"] == "none"
    assert "extra_body" not in calls[0]
