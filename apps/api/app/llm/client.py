"""DeepSeek chat. Only outbound LLM calls live here."""

from __future__ import annotations

import json
import os
from datetime import date


_cached = None
_usage = {"day": date.today(), "calls": 0, "cost": 0.0}


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
    today = date.today()
    if _usage["day"] != today:
        _usage.update(day=today, calls=0, cost=0.0)
    if _usage["calls"] >= int(os.environ.get("LLM_DAILY_CALL_CAP", "1000")) or _usage["cost"] >= float(os.environ.get("LLM_DAILY_COST_CAP", "100")):
        raise RuntimeError("daily model quota exceeded")
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
            usage = getattr(raw, "usage", None)
            tokens = int(getattr(usage, "total_tokens", 0) or 0)
            _usage["calls"] += 1
            _usage["cost"] += tokens / 1_000_000 * float(os.environ.get("LLM_COST_PER_MILLION", "1"))
            return json.loads(content)
        except Exception as exc:
            last = exc
    raise last if last else RuntimeError("complete_json failed")
