"use client";

import { useEffect, useMemo, useState } from "react";
import { kindLabel } from "../feed-bits";

export type QueueEvent = {
  id: string;
  kind: string;
  at: string;
  confidence?: number;
  review?: "pending" | "auto_passed";
  payload?: {
    job_id?: string;
    job_name?: string;
    version_id?: string;
    skill_name?: string;
    category?: string;
    proposed_kind?: string;
    kind_edge?: string;
    proficiency?: string;
    required_votes?: number;
    bonus_votes?: number;
    classified_vote_count?: number;
    independent_source_count?: number;
    decision_reason?: string;
    watching?: string[];
    excerpt?: string;
    error?: string;
    path?: string;
    evidence_id?: string;
    proposed_name?: string;
    old_skill_id?: string;
    canonical_skill_id?: string;
    reason?: string;
    layer?: "high" | "mid" | "low";
    [key: string]: unknown;
  };
};

type Group = { key: string; label: string; items: QueueEvent[]; jobId?: string; versionId?: string };

const CATEGORY: Record<string, string> = { language: "语言", framework: "框架", platform: "平台", engineering: "工程", domain: "领域" };
const PROFICIENCY: Record<string, string> = { aware: "了解", able: "熟练", expert: "精通" };
const LAYER: Record<string, string> = { high: "高", mid: "中", low: "低" };
const REASON: Record<string, string> = { embedding_neighbour_only: "仅向量近邻" };

const label = (map: Record<string, string>, key?: string) => (key ? map[key] ?? key : "–");

function groupQueue(queue: QueueEvent[]): Group[] {
  const byVersion = new Map<string, Group>();
  const rest = new Map<string, Group>();
  for (const item of queue) {
    const p = item.payload ?? {};
    if (item.kind === "requires_add" && p.job_id) {
      const key = `${p.job_id}:${p.version_id || "latest"}`;
      const group = byVersion.get(key) ?? { key, label: String(p.job_name || p.job_id), items: [], jobId: String(p.job_id), versionId: String(p.version_id || "latest") };
      group.items.push(item);
      byVersion.set(key, group);
    } else {
      const group = rest.get(item.kind) ?? { key: item.kind, label: kindLabel(item.kind), items: [] };
      group.items.push(item);
      rest.set(item.kind, group);
    }
  }
  // 同一岗位有多个待发布版本时，名字后缀版本号尾段，否则左栏分不出来。
  const versions = [...byVersion.values()];
  const names = new Map<string, number>();
  versions.forEach((g) => names.set(g.label, (names.get(g.label) ?? 0) + 1));
  versions.forEach((g) => {
    if ((names.get(g.label) ?? 0) > 1) g.label = `${g.label} ·${g.versionId!.slice(-4)}`;
  });
  return [...versions, ...rest.values()];
}

function LayerBar({ items }: { items: QueueEvent[] }) {
  const n = items.length || 1;
  const count = (layer: string) => items.filter((i) => i.payload?.layer === layer).length;
  return (
    <span className="layer-bar" aria-hidden="true">
      <i data-layer="high" style={{ flexGrow: count("high") / n }} />
      <i data-layer="mid" style={{ flexGrow: count("mid") / n }} />
      <i data-layer="low" style={{ flexGrow: count("low") / n }} />
    </span>
  );
}

type Props = {
  queue: QueueEvent[];
  skillNames: Record<string, string>;
  busy: string | null;
  bulkBusy: string | null;
  bulkResult: Record<string, string>;
  onReview: (item: QueueEvent, decision: "approved" | "rejected", draft?: string) => void;
  onApproveAll: (jobId: string, versionId: string) => void;
};

export default function QueueBoard({ queue, skillNames, busy, bulkBusy, bulkResult, onReview, onApproveAll }: Props) {
  const groups = useMemo(() => groupQueue(queue), [queue]);
  const [groupKey, setGroupKey] = useState<string | null>(null);
  const group = groups.find((g) => g.key === groupKey) ?? groups[0];
  const items = group?.items ?? [];
  const [cursor, setCursor] = useState(0);
  const [open, setOpen] = useState<string | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [draft, setDraft] = useState<string>("");

  const row = items[Math.min(cursor, items.length - 1)];
  const isRequires = group?.jobId !== undefined;

  useEffect(() => {
    setCursor(0);
    setOpen(null);
    setSelected(new Set());
  }, [group?.key]);

  function toggleOpen(item: QueueEvent) {
    if (open === item.id) {
      setOpen(null);
      return;
    }
    setOpen(item.id);
    setDraft(item.payload?.excerpt || "");
  }

  function toggleSelect(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function reviewSelected(decision: "approved" | "rejected") {
    items.filter((i) => selected.has(i.id)).forEach((i) => onReview(i, decision));
    setSelected(new Set());
  }

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      const target = event.target as HTMLElement;
      if (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || !row) return;
      if (event.key === "j" || event.key === "ArrowDown") {
        event.preventDefault();
        setCursor((c) => Math.min(items.length - 1, c + 1));
        setOpen(null);
      } else if (event.key === "k" || event.key === "ArrowUp") {
        event.preventDefault();
        setCursor((c) => Math.max(0, c - 1));
        setOpen(null);
      } else if (event.key === "Enter") {
        toggleOpen(row);
      } else if (event.key === "x") {
        toggleSelect(row.id);
      } else if (event.key === "a") {
        onReview(row, "approved", open === row.id ? draft : undefined);
      } else if (event.key === "r") {
        onReview(row, "rejected");
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  useEffect(() => {
    document.querySelector(`[data-row-id="${row?.id}"]`)?.scrollIntoView({ block: "nearest" });
  }, [row?.id]);

  if (!queue.length) return <p className="empty">暂无待审演化事件。</p>;

  return (
    <div className="qb">
      <aside className="qb-groups" aria-label="待审分组">
        {groups.map((g) => (
          <button key={g.key} type="button" aria-current={g.key === group?.key || undefined} onClick={() => setGroupKey(g.key)}>
            <span>{g.label}</span>
            <b>{g.items.length}</b>
            <LayerBar items={g.items} />
          </button>
        ))}
      </aside>

      <section className="qb-main" aria-label={group?.label}>
        <header className="qb-head">
          <h2>{group?.label} <span className="hint">{isRequires ? `版本 ${group?.versionId} · ` : ""}{items.length} 条</span></h2>
          {isRequires && group ? (
            <span className="row">
              {bulkResult[group.key] ? <span className="hint" role="status">{bulkResult[group.key]}</span> : null}
              <button className="primary small" type="button" disabled={bulkBusy === group.key} onClick={() => onApproveAll(group.jobId!, group.versionId!)}>一键批准本版本</button>
            </span>
          ) : null}
        </header>

        <table className="qb-table">
          <colgroup>
            <col className="w-check" />
            {isRequires ? (
              <><col /><col className="w-s" /><col className="w-s" /><col className="w-s" /><col className="w-m" /></>
            ) : group?.key === "skill_merge_proposal" ? (
              <><col /><col className="w-l" /><col className="w-m" /></>
            ) : (
              <><col className="w-l" /><col /></>
            )}
            <col className="w-s" /><col className="w-s" /><col className="w-ops" />
          </colgroup>
          <thead>
            <tr>
              <th className="qb-check" aria-label="选中" />
              {isRequires ? (
                <>
                  <th>技能点</th><th>类目</th><th>性质</th><th>熟练级</th><th className="num">票 / 源</th>
                </>
              ) : group?.key === "skill_merge_proposal" ? (
                <>
                  <th>提案名</th><th>并入</th><th>原因</th>
                </>
              ) : (
                <>
                  <th>证据</th><th>错误</th>
                </>
              )}
              <th>置信</th><th>日期</th><th className="qb-ops" aria-label="操作" />
            </tr>
          </thead>
          <tbody>
            {items.map((item, index) => {
              const p = item.payload ?? {};
              const current = index === Math.min(cursor, items.length - 1);
              const expanded = open === item.id;
              const votes = `${p.required_votes ?? 0}/${p.classified_vote_count ?? 0} · ${p.independent_source_count ?? 0}`;
              const kindEdge = p.proposed_kind || p.kind_edge;
              return [
                <tr key={item.id} data-row-id={item.id} aria-current={current || undefined} aria-expanded={expanded} className={busy === item.id ? "is-busy" : undefined} onClick={() => { setCursor(index); toggleOpen(item); }}>
                  <td className="qb-check" onClick={(e) => e.stopPropagation()}>
                    <input type="checkbox" checked={selected.has(item.id)} onChange={() => toggleSelect(item.id)} aria-label={`选中 ${p.skill_name || p.proposed_name || p.evidence_id || item.id}`} />
                  </td>
                  {isRequires ? (
                    <>
                      <td className="qb-name">{p.skill_name}</td>
                      <td>{label(CATEGORY, p.category)}</td>
                      <td>{kindEdge === "required" ? "必备" : kindEdge === "bonus" ? "加分" : <span className="hint" title="票数不够，批准也不会写边">未定</span>}</td>
                      <td>{label(PROFICIENCY, p.proficiency)}</td>
                      <td className="num">{votes}</td>
                    </>
                  ) : group?.key === "skill_merge_proposal" ? (
                    <>
                      <td className="qb-name">{p.proposed_name}</td>
                      <td title={`${p.old_skill_id} → ${p.canonical_skill_id}`}>{skillNames[p.canonical_skill_id ?? ""] ?? String(p.canonical_skill_id).slice(-6)}</td>
                      <td>{label(REASON, p.reason)}</td>
                    </>
                  ) : (
                    <>
                      <td className="mono">{p.evidence_id || p.path}</td>
                      <td>{p.error}</td>
                    </>
                  )}
                  <td><span className="layer-chip" data-layer={p.layer}>{label(LAYER, p.layer)}</span></td>
                  <td className="mono">{item.at.slice(5, 10)}</td>
                  <td className="qb-ops" onClick={(e) => e.stopPropagation()}>
                    <button type="button" title="批准 a" disabled={busy === item.id} onClick={() => onReview(item, "approved", expanded ? draft : undefined)}>✓</button>
                    <button type="button" title="驳回 r" disabled={busy === item.id} onClick={() => onReview(item, "rejected")}>✕</button>
                  </td>
                </tr>,
                expanded ? (
                  <tr key={`${item.id}-detail`} className="qb-detail">
                    <td colSpan={isRequires ? 9 : group?.key === "skill_merge_proposal" ? 7 : 6}>
                      <dl>
                        {p.excerpt ? <><dt>JD 原文</dt><dd><q>{p.excerpt}</q></dd></> : null}
                        {p.decision_reason ? <><dt>判定</dt><dd>{p.decision_reason}</dd></> : null}
                        {p.watching?.length ? <><dt>观测中</dt><dd>{p.watching.length} 项</dd></> : null}
                        {p.error ? <><dt>路径</dt><dd className="mono">{p.path}</dd></> : null}
                        {p.reason ? <><dt>原因</dt><dd>{label(REASON, p.reason)}</dd></> : null}
                        <dt>置信度</dt><dd>{item.confidence ?? 0}{p.layer === "low" ? "，低置信不可自动通过" : ""}</dd>
                      </dl>
                      {item.kind !== "extract_failed" && p.excerpt !== undefined ? (
                        <label className="qb-draft">
                          最终事实（可改写，原稿保留）
                          <textarea value={draft} rows={2} onChange={(e) => setDraft(e.target.value)} />
                        </label>
                      ) : null}
                    </td>
                  </tr>
                ) : null,
              ];
            })}
          </tbody>
        </table>

        <footer className="qb-foot">
          {selected.size ? (
            <span className="row">
              <span>已选 {selected.size} / {items.length}</span>
              <button className="primary small" type="button" onClick={() => reviewSelected("approved")}>批准所选</button>
              <button className="ghost small" type="button" onClick={() => reviewSelected("rejected")}>驳回所选</button>
              <button className="ghost small" type="button" onClick={() => setSelected(new Set(items.map((i) => i.id)))}>全选</button>
            </span>
          ) : (
            <span className="hint"><kbd>j</kbd><kbd>k</kbd> 移动 <kbd>Enter</kbd> 展开 <kbd>x</kbd> 选中 <kbd>a</kbd> 批准 <kbd>r</kbd> 驳回</span>
          )}
        </footer>
      </section>
    </div>
  );
}
