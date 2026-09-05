"use client";

import { useState } from "react";

export type ReleaseAudit = {
  release: { id?: string | null; period?: string; published_at?: string | null };
  jobs: ReleaseJob[];
};

type GroupMember = { skill_id: string; name: string; kind?: string };
type Fragment = { text: string; supported: boolean; sources?: string[] };
type MissingDetail = {
  target: "requirement" | "claim";
  id: string;
  name?: string;
  kind?: string;
  excerpt?: string;
  text?: string;
  reasons: string[];
  fragments?: Fragment[];
};

type ReleaseError = {
  code: string;
  message?: string;
  count?: number;
  limit?: number;
  group_id?: string;
  reasons?: string[];
  min_required?: number | null;
  members?: GroupMember[];
  items?: string[];
  details?: MissingDetail[] | { skill_id: string; name: string }[];
  delta?: number;
  previous?: number;
};

export type ReleaseCheck = {
  ok: boolean;
  counts?: { required_equivalent?: number; formal_equivalent?: number };
  errors?: ReleaseError[];
  override?: { reason: string } | null;
};

export type ReleaseJob = {
  id: string;
  name: string;
  status?: string;
  definition_count: number;
  diagnostic_release: ReleaseCheck;
};

type Props = {
  audit: ReleaseAudit | null;
  busy: boolean;
  onRefresh: () => void;
  onRun: () => void;
  onRepair: (path: string, body: unknown) => Promise<Response>;
  onChecked: (jobId: string, check: ReleaseCheck) => void;
};

const CODE_LABEL: Record<string, string> = {
  definition_missing: "岗位定义为空或尚未批准",
  required_group_missing: "没有有效必备要求",
  invalid_requirement_group: "要求组不完整",
  evidence_missing: "要求或定义缺少有效证据",
  evidence_retracted: "引用了已撤回证据",
  duplicate_requirement: "同一技能出现重复要求",
  required_count_exceeded: "必备等价数超过上限",
  formal_count_exceeded: "正式等价数超过上限",
  required_delta_anomaly: "必备要求增量异常",
  formal_delta_anomaly: "正式要求增量异常",
};

const GROUP_REASON: Record<string, string> = {
  mixed_kind: "组内同时有必备和加分，整组要么全必备要么全加分",
  min_required_out_of_range: "最低满足数量超出成员数",
};

const MISSING_REASON: Record<string, string> = {
  no_sources: "没有来源",
  source_unknown: "来源不在岗位证据里",
  excerpt_missing: "没有原文摘录",
  excerpt_not_in_evidence: "摘录在来源原文里找不到",
  source_unavailable: "来源缺失或已撤回",
  fragment_not_in_evidence: "有片段在来源原文里找不到",
};

const KIND_LABEL: Record<string, string> = { required: "必备", bonus: "加分" };
const ANOMALY = new Set(["required_delta_anomaly", "formal_delta_anomaly"]);

function errorText(error: ReleaseError) {
  if (error.code === "required_count_exceeded") return `必备 ${error.count}/${error.limit}`;
  if (error.code === "formal_count_exceeded") return `正式 ${error.count}/${error.limit}`;
  return CODE_LABEL[error.code] || error.message || error.code;
}

// 后端 detail 可能是纯文本，也可能是 {code, items} 的 JSON 串；都压成一句话。
function failureText(body: { detail?: unknown; error?: unknown }, fallback: string) {
  const raw = body.detail ?? body.error;
  if (typeof raw !== "string") return fallback;
  try {
    const parsed = JSON.parse(raw) as { code?: string; items?: string[] };
    if (parsed.code === "fragment_not_in_evidence") return `这些片段在证据原文里找不到：${(parsed.items || []).join("；")}`;
    return raw;
  } catch {
    return raw;
  }
}

export default function ReleaseBoard({ audit, busy, onRefresh, onRun, onRepair, onChecked }: Props) {
  const [open, setOpen] = useState<string | null>(null);
  const [pending, setPending] = useState<string | null>(null);
  const [notes, setNotes] = useState<Record<string, { ok: boolean; text: string }>>({});
  const [reasons, setReasons] = useState<Record<string, string>>({});
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [minDrafts, setMinDrafts] = useState<Record<string, string>>({});

  const passed = audit?.jobs.filter((job) => job.diagnostic_release.ok).length ?? 0;

  async function act(jobId: string, key: string, path: string, body: unknown) {
    if (pending) return;
    setPending(key);
    try {
      const response = await onRepair(path, body);
      const json = await response.json().catch(() => ({}));
      if (!response.ok) {
        setNotes((current) => ({ ...current, [jobId]: { ok: false, text: failureText(json, "操作失败，请重试") } }));
        return;
      }
      const check: ReleaseCheck = json.check ?? json;
      onChecked(jobId, check);
      setNotes((current) => ({
        ...current,
        [jobId]: { ok: true, text: check.ok ? "已修正，该岗位通过校验。运行公开校准后进入公开版本。" : "已修正一项，还有其他问题待处理。" },
      }));
    } catch {
      setNotes((current) => ({ ...current, [jobId]: { ok: false, text: "操作失败，网络或服务异常" } }));
    } finally {
      setPending(null);
    }
  }

  function renderGroup(job: ReleaseJob, error: ReleaseError) {
    const gid = error.group_id || "";
    const base = `/admin/jobs/${job.id}/requirement-groups/${encodeURIComponent(gid)}`;
    const reason = reasons[job.id] || "";
    const key = (action: string) => `${job.id}:${gid}:${action}`;
    const members = error.members || [];
    const outOfRange = (error.reasons || []).includes("min_required_out_of_range");
    return (
      <>
        <ul className="release-members" aria-label="要求组成员">
          {members.map((member) => (
            <li key={member.skill_id} data-kind={member.kind}>{member.name} · {KIND_LABEL[member.kind || ""] || member.kind || "未标"}</li>
          ))}
        </ul>
        <p className="hint">
          最低满足数量 {error.min_required ?? "–"}；{(error.reasons || []).map((code) => GROUP_REASON[code] || code).join("；")}。
        </p>
        <div className="release-actions">
          <button type="button" disabled={Boolean(pending)} onClick={() => act(job.id, key("split"), base, { action: "split_by_kind", reason })}>按必备/加分拆成两组</button>
          <button type="button" disabled={Boolean(pending)} onClick={() => act(job.id, key("required"), base, { action: "set_kind", kind: "required", reason })}>整组改为必备</button>
          <button type="button" disabled={Boolean(pending)} onClick={() => act(job.id, key("bonus"), base, { action: "set_kind", kind: "bonus", reason })}>整组改为加分</button>
          <button type="button" disabled={Boolean(pending)} onClick={() => act(job.id, key("dissolve"), base, { action: "dissolve", reason })}>解散要求组</button>
          {outOfRange ? (
            <>
              <input
                type="number"
                min={1}
                max={members.length}
                value={minDrafts[gid] ?? String(Math.min(error.min_required || 1, members.length))}
                onChange={(event) => setMinDrafts((current) => ({ ...current, [gid]: event.target.value }))}
                aria-label="最低满足数量"
              />
              <button type="button" disabled={Boolean(pending)} onClick={() => act(job.id, key("min"), base, { action: "set_min_required", min_required: Number(minDrafts[gid] ?? Math.min(error.min_required || 1, members.length)), reason })}>设置最低数量</button>
            </>
          ) : null}
        </div>
      </>
    );
  }

  function renderMissing(job: ReleaseJob, error: ReleaseError) {
    const details = (error.details || []) as MissingDetail[];
    const reason = reasons[job.id] || "";
    if (!details.length) return <p className="hint">缺证据项：{(error.items || []).join("、")}</p>;
    return details.map((detail) => {
      if (detail.target === "claim") {
        const base = `/admin/jobs/${job.id}/definition-claims/${encodeURIComponent(detail.id)}`;
        const draft = drafts[detail.id] ?? detail.text ?? "";
        return (
          <div className="release-target" key={detail.id}>
            <p className="hint">岗位定义声明：{detail.reasons.map((code) => MISSING_REASON[code] || code).join("；")}。每个片段都要能在来源原文里逐字找到。</p>
            <ul className="release-frags" aria-label="定义片段核对">
              {(detail.fragments || []).map((fragment, index) => (
                <li key={`${detail.id}:${index}`} data-bad={fragment.supported ? undefined : true}>{fragment.text}</li>
              ))}
            </ul>
            <div className="release-actions">
              <button type="button" disabled={Boolean(pending)} onClick={() => act(job.id, `${detail.id}:drop`, base, { action: "drop_unsupported", reason })}>去掉对不上的片段</button>
              <button type="button" disabled={Boolean(pending)} onClick={() => act(job.id, `${detail.id}:regen`, base, { action: "regenerate", reason })}>按证据原文重新生成</button>
            </div>
            <div className="release-actions release-edit">
              <textarea value={draft} onChange={(event) => setDrafts((current) => ({ ...current, [detail.id]: event.target.value }))} aria-label="改写定义声明" />
              <button type="button" disabled={Boolean(pending) || !draft.trim()} onClick={() => act(job.id, `${detail.id}:edit`, base, { action: "edit", text: draft, reason })}>保存改写并核对</button>
            </div>
          </div>
        );
      }
      return (
        <div className="release-target" key={detail.id}>
          <p className="hint">
            要求 <b>{detail.name || detail.id}</b>（{KIND_LABEL[detail.kind || ""] || "未标"}）：{detail.reasons.map((code) => MISSING_REASON[code] || code).join("；")}
            {detail.excerpt ? <>；摘录「{detail.excerpt}」</> : null}。
          </p>
          <div className="release-actions">
            <button type="button" disabled={Boolean(pending) || !reason.trim()} title={reason.trim() ? undefined : "先在下方写明理由"} onClick={() => act(job.id, `${detail.id}:expire`, `/admin/jobs/${job.id}/requirements/${encodeURIComponent(detail.id)}/expire`, { reason })}>移出正式要求</button>
          </div>
        </div>
      );
    });
  }

  function renderDuplicate(job: ReleaseJob, error: ReleaseError) {
    const reason = reasons[job.id] || "";
    const rows = (error.details || []) as { skill_id: string; name: string }[];
    const list = rows.length ? rows : (error.items || []).map((id) => ({ skill_id: id, name: id }));
    return (
      <div className="release-actions">
        {list.map((row) => (
          <button key={row.skill_id} type="button" disabled={Boolean(pending) || !reason.trim()} title={reason.trim() ? undefined : "先在下方写明理由"} onClick={() => act(job.id, `${row.skill_id}:expire`, `/admin/jobs/${job.id}/requirements/${encodeURIComponent(row.skill_id)}/expire`, { reason })}>
            移出 {row.name}
          </button>
        ))}
      </div>
    );
  }

  function renderError(job: ReleaseJob, error: ReleaseError) {
    const reason = reasons[job.id] || "";
    switch (error.code) {
      case "invalid_requirement_group":
        return renderGroup(job, error);
      case "evidence_missing":
        return renderMissing(job, error);
      case "duplicate_requirement":
        return renderDuplicate(job, error);
      case "definition_missing":
        return (
          <div className="release-actions">
            <span className="hint">可到待审队列批准定义提案，或直接用已批准提案的原文片段生成。</span>
            <button type="button" disabled={Boolean(pending)} onClick={() => act(job.id, `${job.id}:regen`, `/admin/jobs/${job.id}/definition-claims/new`, { action: "regenerate", reason })}>按证据原文生成定义</button>
          </div>
        );
      case "required_group_missing":
        return <p className="hint">到待审队列批准该岗位的必备要求提案后再来校验。</p>;
      case "required_count_exceeded":
      case "formal_count_exceeded":
        return <p className="hint">当前 {error.count}，上限 {error.limit}。运行公开校准会按独立来源数把要求裁到上限。</p>;
      case "evidence_retracted":
        return <p className="hint">已撤回证据：{(error.items || []).join("、")}。运行公开校准会重新计票并移出失去支撑的要求。</p>;
      case "required_delta_anomaly":
      case "formal_delta_anomaly":
        return (
          <div className="release-actions">
            <span className="hint">较上期新增 {error.delta}（上期 {error.previous}）。核对无误后写明理由放行。</span>
            <button type="button" disabled={Boolean(pending) || !reason.trim()} title={reason.trim() ? undefined : "先在下方写明理由"} onClick={() => act(job.id, `${job.id}:override`, `/admin/jobs/${job.id}/diagnostic-release`, { reason })}>写明理由放行</button>
          </div>
        );
      default:
        return <p className="hint">{error.message || error.code}</p>;
    }
  }

  function renderDetail(job: ReleaseJob) {
    const errors = job.diagnostic_release.errors || [];
    const note = notes[job.id];
    const needsReason = errors.some((error) => ANOMALY.has(error.code) || error.code === "duplicate_requirement" || error.code === "evidence_missing");
    return (
      <tr className="release-detail" key={`${job.id}-detail`}>
        <td colSpan={7}>
          {errors.map((error, index) => (
            <section className="release-issue" key={`${error.code}:${error.group_id || index}`} aria-label={errorText(error)}>
              <h3>{errorText(error)}</h3>
              {renderError(job, error)}
            </section>
          ))}
          <div className="release-actions release-reason">
            <label htmlFor={`reason-${job.id}`}>理由</label>
            <input
              id={`reason-${job.id}`}
              type="text"
              value={reasons[job.id] || ""}
              placeholder={needsReason ? "放行、移出要求时必填；其他操作作为审计备注" : "审计备注（可选）"}
              onChange={(event) => setReasons((current) => ({ ...current, [job.id]: event.target.value }))}
            />
          </div>
          {note ? <p className={note.ok ? "release-ok" : "release-fail"} role="status">{note.text}</p> : null}
        </td>
      </tr>
    );
  }

  return (
    <section className="qb-main" aria-labelledby="release-board-title">
      <header className="qb-head">
        <h2 id="release-board-title">诊断发布校验 <span className="hint">{audit ? `${passed}/${audit.jobs.length} 个岗位可诊断` : "读取中…"}</span></h2>
        <div className="qb-ops release-ops">
          <button type="button" onClick={onRefresh} disabled={busy}>刷新</button>
          <button type="button" onClick={onRun} disabled={busy}>{busy ? "校准中…" : "运行公开校准"}</button>
        </div>
      </header>
      <p className="release-note">点开未通过的岗位可直接修正要求组、定义声明或移出缺证据的要求；修正只改工作图，运行公开校准后才进入公开版本。</p>
      {!audit ? <p className="release-empty">暂无发布校验结果。</p> : audit.jobs.length === 0 ? <p className="release-empty">暂无公开岗位。</p> : (
        <table className="qb-table release-table">
          <thead><tr><th>岗位</th><th>状态</th><th className="num">定义</th><th className="num">必备等价</th><th className="num">正式等价</th><th>结果</th><th className="qb-ops">操作</th></tr></thead>
          <tbody>
            {audit.jobs.map((job) => {
              const check = job.diagnostic_release;
              const counts = check.counts || {};
              const expanded = open === job.id;
              const note = notes[job.id];
              return [
                <tr key={job.id} aria-expanded={check.ok ? undefined : expanded}>
                  <td className="qb-name">{job.name}</td>
                  <td>{job.status || "–"}</td>
                  <td className="num">{job.definition_count}</td>
                  <td className="num">{counts.required_equivalent ?? "–"}</td>
                  <td className="num">{counts.formal_equivalent ?? "–"}</td>
                  <td className={check.ok ? "release-ok" : "release-fail"}>
                    {check.ok ? (check.override ? "可诊断（已写明理由放行）" : "可诊断") : (check.errors || []).slice(0, 2).map(errorText).join("；") || "未通过校验"}
                    {check.ok && note ? <span className="hint"> · {note.text}</span> : null}
                  </td>
                  <td className="qb-ops">
                    {check.ok ? "–" : (
                      <button type="button" className="release-toggle" aria-expanded={expanded} onClick={() => setOpen(expanded ? null : job.id)}>{expanded ? "收起" : "处理"}</button>
                    )}
                  </td>
                </tr>,
                expanded && !check.ok ? renderDetail(job) : null,
              ];
            })}
          </tbody>
        </table>
      )}
      {audit?.release?.id ? <p className="release-meta">当前公开版本：<span className="mono">{audit.release.id}</span></p> : null}
    </section>
  );
}
