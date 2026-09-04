"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import { useGSAP } from "@gsap/react";
import { kindLabel } from "./feed-bits";
import "./home.css";

if (typeof window !== "undefined") gsap.registerPlugin(useGSAP, ScrollTrigger);

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const PULSE_INTERVAL = 3000;
// 展示层的滚动节奏。数据本身按 PULSE_INTERVAL 轮询，池子里的事件循环推入，保证页面一直在动。
const INTAKE_TICK = 2600;
const EVENT_TICK = 4200;
const TAPE_SPEED = 46; // px / s

const DOMAIN_ORDER = ["ai", "data", "system", "iot"];
const DOMAIN: Record<string, string> = {
  ai: "人工智能",
  data: "大数据",
  system: "智能系统",
  iot: "物联网",
};
const STATUS: Record<string, { label: string; tone: string }> = {
  formed: { label: "成型", tone: "ok" },
  emerging: { label: "萌芽", tone: "hot" },
  candidate: { label: "候选", tone: "mid" },
};
// 赛题默认对照对：诊断页默认岗位与它最近的萌芽岗。首页按名字找 id，图谱重建时名字不变。
const PAIR = ["大模型应用工程师", "Agent 工程师"];

type Card = {
  id: string;
  name: string;
  status: string;
  domain: string;
  n_sources?: number;
  n_added?: number;
  n_expired?: number;
  last_change?: string;
};
type Board = { candidate: Card[]; emerging: Card[]; formed: Card[] };
type Meta = {
  graph_release?: { id: string | null; period: string; published_at: string | null };
  resume_retention_seconds?: number;
  resume_payload?: string;
  model_provider?: string;
};
type FeedEvent = { at: string; text: string; review?: string; kind?: string; n?: number; skills?: string[] };
type Feed = {
  emerging: number;
  formed: number;
  candidate: number;
  in_graph: number;
  pipeline: { source: string; n: number }[];
  heat: { id: string; name: string; v: number }[];
  events: FeedEvent[];
  rise: { name: string; job?: string }[];
  fall: { name: string; job?: string }[];
};
type IntakeRaw = {
  id: string;
  at: string;
  kind: "ingest" | "propose" | "merge" | "barred" | "collect_start" | "collect_done" | string;
  company?: string;
  title?: string;
  domain?: string;
  job?: string;
  skill?: string;
  edge?: string;
  sources?: number;
  read?: number;
  ingested?: number;
};
type Pulse = {
  server_time: string;
  collect: {
    running: boolean;
    status: string;
    started_at?: string | null;
    finished_at?: string | null;
    sources?: number;
    done?: number;
    failed?: number;
    read?: number;
    ingested?: number;
    current?: string[];
  };
  intake: IntakeRaw[];
};
type Slice = {
  job: { id: string; name: string; status: string };
  requires: { kind?: string }[];
  evidence: { company?: string }[];
};
// 统一后的流水行：采集事件与演化事件都落到这个形状，供跑马灯与滚动列表复用。
type Row = { id: string; at: string; type: string; text: string; review?: string };

async function get<T>(path: string): Promise<T | null> {
  try {
    const res = await fetch(`${API}${path}`, { cache: "no-store" });
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  }
}

function day(value?: string | null) {
  return value ? value.slice(0, 10) : "";
}
function hms(value?: string | null) {
  if (!value) return "";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value.slice(11, 19);
  return d.toLocaleTimeString("zh-CN", { hour12: false });
}
function hm(value?: string | null) {
  return hms(value).slice(0, 5);
}
function duration(from?: string | null, to?: string | null) {
  if (!from || !to) return "";
  const s = Math.round((new Date(to).getTime() - new Date(from).getTime()) / 1000);
  if (!Number.isFinite(s) || s <= 0) return "";
  const m = Math.floor(s / 60);
  return m ? `${m} 分 ${s % 60} 秒` : `${s} 秒`;
}
function num(value: number | undefined | null) {
  return typeof value === "number" ? value.toLocaleString("zh-CN") : "—";
}
function reducedMotion() {
  return typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

function intakeRow(r: IntakeRaw): Row {
  const edge = r.edge === "preferred" ? "加分" : "必备";
  switch (r.kind) {
    case "ingest":
      return { id: r.id, at: r.at, type: "JD 入库", text: [r.company, r.title].filter(Boolean).join(" · ") || "新 JD" };
    case "propose":
      return {
        id: r.id,
        at: r.at,
        type: "要求提案",
        text: `${r.job ?? "岗位"} ← ${r.skill ?? "技能"}（${edge}${r.sources ? `，${r.sources} 源` : ""}）`,
      };
    case "merge":
      return { id: r.id, at: r.at, type: "合并提案", text: `技能合并：${r.skill ?? ""}` };
    case "barred":
      return { id: r.id, at: r.at, type: "已拦截", text: "低置信抽取，未入图谱" };
    case "collect_start":
      return { id: r.id, at: r.at, type: "采集开始", text: `${r.sources ?? 0} 个门户排队` };
    case "collect_done":
      return {
        id: r.id,
        at: r.at,
        type: "采集完成",
        text: `${r.sources ?? 0} 门户 · 读取 ${num(r.read)} · 入库 ${num(r.ingested)}`,
      };
    default:
      return { id: r.id, at: r.at, type: r.kind, text: "" };
  }
}

function eventRow(e: FeedEvent, i: number): Row {
  const label = kindLabel(e.kind ?? "");
  const body = e.text && e.text !== e.kind ? e.text : label;
  return {
    id: `${e.at}-${i}`,
    at: e.at,
    type: label,
    text: e.n ? `${body} 新增 ${e.n} 条要求` : body,
    review: e.review,
  };
}

function reviewTone(review?: string) {
  if (review === "待审") return "mid";
  if (review === "驳回" || review === "已撤回") return "warn";
  return "ok";
}

/* ---------- 动效小组件 ---------- */

// 数字读数：首次出现从 0 数到位，之后随数据变化从上一值滚到新值。
function Count({ value, className }: { value?: number | null; className?: string }) {
  const ref = useRef<HTMLSpanElement>(null);
  const prev = useRef<number | null>(null);
  useGSAP(
    () => {
      const el = ref.current;
      if (!el || typeof value !== "number") return;
      if (reducedMotion() || prev.current === value) {
        el.textContent = num(value);
        prev.current = value;
        return;
      }
      const obj = { v: prev.current ?? 0 };
      el.textContent = num(Math.round(obj.v));
      gsap.to(obj, {
        v: value,
        duration: prev.current === null ? 1.1 : 0.6,
        ease: "power2.out",
        onUpdate: () => {
          el.textContent = num(Math.round(obj.v));
        },
      });
      prev.current = value;
    },
    { dependencies: [value] },
  );
  return (
    <span ref={ref} className={className}>
      {num(value)}
    </span>
  );
}

function Clock() {
  const [t, setT] = useState("");
  useEffect(() => {
    const tick = () => setT(new Date().toLocaleTimeString("zh-CN", { hour12: false }));
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);
  return <span className="hm-clock mono">{t || "--:--:--"}</span>;
}

// 跑马灯：两份相同内容首尾相接，位移一半即无缝循环。悬停暂停。
function Tape({ rows }: { rows: Row[] }) {
  const root = useRef<HTMLDivElement>(null);
  const track = useRef<HTMLDivElement>(null);
  useGSAP(
    () => {
      const el = track.current;
      if (!el || rows.length === 0 || reducedMotion()) return;
      const half = el.scrollWidth / 2;
      if (half <= 0) return;
      const tween = gsap.to(el, { xPercent: -50, ease: "none", duration: half / TAPE_SPEED, repeat: -1 });
      const pause = () => tween.pause();
      const play = () => tween.play();
      const box = root.current;
      box?.addEventListener("mouseenter", pause);
      box?.addEventListener("mouseleave", play);
      return () => {
        box?.removeEventListener("mouseenter", pause);
        box?.removeEventListener("mouseleave", play);
      };
    },
    { dependencies: [rows.length], scope: root },
  );
  const half = (key: string) => (
    <div className="hm-tape-half" key={key} aria-hidden={key === "b" || undefined}>
      {rows.map((r) => (
        <span className="hm-tape-item" key={`${key}-${r.id}`}>
          <span className="mono mute">{hms(r.at)}</span>
          <span className="hm-kind">{r.type}</span>
          <span>{r.text}</span>
        </span>
      ))}
    </div>
  );
  return (
    <div className="hm-tape" ref={root} aria-label="实时采集与演化流水">
      <div className="hm-tape-label">
        <i className="hm-live-dot" aria-hidden />
        <span>LIVE</span>
        <Clock />
      </div>
      <div className="hm-tape-viewport">
        {rows.length ? (
          <div className="hm-tape-track" ref={track}>
            {half("a")}
            {half("b")}
          </div>
        ) : (
          <span className="hm-tape-empty mute">等待采集事件…</span>
        )}
      </div>
    </div>
  );
}

// 滚动列表：items 按时间升序；窗口从最新一段开始，每 tick 从顶部推入下一条，到头后回绕。
function Rotator<T>({
  items,
  visible,
  rowH,
  interval,
  keyOf,
  render,
  className,
}: {
  items: T[];
  visible: number;
  rowH: number;
  interval: number;
  keyOf: (t: T) => string;
  render: (t: T) => ReactNode;
  className?: string;
}) {
  const n = items.length;
  const [head, setHead] = useState(-1);
  const list = useRef<HTMLUListElement>(null);
  useEffect(() => {
    if (n <= visible || reducedMotion()) return;
    const id = setInterval(() => setHead((h) => ((h < 0 ? n - 1 : h) + 1) % n), interval);
    return () => clearInterval(id);
  }, [n, visible, interval]);
  const i = head < 0 ? n - 1 : head % n;
  const count = Math.min(n, visible + 1);
  const shown = Array.from({ length: count }, (_, k) => items[(i - k + n) % n]);
  useGSAP(
    () => {
      const el = list.current;
      if (!el || head < 0) return;
      gsap.fromTo(el, { y: -rowH }, { y: 0, duration: 0.65, ease: "power3.out", overwrite: true });
      if (el.firstElementChild) {
        gsap.fromTo(el.firstElementChild, { opacity: 0 }, { opacity: 1, duration: 0.5, ease: "power1.out" });
      }
    },
    { dependencies: [head] },
  );
  return (
    <div className={`hm-rot ${className ?? ""}`} style={{ height: Math.min(n, visible) * rowH }}>
      <ul ref={list}>
        {shown.map((t) => (
          <li key={keyOf(t)} style={{ height: rowH }}>
            {render(t)}
          </li>
        ))}
      </ul>
    </div>
  );
}

/* ---------- 页面 ---------- */

export function Home() {
  const [meta, setMeta] = useState<Meta | null>(null);
  const [board, setBoard] = useState<Board | null>(null);
  const [feed, setFeed] = useState<Feed | null>(null);
  const [feedDone, setFeedDone] = useState(false);
  const [pair, setPair] = useState<Slice[]>([]);
  const [failed, setFailed] = useState(false);
  const [pulse, setPulse] = useState<Pulse | null>(null);
  const [intake, setIntake] = useState<Row[]>([]); // 时间升序，去重后的采集事件池
  const [tape, setTape] = useState<Row[]>([]);
  const main = useRef<HTMLElement>(null);

  useEffect(() => {
    let alive = true;
    (async () => {
      const [m, b, f] = await Promise.all([get<Meta>("/meta"), get<Board>("/discover"), get<Feed>("/feed")]);
      if (!alive) return;
      if (!m && !b && !f) setFailed(true);
      setMeta(m);
      setBoard(b);
      setFeed(f);
      setFeedDone(true);
      const cards = b ? [...b.formed, ...b.emerging, ...b.candidate] : [];
      const ids = PAIR.map((name) => cards.find((c) => c.name === name)?.id).filter(Boolean) as string[];
      const slices = await Promise.all(ids.map((id) => get<Slice>(`/graph/jobs/${id}`)));
      if (alive) setPair(slices.filter(Boolean) as Slice[]);
    })();
    return () => {
      alive = false;
    };
  }, []);

  useEffect(() => {
    let alive = true;
    const fetchPulse = async () => {
      const p = await get<Pulse>("/pulse");
      if (!alive || !p) return;
      setPulse(p);
      setIntake((prev) => {
        const known = new Set(prev.map((r) => r.id));
        const fresh = (p.intake ?? []).filter((r) => r.id && !known.has(r.id)).map(intakeRow);
        if (!fresh.length) return prev;
        return [...prev, ...fresh.reverse()].slice(-80);
      });
    };
    fetchPulse();
    const id = setInterval(fetchPulse, PULSE_INTERVAL);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, []);

  const events = useMemo<Row[]>(() => (feed?.events ?? []).map(eventRow).reverse(), [feed]);

  // 跑马灯只在首批数据到齐时铺一次，之后不重排，避免循环动画被反复重启。
  useEffect(() => {
    if (tape.length || !feedDone || (!intake.length && !events.length)) return;
    const mix = [...intake.slice(-24), ...events.slice(-12)].sort((a, b) => b.at.localeCompare(a.at));
    if (mix.length) setTape(mix);
  }, [tape.length, feedDone, intake, events]);

  const rows = useMemo(() => {
    if (!board) return [];
    const all = [...board.formed, ...board.emerging, ...board.candidate];
    return all.sort((a, b) => {
      const d = DOMAIN_ORDER.indexOf(a.domain) - DOMAIN_ORDER.indexOf(b.domain);
      if (d) return d;
      return (b.last_change ?? "").localeCompare(a.last_change ?? "");
    });
  }, [board]);

  const inGraph = board ? board.formed.length + board.emerging.length : undefined;
  const pairCards = rows.filter((c) => PAIR.includes(c.name));
  const samples = feed?.pipeline?.reduce((acc, row) => acc + row.n, 0);
  const release = meta?.graph_release;
  const retentionMin = meta?.resume_retention_seconds ? Math.round(meta.resume_retention_seconds / 60) : 60;
  const loading = !board && !failed;
  const rebuilding = board && rows.length === 0;
  const collect = pulse?.collect;

  // 进场：首屏两块随加载渐显；下方面板进入视口时逐个浮起。只跑一次。
  useGSAP(
    () => {
      if (reducedMotion()) return;
      gsap.from(".hm-hero-copy > *", { y: 14, opacity: 0, duration: 0.7, stagger: 0.08, ease: "power3.out" });
      gsap.from(".hm-readout", { y: 14, opacity: 0, duration: 0.7, delay: 0.15, ease: "power3.out" });
      gsap.from(".hm-tape", { opacity: 0, duration: 0.6, delay: 0.35 });
      gsap.from(".hm-body > *", { y: 16, opacity: 0, duration: 0.7, stagger: 0.1, delay: 0.25, ease: "power3.out" });
      // 不预先隐藏：元素默认可见，进入视口那一刻才从下方浮起，触发失败也不会留下空白。
      const below = gsap.utils.toArray<HTMLElement>(".hm-pulse .hm-panel, .hm-trust > div");
      ScrollTrigger.batch(below, {
        start: "top 96%",
        once: true,
        onEnter: (batch) => gsap.from(batch, { y: 16, opacity: 0, duration: 0.6, stagger: 0.08, ease: "power3.out", overwrite: true }),
      });
    },
    { scope: main },
  );

  // 热度条：数据到位后从左向右长出来。
  useGSAP(
    () => {
      if (reducedMotion() || !feed?.heat?.length) return;
      gsap.from(".hm-heat-track i", { scaleX: 0, transformOrigin: "0 50%", duration: 0.9, stagger: 0.05, ease: "power3.out" });
    },
    { dependencies: [feed], scope: main },
  );

  return (
    <main className="hm" ref={main}>
      {/* 顶部：定位 + 两个主入口 + 当前发布版本的真实读数 */}
      <section className="hm-hero">
        <div className="hm-hero-copy">
          <p className="hm-eyebrow">
            <span>岗位能力图谱</span>
            <span className="hm-dot" />
            <span>人工智能 · 大数据 · 智能系统 · 物联网</span>
          </p>
          <h1>
            招聘市场在变，
            <br />
            你的换档条件也在变。
          </h1>
          <p className="hm-lede">
            智演从四领域招聘数据流里发现新岗位、记录每个岗位要求边的增减，每条要求都能点到原文证据。对着一份简历，它只回答三件事：卡在哪、换邻近岗会不会更好、这个月先补哪几样。
          </p>
          <div className="hm-actions">
            <Link href="/diagnose" className="hm-btn solid">
              上传简历，做一次诊断
            </Link>
            <Link href="/graph" className="hm-btn">
              打开图谱工作台
            </Link>
            <span className="hm-actions-note">免登录 · 简历只留在会话里 {retentionMin} 分钟</span>
          </div>
        </div>

        <dl className="hm-readout" aria-label="当前发布版本读数">
          <div className="hm-readout-head">
            <dt>当前发布版本</dt>
            <dd>
              {release?.published_at ? day(release.published_at) : loading ? "…" : "尚未发布"}
              {release?.period ? <small>切片 {day(release.period)}</small> : null}
            </dd>
          </div>
          <div>
            <dt>入谱岗位</dt>
            <dd>{loading ? "…" : <Count value={inGraph} />}</dd>
          </div>
          <div>
            <dt>成型 / 萌芽</dt>
            <dd>
              {loading ? (
                "…"
              ) : (
                <span>
                  <Count value={board?.formed.length} /> / <Count value={board?.emerging.length} />
                </span>
              )}
            </dd>
          </div>
          <div>
            <dt>候选中</dt>
            <dd>{loading ? "…" : <Count value={board?.candidate.length} />}</dd>
          </div>
          <div>
            <dt>去重 JD 样本</dt>
            <dd>{loading ? "…" : <Count value={samples} />}</dd>
          </div>
          <div className="hm-readout-foot">
            <dt>数据口径</dt>
            <dd>每条要求边至少两个独立源；候选不入谱，不能对照简历。</dd>
          </div>
        </dl>
      </section>

      {/* 流水带：采集事件与演化事件混排，持续滚动 */}
      <Tape rows={tape} />

      {/* 主体：左侧岗位总览表，右侧诊断入口 */}
      <section className="hm-body">
        <div className="hm-panel hm-jobs">
          <header className="hm-panel-head">
            <h2>图谱里有哪些岗位</h2>
            <Link href="/discover">市场演化 →</Link>
          </header>
          <div className="hm-table-wrap">
            <table className="hm-table">
              <colgroup>
                <col />
                <col className="w-status" />
                <col className="w-num" />
                <col className="w-delta" />
                <col className="w-date" />
              </colgroup>
              <thead>
                <tr>
                  <th>岗位</th>
                  <th>状态</th>
                  <th className="num">独立源</th>
                  <th>本期 +/−</th>
                  <th>最近变化</th>
                </tr>
              </thead>
              <tbody>
                {loading
                  ? Array.from({ length: 8 }).map((_, i) => (
                      <tr key={i} className="hm-skeleton">
                        <td>
                          <i style={{ width: `${48 + (i % 3) * 14}%` }} />
                        </td>
                        <td>
                          <i style={{ width: 36 }} />
                        </td>
                        <td>
                          <i style={{ width: 20 }} />
                        </td>
                        <td>
                          <i style={{ width: 40 }} />
                        </td>
                        <td>
                          <i style={{ width: 70 }} />
                        </td>
                      </tr>
                    ))
                  : null}
                {failed ? (
                  <tr>
                    <td colSpan={5} className="hm-empty">
                      暂时连不上图谱服务。稍后刷新，或直接进入
                      <Link href="/diagnose">简历诊断</Link>。
                    </td>
                  </tr>
                ) : null}
                {rebuilding ? (
                  <tr>
                    <td colSpan={5} className="hm-empty">
                      图谱正在重建，本周期岗位尚未发布。发布后这里会按领域列出全部入谱岗位。
                    </td>
                  </tr>
                ) : null}
                {rows.map((c, i) => {
                  const first = i === 0 || rows[i - 1].domain !== c.domain;
                  const status = STATUS[c.status] ?? { label: c.status, tone: "mid" };
                  const href = c.status === "candidate" ? "/discover" : `/graph?job=${c.id}`;
                  return (
                    <tr key={c.id} className={first ? "hm-domain-first" : undefined}>
                      <td>
                        <Link href={href} className="hm-job">
                          {first ? <span className="hm-domain">{DOMAIN[c.domain] ?? c.domain}</span> : null}
                          <span className="hm-job-name">{c.name}</span>
                        </Link>
                      </td>
                      <td>
                        <span className={`pill ${status.tone}`}>{status.label}</span>
                      </td>
                      <td className="num">{c.n_sources ?? "—"}</td>
                      <td className="hm-delta">
                        {c.n_added ? <span className="rise">+{c.n_added}</span> : null}
                        {c.n_expired ? <span className="fall">−{c.n_expired}</span> : null}
                        {!c.n_added && !c.n_expired ? <span className="mute">·</span> : null}
                      </td>
                      <td className="mono mute">{c.last_change || "—"}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <p className="hm-panel-foot">
            成型 = 至少 10 个独立源或持续 6 个月且定义已批；萌芽 = 至少 3 个独立源、90 天窗；候选只开卷宗。
          </p>
        </div>

        <aside className="hm-panel hm-diag">
          <header className="hm-panel-head">
            <h2>对着简历算一次</h2>
            <span className="hm-panel-tag">约 3 分钟</span>
          </header>
          <ol className="hm-steps">
            <li>
              <b>上传并校对</b>
              <span>PDF 或 docx。系统抽出角色、年限、技能点与简历证据片段，你逐条确认。</span>
            </li>
            <li>
              <b>选两个对照岗</b>
              <span>按推荐序给三个可诊断岗位和前两条理由，你挑两个。</span>
            </li>
            <li>
              <b>看方向结论</b>
              <span>档位文案、缺口集、简历证据不足项、最小换档条件，以及本月先补哪三样。</span>
            </li>
          </ol>

          <div className="hm-pair">
            <p className="hm-pair-title">默认对照对 · 诊断页默认岗位与它最近的新岗</p>
            {PAIR.map((name) => {
              const card = pairCards.find((c) => c.name === name);
              const s = pair.find((x) => x.job.name === name);
              const required = s?.requires.filter((r) => (r.kind ?? "required") === "required").length;
              const preferred = s ? s.requires.length - (required ?? 0) : undefined;
              const companies = s ? new Set(s.evidence.map((e) => e.company).filter(Boolean)).size : card?.n_sources;
              const status = card ? STATUS[card.status] ?? { label: card.status, tone: "mid" } : undefined;
              return (
                <div className="hm-pair-job" key={name}>
                  <div className="hm-pair-name">
                    <span>{name}</span>
                    {status ? <span className={`pill ${status.tone}`}>{status.label}</span> : null}
                  </div>
                  {s ? (
                    <dl>
                      <div>
                        <dt>必备</dt>
                        <dd>{required}</dd>
                      </div>
                      <div>
                        <dt>加分</dt>
                        <dd>{preferred}</dd>
                      </div>
                      <div>
                        <dt>公司</dt>
                        <dd>{companies}</dd>
                      </div>
                    </dl>
                  ) : (
                    <p className="hm-pair-note">
                      {loading
                        ? "读取中…"
                        : card
                          ? `${card.n_sources ?? 0} 个独立源。岗位定义审核中，可看卷宗，暂不可诊断。`
                          : "本周期尚未入谱。"}
                    </p>
                  )}
                </div>
              );
            })}
          </div>

          <Link href="/diagnose" className="hm-btn solid wide">
            看看你离它们差几步
          </Link>

          <ul className="hm-privacy">
            <li>只发送提取后的简历文本，不传原文件。</li>
            <li>数据库不保存简历原文与身份信息。</li>
            <li>匿名会话最长保留 {retentionMin} 分钟，到期自动销毁。</li>
          </ul>
        </aside>
      </section>

      {/* 本周期在变什么：管线状态 + 三条流水/读数 */}
      <section className="hm-pulse">
        <div className="hm-panel">
          <header className="hm-panel-head">
            <h2>管线状态</h2>
            <span className="hm-panel-tag" data-live={collect?.running || undefined}>
              {collect?.running ? "采集中" : "待命"}
            </span>
          </header>
          {collect ? (
            <div className="hm-collect-status">
              <dl>
                <div>
                  <dt>门户</dt>
                  <dd>
                    <Count value={collect.sources ?? 0} />
                  </dd>
                </div>
                <div>
                  <dt>完成</dt>
                  <dd>
                    <Count value={collect.done ?? 0} />
                  </dd>
                </div>
                <div>
                  <dt>读取</dt>
                  <dd>
                    <Count value={collect.read} />
                  </dd>
                </div>
                <div>
                  <dt>入库</dt>
                  <dd>
                    <Count value={collect.ingested} />
                  </dd>
                </div>
              </dl>
              {collect.current && collect.current.length > 0 ? (
                <p className="hm-current-portals">正在采集：{collect.current.join("、")}</p>
              ) : null}
              {collect.started_at ? (
                <p className="hm-collect-time mute mono">
                  {collect.running
                    ? `开始于 ${day(collect.started_at)} ${hm(collect.started_at)}`
                    : `上次 ${day(collect.started_at)} ${hm(collect.started_at)}${
                        duration(collect.started_at, collect.finished_at) ? ` · 用时 ${duration(collect.started_at, collect.finished_at)}` : ""
                      }`}
                  {collect.failed ? ` · 失败 ${collect.failed}` : ""}
                </p>
              ) : null}
            </div>
          ) : (
            <p className="hm-empty-note">读取中…</p>
          )}
        </div>

        <div className="hm-panel hm-intake-panel">
          <header className="hm-panel-head">
            <h2>最近入库</h2>
            <span className="hm-panel-tag hm-tag-live">
              <i className="hm-live-dot" aria-hidden />
              采集事件
            </span>
          </header>
          {intake.length ? (
            <Rotator
              items={intake}
              visible={7}
              rowH={26}
              interval={INTAKE_TICK}
              keyOf={(r) => r.id}
              className="hm-intake"
              render={(r) => (
                <>
                  <span className="mono mute">{hms(r.at)}</span>
                  <span className="hm-kind">{r.type}</span>
                  <span className="hm-rot-text">{r.text}</span>
                </>
              )}
            />
          ) : (
            <p className="hm-empty-note">{pulse ? "暂无事件" : "读取中…"}</p>
          )}
        </div>

        <div className="hm-panel">
          <header className="hm-panel-head">
            <h2>技能覆盖热度</h2>
            <span className="hm-panel-tag">簇内覆盖率</span>
          </header>
          {feed?.heat?.length ? (
            <ol className="hm-heat">
              {feed.heat.slice(0, 10).map((row) => (
                <li key={row.id}>
                  <span className="hm-heat-name" title={row.name}>
                    {row.name}
                  </span>
                  <span className="hm-heat-track">
                    <i style={{ width: `${Math.min(100, row.v)}%` }} />
                  </span>
                  <span className="hm-heat-v">{row.v}%</span>
                </li>
              ))}
            </ol>
          ) : (
            <p className="hm-empty-note">{loading ? "读取中…" : "本周期尚无覆盖率数据。"}</p>
          )}
        </div>

        <div className="hm-panel">
          <header className="hm-panel-head">
            <h2>本周期升值 / 失效</h2>
            <span className="hm-panel-tag">切片差分</span>
          </header>
          {feed && (feed.rise.length || feed.fall.length) ? (
            <ul className="hm-diff">
              {feed.rise.slice(0, 6).map((r, i) => (
                <li key={`r${i}`}>
                  <span className="rise">+</span>
                  <span>{r.name}</span>
                  {r.job ? <span className="mute">{r.job}</span> : null}
                </li>
              ))}
              {feed.fall.slice(0, 6).map((r, i) => (
                <li key={`f${i}`}>
                  <span className="fall">−</span>
                  <span>{r.name}</span>
                  {r.job ? <span className="mute">{r.job}</span> : null}
                </li>
              ))}
            </ul>
          ) : (
            <p className="hm-empty-note">
              {loading ? "读取中…" : "本周期没有技能点升值或失效。要求边的稳定本身也是信号。"}
            </p>
          )}
          <p className="hm-panel-foot">
            覆盖率上升且刚过 30% 入池线记为升值；写入 valid_to 记为失效。观测中的技能不算缺口。
          </p>
        </div>

        <div className="hm-panel">
          <header className="hm-panel-head">
            <h2>最近演化事件</h2>
            <Link href="/discover">全部流水 →</Link>
          </header>
          {events.length ? (
            <Rotator
              items={events}
              visible={5}
              rowH={30}
              interval={EVENT_TICK}
              keyOf={(r) => r.id}
              className="hm-events"
              render={(r) => (
                <>
                  <span className="mono mute">{day(r.at).slice(5)}</span>
                  <span className="hm-rot-text" title={r.text}>
                    {r.text}
                  </span>
                  {r.review ? <span className={`pill ${reviewTone(r.review)}`}>{r.review}</span> : <span />}
                </>
              )}
            />
          ) : (
            <p className="hm-empty-note">{loading ? "读取中…" : "暂无事件。"}</p>
          )}
          {feed?.events?.length ? (
            <p className="hm-panel-foot">
              事件类型：{Array.from(new Set(feed.events.map((e) => kindLabel(e.kind ?? "")))).join(" · ")}。
              待审事件不进入公开图谱。
            </p>
          ) : null}
        </div>
      </section>

      {/* 为什么可信：写规则，不写口号，每格都能点到验证处 */}
      <section className="hm-trust">
        <div>
          <b>每条要求边有来源</b>
          <p>至少两个独立招聘源印证，点开技能点就是原文最短摘录与公司、观察时间。</p>
          <Link href="/graph">在工作台点一条看看 →</Link>
        </div>
        <div>
          <b>必备与加分不靠猜</b>
          <p>明确必备票或加分票占已分类票 60% 以上才定性质，否则只进待审。三类票数与原文并列展示。</p>
          <Link href="/discover">看某个岗位的卷宗 →</Link>
        </div>
        <div>
          <b>发布前有一道闸</b>
          <p>新岗位首次发布、核心必备新增、低置信抽取都先进待审队列。要求数异常的岗位暂停诊断。</p>
          <Link href="/admin">管理后台 →</Link>
        </div>
      </section>

      <footer className="hm-foot">
        <span>© 2026 智演 JobEvolution</span>
        <nav>
          <Link href="/graph">图谱工作台</Link>
          <Link href="/discover">市场演化</Link>
          <Link href="/diagnose">简历诊断</Link>
          <Link href="/admin">管理后台</Link>
        </nav>
      </footer>
    </main>
  );
}
