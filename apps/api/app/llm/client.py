"""OpenAI-compatible LLM providers. Only outbound generation calls live here."""

from __future__ import annotations

import json
import os
from datetime import date


_cached = None
_cached_signature = None
_usage = {"day": date.today(), "calls": 0, "cost": 0.0}


def _parse_json_content(content) -> dict:
    """Decode provider JSON while tolerating harmless wrapper text."""
    if isinstance(content, list):
        content = "".join(
            part.get("text", "") if isinstance(part, dict) else str(part)
            for part in content
        )
    text = str(content or "").strip()
    if text.startswith("```"):
        text = text.strip("`").removeprefix("json").strip()
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        if start < 0:
            raise
        value, _ = json.JSONDecoder().raw_decode(text[start:])
    if not isinstance(value, dict):
        raise ValueError("LLM JSON root must be an object")
    return value


def _provider_config() -> tuple[str, str, str, str]:
    provider = os.environ.get("LLM_PROVIDER", "deepseek").strip().casefold()
    if provider == "bai":
        return (
            provider,
            os.environ.get("BAI_API_KEY") or "",
            os.environ.get("BAI_BASE_URL", "https://api.b.ai/v1"),
            os.environ.get("BAI_MODEL", "deepseek-v4-flash-vision-exp"),
        )
    if provider == "tuzi":
        return (
            provider,
            os.environ.get("TUZI_API_KEY") or "",
            os.environ.get("TUZI_BASE_URL", "https://api.tu-zi.com/v1"),
            os.environ.get("TUZI_MODEL", "gpt-5.6-luna"),
        )
    if provider == "deepseek":
        return (
            provider,
            os.environ.get("DEEPSEEK_API_KEY") or "",
            os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
            os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-flash"),
        )
    raise ValueError(f"unsupported LLM_PROVIDER: {provider}")


def _client():
    global _cached, _cached_signature
    provider, api_key, base_url, _ = _provider_config()
    signature = (provider, api_key, base_url)
    if _cached is None or _cached_signature != signature:
        from openai import OpenAI

        _cached = OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=60.0,
        )
        _cached_signature = signature
    return _cached


def complete_json(messages) -> dict:
    today = date.today()
    if _usage["day"] != today:
        _usage.update(day=today, calls=0, cost=0.0)
    if _usage["calls"] >= int(os.environ.get("LLM_DAILY_CALL_CAP", "1000")) or _usage["cost"] >= float(os.environ.get("LLM_DAILY_COST_CAP", "100")):
        raise RuntimeError("daily model quota exceeded")
    provider, _, _, model = _provider_config()
    try:
        max_tokens = max(1024, min(16_384, int(os.environ.get("LLM_MAX_OUTPUT_TOKENS", "4096"))))
    except (TypeError, ValueError):
        max_tokens = 4096
    last: Exception | None = None
    for attempt in range(2):
        try:
            request_messages = messages
            if attempt:
                request_messages = [
                    *messages,
                    {
                        "role": "system",
                        "content": "上一次 JSON 输出不完整。请压缩输出：只返回合法 JSON，skills 最多 40 条，每条 excerpt 不超过 80 字，不重复，不输出解释。",
                    },
                ]
            request = {
                "model": model,
                "messages": request_messages,
                "response_format": {"type": "json_object"},
                "max_tokens": max_tokens // 2 if attempt else max_tokens,
                # 管线产物要可复现：同一份缓存 + 同一判别提示，重跑不许换答案
                "temperature": 0,
            }
            if provider == "tuzi":
                request["reasoning_effort"] = os.environ.get("TUZI_REASONING_EFFORT", "none")
            disable_thinking = os.environ.get("BAI_DISABLE_THINKING", "1") != "0"
            if provider == "deepseek" or (provider == "bai" and disable_thinking):
                request["extra_body"] = {"thinking": {"type": "disabled"}}
            raw = _client().chat.completions.create(**request)
            content = raw.choices[0].message.content or "{}"
            usage = getattr(raw, "usage", None)
            tokens = int(getattr(usage, "total_tokens", 0) or 0)
            _usage["calls"] += 1
            _usage["cost"] += tokens / 1_000_000 * float(os.environ.get("LLM_COST_PER_MILLION", "1"))
            return _parse_json_content(content)
        except Exception as exc:
            last = exc
    raise last if last else RuntimeError("complete_json failed")
