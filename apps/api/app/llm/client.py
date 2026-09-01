"""DeepSeek chat. Only outbound LLM calls live here."""

from __future__ import annotations

import json
import os


_cached = None


def _client():
    global _cached
    if _cached is None:
        from openai import OpenAI

        _cached = OpenAI(
            api_key=os.environ.get("DEEPSEEK_API_KEY") or "",
            base_url=os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
            timeout=60.0,
        )
    return _cached


def complete_json(messages) -> dict:
    model = os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-flash")
    last: Exception | None = None
    for _ in range(2):
        try:
            raw = _client().chat.completions.create(
                model=model,
                messages=messages,
                response_format={"type": "json_object"},
                extra_body={"thinking": {"type": "disabled"}},
                # 管线产物要可复现：同一份缓存 + 同一判别提示，重跑不许换答案（io.md 对得上 EvolutionEvent 的前提）
                temperature=0,
            )
            content = raw.choices[0].message.content or "{}"
            return json.loads(content)
        except Exception as exc:
            last = exc
    raise last if last else RuntimeError("complete_json failed")
