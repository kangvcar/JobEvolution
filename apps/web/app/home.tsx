"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { EventList, kindLabel } from "./feed-bits";
import "./home.css";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

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
type Feed = {
  emerging: number;
  formed: number;
  candidate: number;
  in_graph: number;
  pipeline: { source: string; n: number }[];
  heat: { id: string; name: string; v: number }[];
  events: { at: string; text: string; review?: string; kind?: string; n?: number; skills?: string[] }[];
  rise: { name: string; job?: string }[];
  fall: { name: string; job?: string }[];
};
type Slice = {
  job: { id: string; name: string; status: string };
  requires: { kind?: string }[];
  evidence: { company?: string }[];
};

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

function num(value: number | undefined | null) {
  return typeof value === "number" ? value.toLocaleString("zh-CN") : "—";
}

export function Home() {
  const [meta, setMeta] = useState<Meta | null>(null);
  const [board, setBoard] = useState<Board | null>(null);
  const [feed, setFeed] = useState<Feed | null>(null);
  const [pair, setPair] = useState<Slice[]>([]);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let alive = true;
    (async () => {
      const [m, b, f] = await Promise.all([get<Meta>("/meta"), get<Board>("/discover"), get<Feed>("/feed")]);
      if (!alive) return;
      if (!m && !b && !f) setFailed(true);
      setMeta(m);
      setBoard(b);
      setFeed(f);
      const cards = b ? [...b.formed, ...b.emerging, ...b.candidate] : [];
      const ids = PAIR.map((name) => cards.find((c) => c.name === name)?.id).filter(Boolean) as string[];
      const slices = await Promise.all(ids.map((id) => get<Slice>(`/graph/jobs/${id}`)));
      if (alive) setPair(slices.filter(Boolean) as Slice[]);
    })();
    return () => {
      alive = false;
    };
  }, []);

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

  return (
    <main className="hm">
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
            <dd>{loading ? "…" : num(inGraph)}</dd>
          </div>
          <div>
            <dt>成型 / 萌芽</dt>
            <dd>
              {loading ? "…" : `${num(board?.formed.length)} / ${num(board?.emerging.length)}`}
            </dd>
          </div>
          <div>
            <dt>候选中</dt>
            <dd>{loading ? "…" : num(board?.candidate.length)}</dd>
          </div>
          <div>
            <dt>去重 JD 样本</dt>
            <dd>{loading ? "…" : num(samples)}</dd>
          </div>
          <div className="hm-readout-foot">
            <dt>数据口径</dt>
            <dd>每条要求边至少两个独立源；候选不入谱，不能对照简历。</dd>
          </div>
        </dl>
      </section>

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
                      <td className="mono mute">{c.last_change ?? ""}</td>
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

      {/* 本周期在变什么：三格，全部来自 /feed */}
      <section className="hm-pulse">
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
          {feed ? (
            <EventList rows={feed.events.slice(0, 5)} />
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
