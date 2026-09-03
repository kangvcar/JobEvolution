"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { kindLabel } from "../feed-bits";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type QueueEvent = {
  id: string;
  kind: string;
  at: string;
  confidence: number;
  review?: "pending" | "auto_passed";
  payload?: {
    job_name?: string;
    skill_name?: string;
    excerpt?: string;
    error?: string;
    layer?: "high" | "mid" | "low";
    [key: string]: unknown;
  };
};

type AdjRow = {
  id: string;
  title: string;
  text: string;
  kept: { id: string; name: string }[];
  suspects: { id: string; name: string }[];
  proposals: { skill_id: string; name: string; span: string }[];
  unaligned: string[];
};

type AdjState = {
  file: "jd" | "resume";
  total: number;
  done: number;
  row: AdjRow | null;
  draft_missing?: boolean;
};

function reviewLabel(review: QueueEvent["review"]) {
  return review === "auto_passed" ? "自动通过" : "待审";
}

function highlight(text: string, terms: string[]) {
  const clean = [...new Set(terms.filter((t) => t && t.length > 1))].map((t) =>
    t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"),
  );
  if (!clean.length) return text;
  return text.split(new RegExp(`(${clean.join("|")})`, "gi")).map((part, i) =>
    clean.some((c) => part.toLowerCase() === c.toLowerCase()) ? <mark key={i}>{part}</mark> : part,
  );
}

export default function AdminPage() {
  const [password, setPassword] = useState("");
  const [queue, setQueue] = useState<QueueEvent[] | null>(null);
  const [passthrough, setPassthrough] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [tab, setTab] = useState<"queue" | "gold" | "collect">("queue");
  const [portals, setPortals] = useState<{ key: string; type: string; name: string; host?: string; enabled: boolean; builtin?: boolean }[] | null>(null);
  const [collectBusy, setCollectBusy] = useState(false);
  const [feed, setFeed] = useState<string[]>([]);
  const [addName, setAddName] = useState("");
  const [addHost, setAddHost] = useState("");
  const streamRef = useRef<EventSource | null>(null);
  const [adjFile, setAdjFile] = useState<"jd" | "resume">("jd");
  const [gold, setGold] = useState<AdjState | null>(null);
  const [bulkBusy, setBulkBusy] = useState<string | null>(null);
  const [bulkResult, setBulkResult] = useState<Record<string, string>>({});

  const csrfHeaders = (): Record<string, string> => {
    const token = document.cookie.split(";").map((part) => part.trim()).find((part) => part.startsWith("admin_csrf="))?.split("=")[1];
    return token ? { "X-CSRF-Token": decodeURIComponent(token) } : {};
  };

  async function loadQueue() {
    const response = await fetch(`${API}/admin/queue`, { credentials: "include" });
    if (!response.ok) throw new Error("口令错误");
    setQueue(await response.json());
  }

  async function loadNext(file: "jd" | "resume") {
    const response = await fetch(`${API}/admin/adjudicate/next?file=${file}`, { credentials: "include" });
    if (!response.ok) throw new Error("裁决队列读取失败");
    setGold(await response.json());
  }

  async function enter(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    try {
      const response = await fetch(`${API}/admin/login`, { method: "POST", headers: { "Content-Type": "application/json" }, credentials: "include", body: JSON.stringify({ password }) });
      if (!response.ok) throw new Error("口令错误");
      setPassthrough((await response.json()).enabled);
      await loadQueue();
    } catch {
      setError("口令错误");
    }
  }

  async function loadPortals() {
    const response = await fetch(`${API}/admin/portals`, { credentials: "include" });
    if (!response.ok) throw new Error("门户名单读取失败");
    const body = await response.json();
    setPortals(body.portals || []);
    setCollectBusy(Boolean(body.busy));
  }

  function openTab(next: "queue" | "gold" | "collect") {
    setTab(next);
    if (next === "gold" && gold === null) {
      loadNext(adjFile).catch(() => setError("裁决队列读取失败"));
    }
    if (next === "collect") {
      loadPortals().catch(() => setError("门户名单读取失败"));
    }
  }

  useEffect(() => {
    if (tab !== "collect") {
      streamRef.current?.close();
      streamRef.current = null;
      return;
    }
    const types = "collect_started,jd_ingested,collect_portal_failed,collect_finished";
    const source = new EventSource(`${API}/events/stream?types=${encodeURIComponent(types)}`, { withCredentials: true });
    source.onmessage = (event) => {
      try {
        const row = JSON.parse(event.data);
        const line = `${row.type} ${typeof row.payload === "string" ? row.payload : JSON.stringify(row.payload ?? {})}`;
        setFeed((current) => [line, ...current].slice(0, 50));
      } catch {
        /* ignore malformed SSE payloads */
      }
    };
    source.onerror = () => setError("采集事件流中断，刷新管理页后重试");
    streamRef.current = source;
    return () => {
      source.close();
      streamRef.current = null;
    };
  }, [tab]);

  async function togglePortal(key: string, enabled: boolean) {
    setError("");
    const response = await fetch(`${API}/admin/portals/${key}`, { method: "POST", headers: { "Content-Type": "application/json", ...csrfHeaders() }, credentials: "include", body: JSON.stringify({ enabled }) });
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      setError(body.error || "无法更新门户");
      return;
    }
    await loadPortals();
  }

  async function removePortal(key: string) {
    setError("");
    const response = await fetch(`${API}/admin/portals/${key}/delete`, { method: "POST", headers: csrfHeaders(), credentials: "include" });
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      setError(body.error || "无法删除门户");
      return;
    }
    await loadPortals();
  }

  async function addPortal(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    const response = await fetch(`${API}/admin/portals`, { method: "POST", headers: { "Content-Type": "application/json", ...csrfHeaders() }, credentials: "include", body: JSON.stringify({ name: addName, host: addHost }) });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) {
      setError(body.error || "探测失败，未保存");
      return;
    }
    setAddName("");
    setAddHost("");
    setPortals(body.portals || []);
  }

  async function runCollect() {
    setError("");
    const response = await fetch(`${API}/admin/collect`, { method: "POST", headers: csrfHeaders(), credentials: "include" });
    if (response.status === 409) {
      setError("已有采集任务在跑");
      return;
    }
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      setError(body.error || "无法启动采集");
      return;
    }
    setCollectBusy(true);
  }

  function switchAdjFile(file: "jd" | "resume") {
    setAdjFile(file);
    loadNext(file).catch(() => setError("裁决队列读取失败"));
  }

  async function decide(payload: { deleted?: string[]; added?: { skill_id: string; span: string }[]; skip?: boolean }) {
    if (!gold?.row) return;
    setError("");
    const response = await fetch(`${API}/admin/adjudicate/decide`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...csrfHeaders() },
      credentials: "include",
      body: JSON.stringify({ file: gold.file, row_id: gold.row.id, ...payload }),
    });
    if (!response.ok) {
      setError("裁决写回失败");
      return;
    }
    await loadNext(gold.file);
  }

  useEffect(() => {
    if (tab !== "gold" || !gold?.row) return;
    function onKey(event: KeyboardEvent) {
      const target = event.target as HTMLElement;
      if (target.tagName === "INPUT" || target.tagName === "TEXTAREA") return;
      if (event.key === "d" && gold?.row?.suspects.length) {
        decide({ deleted: gold.row.suspects.map((s) => s.id) });
      } else if (event.key === "a" && gold?.row?.proposals.length) {
        decide({ added: gold.row.proposals.map((p) => ({ skill_id: p.skill_id, span: p.span })) });
      } else if (event.key === "s" || event.key === "ArrowRight") {
        decide({ skip: true });
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  async function togglePassthrough() {
    setError("");
    try {
      const response = await fetch(`${API}/admin/passthrough`, {
        method: "PUT",
        headers: { "Content-Type": "application/json", ...csrfHeaders() }, credentials: "include",
        body: JSON.stringify({ enabled: !passthrough }),
      });
      if (!response.ok) throw new Error("开关更新失败");
      setPassthrough((await response.json()).enabled);
      await loadQueue();
    } catch {
      setError("开关更新失败");
    }
  }

  async function review(item: QueueEvent, decision: "approved" | "rejected") {
    setBusy(item.id);
    setError("");
    const payload = item.payload ? { ...item.payload } : undefined;
    const draft = drafts[item.id];
    if (decision === "approved" && payload && draft !== undefined) payload.excerpt = draft;
      const response = await fetch(`${API}/admin/queue/${item.id}/${decision === "approved" ? "approve" : "reject"}`, {
        method: "POST",
      headers: { "Content-Type": "application/json", ...csrfHeaders() }, credentials: "include",
      body: decision === "approved" ? JSON.stringify({ payload }) : undefined,
    });
    if (!response.ok) {
      setError("审核操作失败，请重试");
      setBusy(null);
      return;
    }
    setQueue((items) => items?.filter(({ id }) => id !== item.id) ?? []);
    setBusy(null);
  }

  async function approveAll(jobId: string, versionId: string) {
    const key = `${jobId}:${versionId}`;
    setBulkBusy(key);
    setError("");
    const response = await fetch(`${API}/admin/jobs/${jobId}/versions/${versionId}/approve-all`, { method: "POST", headers: { "Content-Type": "application/json", ...csrfHeaders() }, credentials: "include", body: JSON.stringify({ override_reason: "" }) });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) { setError(body.error || body.detail || "批量审核被拦截，请检查岗位定义、证据和异常增量"); setBulkBusy(null); return; }
    setBulkResult((current) => ({ ...current, [key]: `已批准 ${body.event_ids?.length || 0} 条，批量决定 ${body.batch_id || "已记录"}` }));
    await loadQueue();
    setBulkBusy(null);
  }

  if (queue === null) {
    return (
      <main id="main" className="page admin-page">
        <section className="admin-gate" aria-labelledby="admin-gate-title">
          <h1 id="admin-gate-title">管理</h1>
          <p className="hint">输入口令查看待审队列。</p>
          <form onSubmit={enter}>
            <label htmlFor="admin-password">口令</label>
            <input id="admin-password" type="password" value={password} onChange={(event) => setPassword(event.target.value)} autoFocus required />
            <div className="row">
              <button className="primary" type="submit">进入待审队列</button>
              <button className="ghost" type="button" onClick={() => window.history.back()}>取消</button>
            </div>
          </form>
          {error ? <p className="admin-error" role="alert">{error}</p> : null}
        </section>
      </main>
    );
  }

  const terms = gold?.row
    ? [...gold.row.kept.map((k) => k.name), ...gold.row.proposals.map((p) => p.span)]
    : [];
  const bulkGroups = [...(queue || []).reduce((groups, item) => {
    const jobId = String(item.payload?.job_id || "");
    if (!jobId) return groups;
    const versionId = String(item.payload?.version_id || "latest");
    const key = `${jobId}:${versionId}`;
    const group = groups.get(key) || { jobId, versionId, name: String(item.payload?.job_name || jobId), count: 0 };
    group.count += 1;
    groups.set(key, group);
    return groups;
  }, new Map<string, { jobId: string; versionId: string; name: string; count: number }>()).values()];

  return (
    <main id="main" className="page admin-page">
      <div className="admin-event-head">
        <h1>管理</h1>
        <div className="admin-tabs" role="tablist">
          <button type="button" role="tab" aria-pressed={tab === "queue"} onClick={() => openTab("queue")}>待审队列</button>
          <button type="button" role="tab" aria-pressed={tab === "gold"} onClick={() => openTab("gold")}>金标裁决</button>
          <button type="button" role="tab" aria-pressed={tab === "collect"} onClick={() => openTab("collect")}>官网采集</button>
        </div>
        <button className="ghost" type="button" aria-pressed={passthrough} onClick={togglePassthrough}>
          {passthrough ? "直通开启" : "直通关闭"}
        </button>
        <button className="ghost" type="button" onClick={async () => { await fetch(`${API}/admin/logout`, { method: "POST", credentials: "include", headers: csrfHeaders() }); window.location.reload(); }}>退出</button>
      </div>
      {error ? <p className="admin-error" role="alert">{error}</p> : null}

      {tab === "queue" ? (
        <>
          <p className="hint">口令通过后显示尚未入谱的演化事件。</p>
          {queue.length === 0 ? <p className="empty">暂无待审演化事件</p> : null}
          {bulkGroups.length ? <section className="bulk-groups" aria-label="岗位版本批量审核"><h2>按岗位版本审核</h2>{bulkGroups.map((group) => { const key = `${group.jobId}:${group.versionId}`; return <article key={key}><div><strong>{group.name}</strong><span>{group.count} 条待审提案 · 版本 {group.versionId}</span></div><button className="primary" type="button" disabled={bulkBusy === key} onClick={() => approveAll(group.jobId, group.versionId)}>一键全部批准</button>{bulkResult[key] ? <p className="hint" role="status">{bulkResult[key]}</p> : null}</article>; })}</section> : null}
          <ul className="admin-queue" aria-label="待审演化事件">
            {queue.map((item) => {
              const payload = item.payload ?? {};
              const subject = payload.job_name || payload.skill_name || "未标注岗位或技能点";
              const summary = payload.excerpt || payload.error || "暂无摘要";
              const layerLabel = payload.layer === "low" ? "低置信，不可直通" : payload.layer === "mid" ? "中置信，需审核" : payload.layer === "high" ? "高置信，需审核" : "";
              return (
                <li key={item.id}>
                  <div className="admin-event-head"><strong>{kindLabel(item.kind)} · {reviewLabel(item.review)}</strong><time dateTime={item.at}>{item.at.slice(0, 10)}</time></div>
                  <p className="admin-event-subject">{subject}</p>
                  <p className="hint">原始提案：{summary}</p>
                  {layerLabel ? <p className="hint">{layerLabel}</p> : null}
                  {item.review !== "auto_passed" && item.kind !== "extract_failed" ? (
                    <label>
                      最终事实（可选改写，原稿仍保留）
                      <textarea value={drafts[item.id] ?? (payload.excerpt || "")} onChange={(event) => setDrafts((current) => ({ ...current, [item.id]: event.target.value }))} rows={3} />
                    </label>
                  ) : null}
                  {item.review !== "auto_passed" ? (
                  <div className="row">
                    <button className="primary" type="button" disabled={busy === item.id} onClick={() => review(item, "approved")}>确认发布</button>
                    <button className="ghost" type="button" disabled={busy === item.id} onClick={() => review(item, "rejected")}>驳回</button>
                  </div>
                  ) : null}
                </li>
              );
            })}
          </ul>
        </>
      ) : null}

      {tab === "gold" ? (
        <section aria-label="金标裁决">
          <p className="hint">
            ADR-0011 两段修订的裁决段：自动留的是原文或草稿可溯的金标，你只裁存疑与提案。
            快捷键 d=全删存疑 a=全收提案 s=跳过。
          </p>
          <div className="admin-event-head">
            <div className="admin-tabs" role="group" aria-label="金标文件">
              <button type="button" aria-pressed={adjFile === "jd"} onClick={() => switchAdjFile("jd")}>JD 金标</button>
              <button type="button" aria-pressed={adjFile === "resume"} onClick={() => switchAdjFile("resume")}>简历金标</button>
            </div>
            {gold ? <p className="hint">进度 {gold.done}/{gold.total}</p> : null}
          </div>
          {gold?.draft_missing ? <p className="empty">这一行还没有草稿，先在主机跑 python -m app.eval draft。</p> : null}
          {gold && !gold.row && !gold.draft_missing ? <p className="empty">该文件已全部裁决。</p> : null}
          {gold?.row ? (
            <article className="adj-card">
              <h2>{gold.row.title}</h2>
              <p className="adj-text">{highlight(gold.row.text, terms)}</p>
              <p className="hint">自动留 {gold.row.kept.length}：{gold.row.kept.map((k) => k.name).join("、") || "（无）"}</p>
              {gold.row.suspects.length ? (
                <div>
                  <div className="admin-event-head">
                    <h3>存疑（金标里原文与草稿都找不到）</h3>
                    <button className="ghost" type="button" onClick={() => decide({ deleted: gold.row!.suspects.map((s) => s.id) })}>全删（d）</button>
                  </div>
                  <ul className="adj-list">
                    {gold.row.suspects.map((s) => (
                      <li key={s.id}>
                        <span>{s.name}</span>
                        <span className="row">
                          <button className="primary" type="button" onClick={() => decide({ deleted: [s.id] })}>删</button>
                          <button className="ghost" type="button" onClick={() => decide({})}>留</button>
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}
              {gold.row.proposals.length ? (
                <div>
                  <div className="admin-event-head">
                    <h3>提案加（草稿对齐到词表）</h3>
                    <button className="ghost" type="button" onClick={() => decide({ added: gold.row!.proposals.map((p) => ({ skill_id: p.skill_id, span: p.span })) })}>全收（a）</button>
                  </div>
                  <ul className="adj-list">
                    {gold.row.proposals.map((p) => (
                      <li key={p.skill_id}>
                        <span>{p.name}（草稿: {p.span}）</span>
                        <button className="primary" type="button" onClick={() => decide({ added: [p] })}>加</button>
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}
              {gold.row.unaligned.length ? (
                <p className="hint">草稿未对齐（仅提示，不入金标）：{gold.row.unaligned.join("、")}</p>
              ) : null}
              <div className="row">
                <button className="ghost" type="button" onClick={() => decide({ skip: true })}>跳过此行（s）</button>
              </div>
            </article>
          ) : null}
        </section>
      ) : null}

      {tab === "collect" ? (
        <section aria-label="官网采集">
          <p className="hint">只打公司官网公开 JSON。立即采集与每日任务共用一把锁，当晚抽取进待审，求职者页不订这条流。</p>
          <div className="row">
            <button className="primary" type="button" disabled={collectBusy} onClick={runCollect}>立即采集</button>
            {collectBusy ? <p className="hint" role="status">任务在跑或刚已启动</p> : null}
          </div>
          <ul className="admin-queue" aria-label="招聘门户">
            {(portals || []).map((portal) => (
              <li key={portal.key}>
                <div className="admin-event-head">
                  <strong>{portal.name}</strong>
                  <span className="hint">{portal.type}{portal.host ? ` · ${portal.host}` : ""}</span>
                </div>
                <div className="row">
                  <label>
                    <input type="checkbox" checked={portal.enabled} onChange={(event) => togglePortal(portal.key, event.target.checked)} />
                    启用
                  </label>
                  {portal.builtin ? <p className="hint">内置，不可删</p> : <button className="ghost" type="button" onClick={() => removePortal(portal.key)}>删除</button>}
                </div>
              </li>
            ))}
          </ul>
          <form onSubmit={addPortal} aria-label="新增飞书门户">
            <label htmlFor="portal-name">名称</label>
            <input id="portal-name" value={addName} onChange={(event) => setAddName(event.target.value)} required />
            <label htmlFor="portal-host">飞书域名</label>
            <input id="portal-host" value={addHost} onChange={(event) => setAddHost(event.target.value)} placeholder="zhipu-ai.jobs.feishu.cn" required />
            <button className="primary" type="submit">探测并保存</button>
          </form>
          <h2>采集事件</h2>
          <ul className="admin-queue" aria-live="polite" aria-label="采集事件">
            {feed.length === 0 ? <li className="empty">尚无事件</li> : feed.map((line, index) => <li key={`${index}-${line.slice(0, 24)}`}><p className="hint">{line}</p></li>)}
          </ul>
        </section>
      ) : null}
    </main>
  );
}
