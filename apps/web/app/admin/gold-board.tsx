"use client";

import { ReactNode, useEffect, useMemo, useState } from "react";

export type AdjRow = {
  id: string;
  title: string;
  text: string;
  source_path?: string;
  kept: { id: string; name: string }[];
  suspects: { id: string; name: string }[];
  proposals: { skill_id: string; name: string; span: string }[];
  unaligned: string[];
};

export type AdjState = {
  file: "jd" | "resume";
  total: number;
  done: number;
  row: AdjRow | null;
  draft_missing?: boolean;
};

export type AdjDecision = { deleted?: string[]; added?: { skill_id: string; span: string }[]; skip?: boolean };

type Props = {
  gold: AdjState | null;
  file: "jd" | "resume";
  busy: "load" | "decide" | null;
  flash: string | null;
  onSwitchFile: (file: "jd" | "resume") => void;
  onDecide: (payload: AdjDecision) => Promise<boolean>;
};

type Term = { kind: "kept" | "add"; id: string };

// 原文里两类标记：自动留的技能名走墨色，草稿提案的原句走强调色；勾选中的提案反白。
function highlight(text: string, terms: Map<string, Term>, selected: Set<string>): ReactNode {
  const keys = [...terms.keys()].sort((a, b) => b.length - a.length);
  if (!keys.length) return text;
  const pattern = new RegExp(`(${keys.map((t) => t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|")})`, "gi");
  return text.split(pattern).map((part, i) => {
    const term = terms.get(part.toLowerCase());
    if (!term) return part;
    return (
      <mark key={i} data-kind={term.kind} data-on={term.kind === "add" && selected.has(term.id) ? "true" : undefined}>
        {part}
      </mark>
    );
  });
}

function toggle<T>(set: Set<T>, key: T): Set<T> {
  const next = new Set(set);
  if (next.has(key)) next.delete(key);
  else next.add(key);
  return next;
}

export default function GoldBoard({ gold, file, busy, flash, onSwitchFile, onDecide }: Props) {
  const row = gold?.row ?? null;
  const [selDel, setSelDel] = useState<Set<string>>(new Set());
  const [selAdd, setSelAdd] = useState<Set<string>>(new Set());

  // 换行就清空勾选，防止上一行的选择带到下一行。
  useEffect(() => {
    setSelDel(new Set());
    setSelAdd(new Set());
  }, [row?.id]);

  const terms = useMemo(() => {
    const map = new Map<string, Term>();
    if (!row) return map;
    for (const k of row.kept) if (k.name && k.name.length > 1) map.set(k.name.toLowerCase(), { kind: "kept", id: k.id });
    for (const p of row.proposals) if (p.span && p.span.length > 1) map.set(p.span.toLowerCase(), { kind: "add", id: p.skill_id });
    return map;
  }, [row]);

  const locked = busy !== null || !row;
  const allDel = Boolean(row?.suspects.length) && row!.suspects.every((s) => selDel.has(s.id));
  const allAdd = Boolean(row?.proposals.length) && row!.proposals.every((p) => selAdd.has(p.skill_id));

  function toggleAllDel() {
    if (!row) return;
    setSelDel(allDel ? new Set() : new Set(row.suspects.map((s) => s.id)));
  }

  function toggleAllAdd() {
    if (!row) return;
    setSelAdd(allAdd ? new Set() : new Set(row.proposals.map((p) => p.skill_id)));
  }

  function submit() {
    if (!row || locked) return;
    const added = row.proposals.filter((p) => selAdd.has(p.skill_id)).map((p) => ({ skill_id: p.skill_id, span: p.span }));
    onDecide({ deleted: [...selDel], added });
  }

  function skip() {
    if (!row || locked) return;
    onDecide({ skip: true });
  }

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      const target = event.target as HTMLElement;
      if (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || event.metaKey || event.ctrlKey || event.altKey) return;
      if (!row) return;
      // 处理中吞掉快捷键，避免连按导致重复写回。
      if (busy) {
        if (["d", "a", "s", "Enter", "ArrowRight", "Escape"].includes(event.key)) event.preventDefault();
        return;
      }
      if (event.key === "d" && row.suspects.length) toggleAllDel();
      else if (event.key === "a" && row.proposals.length) toggleAllAdd();
      else if (event.key === "s" || event.key === "ArrowRight") skip();
      else if (event.key === "Enter") {
        event.preventDefault();
        submit();
      } else if (event.key === "Escape") {
        setSelDel(new Set());
        setSelAdd(new Set());
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  const summary = (() => {
    const parts: string[] = [];
    if (selDel.size) parts.push(`删 ${selDel.size}`);
    if (selAdd.size) parts.push(`加 ${selAdd.size}`);
    return parts.length ? parts.join(" · ") : "全部保留";
  })();

  const status = busy === "decide" ? "写回中…" : busy === "load" ? "载入下一行…" : flash;
  const pct = gold && gold.total ? Math.round((gold.done / gold.total) * 100) : 0;

  return (
    <section className="adj" aria-label="金标裁决" aria-busy={busy ? "true" : undefined}>
      <div className="adj-head">
        <div className="seg" role="group" aria-label="金标文件">
          <button type="button" aria-pressed={file === "jd"} disabled={busy !== null} onClick={() => onSwitchFile("jd")}>JD 金标</button>
          <button type="button" aria-pressed={file === "resume"} disabled={busy !== null} onClick={() => onSwitchFile("resume")}>简历金标</button>
        </div>
        {gold ? (
          <div className="adj-progress" title={`已裁决 ${gold.done} / ${gold.total}`}>
            <span>{gold.done}<i>/{gold.total}</i></span>
            <div className="adj-progress-bar" role="progressbar" aria-valuemin={0} aria-valuemax={gold.total} aria-valuenow={gold.done}><b style={{ width: `${pct}%` }} /></div>
          </div>
        ) : null}
        <p className="hint">自动留的是原文或草稿可溯的金标，只裁存疑与提案。勾选后 <kbd>⏎</kbd> 提交 · <kbd>d</kbd> 全选存疑 <kbd>a</kbd> 全选提案 <kbd>s</kbd> 跳过 <kbd>esc</kbd> 清空</p>
      </div>

      {gold === null && busy === "load" ? <p className="empty adj-loading"><i className="adj-dot" />载入裁决队列…</p> : null}
      {gold?.draft_missing ? <p className="empty">这一行还没有草稿，先在主机跑 python -m app.eval draft。</p> : null}
      {gold && !gold.row && !gold.draft_missing ? <p className="empty">该文件已全部裁决。</p> : null}

      {row ? (
        <article className="adj-card" data-busy={busy ?? undefined}>
          <div className="adj-text">
            <h2>{row.title}</h2>
            {row.source_path ? <p className="adj-source">证据：{row.source_path}</p> : null}
            <p className="hint">先读原文，再勾选删除或加入的技能。点击“提交”才会写回；不确定时跳过。</p>
            <p className="adj-original">{highlight(row.text, terms, selAdd)}</p>
            <p className="adj-legend" aria-hidden="true">
              <mark data-kind="kept">自动留</mark>
              <mark data-kind="add">提案原句</mark>
              <mark data-kind="add" data-on="true">已勾选的提案</mark>
            </p>
          </div>

          <div className="adj-side">
            <section>
              <h3>自动留 <b>{row.kept.length}</b></h3>
              <p className="hint">{row.kept.map((k) => k.name).join("、") || "（无）"}</p>
            </section>

            <section>
              <h3>
                存疑 <b>{row.suspects.length}</b>
                {row.suspects.length ? (
                  <button className="ghost small" type="button" disabled={locked} aria-pressed={allDel} onClick={toggleAllDel}>
                    {allDel ? "取消全选" : "全选删除"} <kbd>d</kbd>
                  </button>
                ) : null}
              </h3>
              {row.suspects.length ? (
                <ul className="adj-list" role="group" aria-label="勾选要删除的存疑技能">
                  {row.suspects.map((s) => {
                    const on = selDel.has(s.id);
                    return (
                      <li key={s.id} data-on={on ? "true" : undefined} data-act="del">
                        <label>
                          <input type="checkbox" checked={on} disabled={locked} onChange={() => setSelDel((cur) => toggle(cur, s.id))} />
                          <span>{s.name}</span>
                          <em>{on ? "删除" : "保留"}</em>
                        </label>
                      </li>
                    );
                  })}
                </ul>
              ) : <p className="hint">原文与草稿都能找到，无存疑。</p>}
            </section>

            <section>
              <h3>
                提案加 <b>{row.proposals.length}</b>
                {row.proposals.length ? (
                  <button className="ghost small" type="button" disabled={locked} aria-pressed={allAdd} onClick={toggleAllAdd}>
                    {allAdd ? "取消全选" : "全选收下"} <kbd>a</kbd>
                  </button>
                ) : null}
              </h3>
              {row.proposals.length ? (
                <ul className="adj-list" role="group" aria-label="勾选要加入的提案">
                  {row.proposals.map((p) => {
                    const on = selAdd.has(p.skill_id);
                    return (
                      <li key={p.skill_id} data-on={on ? "true" : undefined} data-act="add">
                        <label>
                          <input type="checkbox" checked={on} disabled={locked} onChange={() => setSelAdd((cur) => toggle(cur, p.skill_id))} />
                          <span>{p.name} <small>草稿「{p.span}」</small></span>
                          <em>{on ? "加入" : "忽略"}</em>
                        </label>
                      </li>
                    );
                  })}
                </ul>
              ) : <p className="hint">草稿没有新增提案。</p>}
            </section>

            {row.unaligned.length ? <p className="hint">草稿未对齐（不入金标）：{row.unaligned.join("、")}</p> : null}

            <footer className="adj-foot">
              <button className="primary small" type="button" disabled={locked} onClick={submit}>
                {busy === "decide" ? <><i className="adj-dot" />写回中…</> : <>{summary} → 提交 <kbd>⏎</kbd></>}
              </button>
              <button className="ghost small" type="button" disabled={locked} onClick={skip}>跳过 <kbd>s</kbd></button>
              <span className="adj-status" role="status" aria-live="polite" data-kind={busy ? "busy" : flash ? "ok" : undefined}>
                {busy ? <i className="adj-dot" /> : null}
                {status}
              </span>
            </footer>
          </div>
        </article>
      ) : null}
    </section>
  );
}
