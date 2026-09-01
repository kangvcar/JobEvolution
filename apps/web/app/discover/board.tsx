"use client";

import Link from "next/link";
import { KeyboardEvent, useEffect, useState } from "react";
import { EventList, Heat, Pipe, kindLabel } from "../feed-bits";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const DOMAIN: Record<string, string> = {
  ai: "人工智能",
  data: "大数据",
  system: "智能系统",
  iot: "物联网",
};
const STAGES = [
  { key: "candidate", label: "候选" },
  { key: "emerging", label: "萌芽" },
  { key: "formed", label: "成型" },
] as const;

type Card = { id: string; name: string; status: string; domain: string; n_sources?: number };
type Board = {
  candidate: Card[];
  emerging: Card[];
  formed: Card[];
  formed_total?: number;
};
type Dossier = {
  id: string;
  name: string;
  status: string;
  domain: string;
  n_sources: number;
  sources: string[];
  evidence: { id: string; company: string; observed_at: string; source?: string }[];
  events: { id: string; kind: string; at: string; review: string }[];
  aliases_in: { id: string; name: string }[];
  alias_of: { id: string; name: string } | null;
  cluster?: { n: number; n_sources: number };
};
type Feed = {
  emerging: number;
  formed: number;
  candidate: number;
  pending: number;
  barred: number;
  pipeline: { source: string; n: number }[];
  heat: { name: string; v: number }[];
  events: { at: string; text: string; review?: string }[];
  rise: { name: string }[];
  fall: { name: string }[];
};

function pill(status: string) {
  if (status === "emerging") return "hot";
  if (status === "formed") return "ok";
  return "mid";
}

function statusLabel(status: string) {
  if (status === "candidate") return "未入谱";
  if (status === "emerging") return "萌芽";
  if (status === "formed") return "成型";
  return status;
}

function reviewLabel(review: string) {
  if (review === "pending") return "待审";
  if (review === "approved") return "已入谱";
  if (review === "auto_passed") return "自动通过";
  if (review === "rejected") return "驳回";
  return review;
}

export function DiscoverBoard() {
  const [board, setBoard] = useState<Board>({ candidate: [], emerging: [], formed: [] });
  const [feed, setFeed] = useState<Feed | null>(null);
  const [pick, setPick] = useState("");
  const [dossier, setDossier] = useState<Dossier | null>(null);

  useEffect(() => {
    fetch(`${API}/discover`)
      .then((r) => r.json())
      .then((body: Board) => {
        setBoard(body);
        const first = body.emerging[0] || body.candidate[0] || body.formed[0];
        if (first) setPick(first.id);
      })
      .catch(() => setBoard({ candidate: [], emerging: [], formed: [] }));
    fetch(`${API}/feed`)
      .then((r) => r.json())
      .then((body: Feed) => setFeed(body))
      .catch(() => setFeed(null));
  }, []);

  useEffect(() => {
    if (!pick) return;
    fetch(`${API}/discover/${encodeURIComponent(pick)}`)
      .then((r) => r.json())
      .then((body: Dossier) => setDossier(body))
      .catch(() => setDossier(null));
  }, [pick]);

  const order = [...board.candidate, ...board.emerging, ...board.formed];

  function onCardKey(event: KeyboardEvent<HTMLButtonElement>, id: string) {
    if (event.key !== "ArrowDown" && event.key !== "ArrowUp") return;
    event.preventDefault();
    const i = order.findIndex((card) => card.id === id);
    if (i < 0) return;
    const next =
      event.key === "ArrowDown"
        ? order[(i + 1) % order.length]
        : order[(i - 1 + order.length) % order.length];
    setPick(next.id);
    const el = document.querySelector<HTMLButtonElement>(`[data-job="${next.id}"]`);
    el?.focus();
  }

  return (
    <main id="main" className="page discover-page">
      <h1>发现</h1>
      <p className="hint">
        三列是漏斗。候选未入谱，只开卷宗，不能对照简历。别名不占候选列。管线、热度、流水在本页。
      </p>
      {feed ? (
        <dl className="readout">
          <div>
            <dt>候选</dt>
            <dd>{feed.candidate}</dd>
          </div>
          <div>
            <dt>萌芽</dt>
            <dd>{feed.emerging}</dd>
          </div>
          <div>
            <dt>成型</dt>
            <dd>{feed.formed}</dd>
          </div>
          <div>
            <dt>待审</dt>
            <dd>{feed.pending}</dd>
          </div>
          <div>
            <dt>拦下</dt>
            <dd>{feed.barred}</dd>
          </div>
        </dl>
      ) : null}
      <div className="disc-board">
        <div className="kanban">
          {STAGES.map((stage) => {
            const items = board[stage.key];
            const title =
              stage.key === "formed"
                ? `成型（切片） · ${items.length}/${board.formed_total ?? items.length}`
                : `${stage.label} · ${items.length}`;
            return (
              <div className="col" key={stage.key}>
                <h2>{title}</h2>
                {items.map((card) => (
                  <button
                    key={card.id}
                    className={`kitem${card.id === pick ? " on" : ""}`}
                    type="button"
                    data-job={card.id}
                    tabIndex={card.id === pick ? 0 : -1}
                    onClick={() => setPick(card.id)}
                    onKeyDown={(event) => onCardKey(event, card.id)}
                  >
                    <span className={`pill ${pill(card.status)}`}>
                      {statusLabel(card.status)}
                    </span>
                    <b>{card.name}</b>
                    <span className="meta">
                      {DOMAIN[card.domain] || card.domain} · 独立源 {card.n_sources ?? 0}
                    </span>
                  </button>
                ))}
              </div>
            );
          })}
        </div>
        <aside className="story dossier">
          {dossier ? (
            <>
              <span className={`pill ${pill(dossier.status)}`}>{statusLabel(dossier.status)}</span>
              <h2>{dossier.name}</h2>
              <p className="src">
                {DOMAIN[dossier.domain] || dossier.domain} · 独立源 {dossier.n_sources}
                {dossier.sources.length ? ` · ${dossier.sources.join(" · ")}` : ""}
              </p>
              {dossier.alias_of ? (
                <p className="hint">已并入 {dossier.alias_of.name}，不占候选列。</p>
              ) : null}
              {dossier.aliases_in.length ? (
                <p className="hint">
                  别名已并入：{dossier.aliases_in.map((row) => row.name).join("、")}
                </p>
              ) : null}
              <p className="mono">
                簇 {dossier.cluster?.n ?? dossier.evidence.length} 条 · 独立源 {dossier.n_sources} ·
                演化事件 {dossier.events.length}
              </p>
              {dossier.status === "candidate" ? (
                <p className="hint">未入谱。不能对照简历，不能进工作台。</p>
              ) : (
                <div className="row">
                  <Link className="primary" href={`/graph?job=${encodeURIComponent(dossier.id)}`}>
                    进工作台
                  </Link>
                </div>
              )}
              <h2 className="block-title">独立源</h2>
              <ul className="plain">
                {(dossier.sources.length ? dossier.sources : ["无"]).map((name) => (
                  <li key={name}>{name}</li>
                ))}
              </ul>
              <h2 className="block-title">证据</h2>
              <ul className="plain">
                {dossier.evidence.map((row) => (
                  <li key={row.id}>
                    {row.company || row.id} · {(row.observed_at || "").slice(0, 10)}
                  </li>
                ))}
              </ul>
              <h2 className="block-title">演化事件</h2>
              <ul className="plain">
                {dossier.events.map((row) => (
                  <li key={row.id}>
                    {kindLabel(row.kind)} · {reviewLabel(row.review)} · {(row.at || "").slice(0, 10)}
                  </li>
                ))}
              </ul>
            </>
          ) : (
            <p className="hint">点一张卡打开卷宗。</p>
          )}
        </aside>
      </div>
      <div className="disc-lower">
        <section>
          <h2>发现管线</h2>
          <p className="hint">与总览同一口径。</p>
          <Pipe rows={feed?.pipeline || []} />
        </section>
        <section>
          <h2>技能热度</h2>
          <p className="hint">谱内岗位占比。与总览同一张表。</p>
          <Heat rows={feed?.heat || []} />
        </section>
        <aside className="move">
          <h2 className="rise">升值</h2>
          <ul>
            {(feed?.rise || []).map((row) => (
              <li key={row.name}>
                <span>{row.name}</span>
                <span className="pt rise">新增</span>
              </li>
            ))}
          </ul>
          <h2 className="fall">贬值</h2>
          <ul>
            {(feed?.fall || []).map((row) => (
              <li key={row.name}>
                <span>{row.name}</span>
                <span className="pt fall">失效</span>
              </li>
            ))}
          </ul>
        </aside>
      </div>
      <section className="disc-feed">
        <h2>演化流水</h2>
        <p className="hint">边级事件，与总览同一份。</p>
        <EventList rows={feed?.events || []} />
      </section>
    </main>
  );
}
