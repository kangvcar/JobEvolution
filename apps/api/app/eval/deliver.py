from __future__ import annotations

import json

from app.eval.io import write_json, write_jsonl
from app.eval.paths import eval_dir
from app.matching.score import compare_job
from app.pipeline.status import job_id_for

AGENT = "Agent 工程师"
LLM = "大模型应用工程师"


def _job_payload(graph, name: str) -> dict:
    job_id = job_id_for(name)
    job = graph.get_any_job(job_id) or {}
    evidence = graph.list_job_evidence(job_id)
    events = graph.list_job_events(job_id)
    requires = graph.list_requires(job_id)
    history = graph.list_requires_history(job_id)
    return {
        "id": job_id,
        "name": name,
        "status": job.get("status"),
        "domain": job.get("domain"),
        "watching": job.get("watching") or [],
        "n_sources": len({row.get("company") for row in evidence if row.get("company")}),
        "requires": requires,
        "requires_history": history,
        "period_delta": graph.period_delta(job_id),
        "aliases_in": graph.list_aliases_in(job_id),
        "alias_of": graph.alias_of(job_id),
        "events": events,
        "evidence": evidence,
    }


def _io_md(payload: dict, *, alias_note: str = "") -> str:
    lines = [
        f"# {payload['name']}",
        "",
        f"job_id `{payload['id']}`  status `{payload.get('status')}`  domain `{payload.get('domain')}`",
        "",
        "## 输入",
        "",
        f"独立源 {payload['n_sources']}。证据 {len(payload['evidence'])} 条。",
        "",
    ]
    for row in payload["evidence"][:8]:
        lines.append(
            f"- `{row.get('id')}` company `{row.get('company')}` observed_at `{row.get('observed_at')}`"
        )
    if len(payload["evidence"]) > 8:
        lines.append(f"（仅列前 8 条，共 {len(payload['evidence'])} 条，全量见 sources.jsonl）")
    lines += ["", "## 输出", "", "### REQUIRES", ""]
    for row in payload["requires"]:
        lines.append(
            f"- Skill.id `{row['skill_id']}` name `{row.get('name')}` kind `{row.get('kind')}` "
            f"proficiency `{row.get('proficiency')}` valid_from `{row.get('valid_from')}` "
            f"valid_to `{row.get('valid_to')}`"
        )
    if payload.get("period_delta"):
        lines += ["", "### period_delta", ""]
        for key in ("added", "expired"):
            names = [x.get("name") for x in payload["period_delta"].get(key) or []]
            lines.append(f"- {key}: {', '.join(n for n in names if n) or '（空）'}")
    lines += ["", "### EvolutionEvent", ""]
    for event in payload["events"]:
        payload_e = event.get("payload") or {}
        skill = payload_e.get("skill_id") or payload_e.get("skill_name") or ""
        lines.append(
            f"- `{event.get('id')}` kind `{event.get('kind')}` review `{event.get('review')}` "
            f"at `{event.get('at')}` Skill.id `{skill}`"
        )
    if alias_note:
        lines += ["", "## ALIAS_OF", "", alias_note]
    return "\n".join(lines) + "\n"


def dump_deliver() -> dict:
    from app import graph

    graph.init_graph()
    root = eval_dir() / "deliver"
    agent = _job_payload(graph, AGENT)
    llm = _job_payload(graph, LLM)
    alias = llm.get("aliases_in") or []
    alias_note = ""
    if alias:
        names = "、".join(row["name"] for row in alias)
        alias_note = (
            f"「{names}」写 ALIAS_OF 并入 `{llm['id']}` {LLM}，不是新岗位，不占候选列。"
        )
    for key, payload, note in (("agent", agent, ""), ("llm-app", llm, alias_note)):
        dest = root / key
        dest.mkdir(parents=True, exist_ok=True)
        write_json(
            dest / "job.json",
            {k: payload[k] for k in payload if k not in {"evidence", "events"}},
        )
        write_jsonl(dest / "sources.jsonl", payload["evidence"])
        (dest / "io.md").write_text(_io_md(payload, alias_note=note), encoding="utf-8")
    report = compare_job(llm["requires"], [])
    write_json(
        root / "llm-app" / "diagnose.example.json",
        {
            "job_id": llm["id"],
            "band": report["band"],
            "gap_ids": [g["skill_id"] for g in report["gaps"]],
            "shift_ids": report.get("shift_ids") or [],
        },
    )
    return {"agent": agent["id"], "llm_app": llm["id"], "alias": alias}


def main() -> int:
    info = dump_deliver()
    print(json.dumps(info, ensure_ascii=False))
    return 0
