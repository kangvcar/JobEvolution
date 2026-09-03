"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import QueueBoard, { QueueEvent } from "./queue-board";
import { Portal, PortalTable } from "./portal-table";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

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

type OpsEntry = { status: string; at?: number };
type Ops = { status: Record<string, OpsEntry>; stale: boolean };
type FeedLine = { at: string; type: string; text: string };

const OPS_LABEL: Record<string, string> = { pipeline: "管线", backup: "备份", publish: "发布" };

function highlight(text: string, terms: string[]) {
  const clean = [...new Set(terms.filter((t) => t && t.length > 1))].map((t) =>
    t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"),
  );
  if (!clean.length) return text;
  return text.split(new RegExp(`(${clean.join("|")})`, "gi")).map((part, i) =>
    clean.some((c) => part.toLowerCase() === c.toLowerCase()) ? <mark key={i}>{part}</mark> : part,
  );
}

function ago(at?: number) {
  if (!at) return "无记录";
  const hours = Math.floor((Date.now() / 1000 - at) / 3600);
  return hours < 1 ? "1 小时内" : hours < 48 ? `${hours} 小时前` : `${Math.floor(hours / 24)} 天前`;
}

// 把采集事件的 payload 压成一行人话；字段来自 collectors/sink.py。
function feedText(type: string, payload: unknown) {
  if (typeof payload !== "object" || payload === null) return String(payload ?? "");
  const p = payload as Record<string, unknown>;
  if (type === "jd_ingested") return `${p.company ?? ""} · ${p.title ?? ""}`;
  if (type === "collect_portal_failed") return `${p.key ?? ""} ${p.error ?? ""}`;
  if (type === "collect_started" && Array.isArray(p.portals)) return `${p.portals.length} 个门户`;
  if (type === "collect_finished" && Array.isArray(p.portals)) {
    const stats = p.portals as { ingested?: number; error?: string }[];
    const ingested = stats.reduce((n, s) => n + (s.ingested || 0), 0);
    const failed = stats.filter((s) => s.error).length;
    return `入库 ${ingested} 条${failed ? `，${failed} 个门户失败` : ""}`;
  }
  return JSON.stringify(p);
}

export default function AdminPage() {
  const [password, setPassword] = useState("");
  const [queue, setQueue] = useState<QueueEvent[] | null>(null);
  const [passthrough, setPassthrough] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [tab, setTab] = useState<"queue" | "gold" | "collect">("queue");
  const [portals, setPortals] = useState<Portal[] | null>(null);
  const [collectBusy, setCollectBusy] = useState(false);
  const [feed, setFeed] = useState<FeedLine[]>([]);
  const streamRef = useRef<EventSource | null>(null);
  const [adjFile, setAdjFile] = useState<"jd" | "resume">("jd");
  const [gold, setGold] = useState<AdjState | null>(null);
  const [ops, setOps] = useState<Ops | null>(null);
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

  async function loadPortals() {
    const response = await fetch(`${API}/admin/portals`, { credentials: "include" });
    if (!response.ok) throw new Error("门户名单读取失败");
    const body = await response.json();
    setPortals(body.portals || []);
    setCollectBusy(Boolean(body.busy));
  }

  async function loadOps() {
    const response = await fetch(`${API}/admin/ops/status`, { credentials: "include" });
    if (response.ok) setOps(await response.json());
  }

  async function enter(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    try {
      const response = await fetch(`${API}/admin/login`, { method: "POST", headers: { "Content-Type": "application/json" }, credentials: "include", body: JSON.stringify({ password }) });
      if (!response.ok) throw new Error("口令错误");
      setPassthrough((await response.json()).enabled);
      await loadQueue();
      // 顶栏三个计数并行取；任一失败只影响自己那格，不拦登录。
      loadPortals().catch(() => null);
      loadNext("jd").catch(() => null);
      loadOps().catch(() => null);
    } catch {
      setError("口令错误");
    }
  }

  function openTab(next: "queue" | "gold" | "collect") {
    setTab(next);
    setError("");
    if (next === "gold" && gold === null) loadNext(adjFile).catch(() => setError("裁决队列读取失败"));
    if (next === "collect") loadPortals().catch(() => setError("门户名单读取失败"));
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
        // SSE id 是 Redis 流 id「毫秒-序号」，取毫秒当事件时间。
        const ms = Number(String(event.lastEventId).split("-")[0]);
        const at = Number.isFinite(ms) && ms > 0 ? new Date(ms).toTimeString().slice(0, 8) : "--:--:--";
        setFeed((current) => [{ at, type: row.type, text: feedText(row.type, row.payload) }, ...current].slice(0, 50));
        if (row.type === "collect_started") setCollectBusy(true);
        if (row.type === "collect_finished") setCollectBusy(false);
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

  async function post(path: string, body?: unknown) {
    setError("");
    const response = await fetch(`${API}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...csrfHeaders() },
      credentials: "include",
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    return response;
  }

  async function togglePortal(key: string, enabled: boolean) {
    const response = await post(`/admin/portals/${key}`, { enabled });
    if (!response.ok) {
      setError((await response.json().catch(() => ({}))).error || "无法更新门户");
      return;
    }
    await loadPortals();
  }

  async function removePortal(key: string) {
    const response = await post(`/admin/portals/${key}/delete`);
    if (!response.ok) {
      setError((await response.json().catch(() => ({}))).error || "无法删除门户");
      return;
    }
    await loadPortals();
  }

  async function addPortal(name: string, host: string) {
    const response = await post("/admin/portals", { name, host });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) {
      setError(body.error || "探测失败，未保存");
      return false;
    }
    setPortals(body.portals || []);
    return true;
  }

  async function runCollect() {
    const response = await post("/admin/collect");
    if (response.status === 409) {
      setError("已有采集任务在跑");
      return;
    }
    if (!response.ok) {
      setError((await response.json().catch(() => ({}))).error || "无法启动采集");
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
    const response = await post("/admin/adjudicate/decide", { file: gold.file, row_id: gold.row.id, ...payload });
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

  async function review(item: QueueEvent, decision: "approved" | "rejected", draft?: string) {
    setBusy(item.id);
    setError("");
    const payload = item.payload ? { ...item.payload } : undefined;
    if (decision === "approved" && payload && draft !== undefined) payload.excerpt = draft;
    const response = await post(`/admin/queue/${item.id}/${decision === "approved" ? "approve" : "reject"}`, decision === "approved" ? { payload } : undefined);
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
    const response = await post(`/admin/jobs/${jobId}/versions/${versionId}/approve-all`, { override_reason: "" });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) {
      setError(body.error || body.detail || "批量审核被拦截，请检查岗位定义、证据和异常增量");
      setBulkBusy(null);
      return;
    }
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

  const terms = gold?.row ? [...gold.row.kept.map((k) => k.name), ...gold.row.proposals.map((p) => p.span)] : [];
  const enabledPortals = portals?.filter((p) => p.enabled).length;

  return (
    <main id="main" className="page admin-page">
      <header className="admin-bar">
        <h1>管理</h1>
        <nav className="admin-tabs" role="tablist" aria-label="管理分区">
          <button type="button" role="tab" aria-selected={tab === "queue"} onClick={() => openTab("queue")}>
            待审 <b>{queue.length}</b>
          </button>
          <button type="button" role="tab" aria-selected={tab === "gold"} onClick={() => openTab("gold")}>
            金标 <b>{gold ? `${gold.done}/${gold.total}` : "–"}</b>
          </button>
          <button type="button" role="tab" aria-selected={tab === "collect"} onClick={() => openTab("collect")} data-busy={collectBusy || undefined}>
            采集 <b>{portals ? `${enabledPortals}/${portals.length}` : "–"}</b>
          </button>
        </nav>
        <ul className="ops-dots" aria-label="运维状态" title={ops?.stale ? "管线超过 48 小时没有成功记录" : undefined}>
          {Object.entries(OPS_LABEL).map(([key, label]) => {
            const entry = ops?.status?.[key];
            const state = !entry || entry.status === "unknown" ? "unknown" : entry.status === "failed" ? "failed" : "ok";
            return (
              <li key={key} data-state={state} title={`${label}：${entry?.status ?? "unknown"} · ${ago(entry?.at)}`}>
                <i /> {label}
              </li>
            );
          })}
        </ul>
        <button className="ghost small" type="button" aria-pressed={passthrough} onClick={togglePassthrough}>
          {passthrough ? "自动审核开启" : "自动审核关闭"}
        </button>
        <button className="ghost small" type="button" onClick={async () => { await fetch(`${API}/admin/logout`, { method: "POST", credentials: "include", headers: csrfHeaders() }); window.location.reload(); }}>退出</button>
      </header>
      {error ? <p className="admin-error" role="alert">{error}</p> : null}

      {tab === "queue" ? (
        <QueueBoard queue={queue} busy={busy} bulkBusy={bulkBusy} bulkResult={bulkResult} onReview={review} onApproveAll={approveAll} />
      ) : null}

      {tab === "gold" ? (
        <section className="adj" aria-label="金标裁决">
          <div className="adj-head">
            <div className="seg" role="group" aria-label="金标文件">
              <button type="button" aria-pressed={adjFile === "jd"} onClick={() => switchAdjFile("jd")}>JD 金标</button>
              <button type="button" aria-pressed={adjFile === "resume"} onClick={() => switchAdjFile("resume")}>简历金标</button>
            </div>
            <p className="hint">自动留的是原文或草稿可溯的金标，只裁存疑与提案。<kbd>d</kbd> 全删存疑 <kbd>a</kbd> 全收提案 <kbd>s</kbd> 跳过</p>
          </div>
          {gold?.draft_missing ? <p className="empty">这一行还没有草稿，先在主机跑 python -m app.eval draft。</p> : null}
          {gold && !gold.row && !gold.draft_missing ? <p className="empty">该文件已全部裁决。</p> : null}
          {gold?.row ? (
            <article className="adj-card">
              <div className="adj-text">
                <h2>{gold.row.title}</h2>
                <p>{highlight(gold.row.text, terms)}</p>
              </div>
              <div className="adj-side">
                <section>
                  <h3>自动留 <b>{gold.row.kept.length}</b></h3>
                  <p className="hint">{gold.row.kept.map((k) => k.name).join("、") || "（无）"}</p>
                </section>
                <section>
                  <h3>存疑 <b>{gold.row.suspects.length}</b>{gold.row.suspects.length ? <button className="ghost small" type="button" onClick={() => decide({ deleted: gold.row!.suspects.map((s) => s.id) })}>全删 d</button> : null}</h3>
                  {gold.row.suspects.length ? (
                    <ul className="adj-list">
                      {gold.row.suspects.map((s) => (
                        <li key={s.id}>
                          <span>{s.name}</span>
                          <button className="primary small" type="button" onClick={() => decide({ deleted: [s.id] })}>删</button>
                          <button className="ghost small" type="button" onClick={() => decide({})}>留</button>
                        </li>
                      ))}
                    </ul>
                  ) : <p className="hint">原文与草稿都能找到，无存疑。</p>}
                </section>
                <section>
                  <h3>提案加 <b>{gold.row.proposals.length}</b>{gold.row.proposals.length ? <button className="ghost small" type="button" onClick={() => decide({ added: gold.row!.proposals.map((p) => ({ skill_id: p.skill_id, span: p.span })) })}>全收 a</button> : null}</h3>
                  {gold.row.proposals.length ? (
                    <ul className="adj-list">
                      {gold.row.proposals.map((p) => (
                        <li key={p.skill_id}>
                          <span>{p.name} <small>草稿 {p.span}</small></span>
                          <button className="primary small" type="button" onClick={() => decide({ added: [p] })}>加</button>
                        </li>
                      ))}
                    </ul>
                  ) : <p className="hint">草稿没有新增提案。</p>}
                </section>
                {gold.row.unaligned.length ? <p className="hint">草稿未对齐（不入金标）：{gold.row.unaligned.join("、")}</p> : null}
                <button className="ghost small" type="button" onClick={() => decide({ skip: true })}>跳过此行 s</button>
              </div>
            </article>
          ) : null}
        </section>
      ) : null}

      {tab === "collect" ? (
        <PortalTable
          portals={portals || []}
          collectBusy={collectBusy}
          feed={feed}
          onRunCollect={runCollect}
          onToggle={togglePortal}
          onRemove={removePortal}
          onAdd={addPortal}
        />
      ) : null}
    </main>
  );
}
