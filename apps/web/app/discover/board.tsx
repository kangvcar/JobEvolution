"use client";

import Link from "next/link";
import { KeyboardEvent, useEffect, useMemo, useState } from "react";
import { EventList, Heat, Pipe } from "../feed-bits";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const DOMAIN: Record<string, string> = {
  ai: "AI",
  data: "大数据",
  system: "智能系统",
  iot: "物联网",
};
const STAGES = [
  { key: "candidate", label: "候选" },
  { key: "emerging", label: "萌芽" },
  { key: "formed", label: "成型" },
] as const;
type Stage = (typeof STAGES)[number]["key"];

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
type Board = { candidate: Card[]; emerging: Card[]; formed: Card[]; formed_total?: number };
type Requirement = {
  skill_id: string;
  name: string;
  kind: string;
  category: string;
  n_sources: number;
  excerpt: string;
  valid_from: string;
};
type Event = { id: string; kind: string; at: string; review: string; skill_name: string; excerpt: string };
type Dossier = {
  id: string;
  name: string;
  status: string;
  domain: string;
  n_sources: number;
  n_window: number;
  sources: string[];
  evidence: { id: string; company: string; observed_at: string; source?: string }[];
  requires: Requirement[];
  events: Event[];
  aliases_in: { id: string; name: string }[];
  alias_of: { id: string; name: string } | null;
  period_delta?: { added?: { name: string }[]; expired?: { name: string }[] };
  neighbor?: { job_id: string; name: string; shared_requirements: string[]; unique_requirements: string[] } | null;
};
type Feed = {
  emerging: number;
  formed: number;
  candidate: number;
  pending: number;
  barred: number;
  pipeline: { source: string; n: number }[];
  heat: { name: string; v: number }[];
  events: { at: string; text: string; review?: string; kind?: string; n?: number; skills?: string[] }[];
  rise: { name: string }[];
  fall: { name: string }[];
};

const STAGE_TIP: Record<string, string> = {
  candidate: "管线发现但未入谱的岗位，只开卷宗",
  emerging: "至少 3 家去重公司在 90 天内招聘，且判为新岗位而非别名",
  formed: "至少 10 家去重公司或持续 6 个月以上，岗位定义已获批",
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
  if (review === "retracted") return "已撤回";
  return review;
}

function kindLabel(kind: string) {
  if (kind === "required") return "必备";
  if (kind === "bonus" || kind === "preferred") return "加分";
  if (kind === "observed") return "观测中";
  return kind;
}

function day(at: string) {
  return (at || "").slice(0, 10);
}

/** 结论只说数据说了什么，不重复状态名。 */
function verdict(d: Dossier) {
  const added = d.period_delta?.added?.length ?? 0;
  const expired = d.period_delta?.expired?.length ?? 0;
  const change = added || expired ? `本周期要求 +${added} −${expired}` : "本周期要求没有变化";
  if (d.alias_of) return `已并入${d.alias_of.name}，去那份卷宗看要求。`;
  if (d.status === "formed") return `可以开始比较。${d.n_window} 家公司近 90 天仍在招，${change}。`;
  if (d.status === "emerging") return `继续观察。近 90 天 ${d.n_window} 家公司在招，${change}，还差成型门槛。`;
  if (d.n_sources <= 1) return `只有 ${d.n_sources} 家公司的样本，还不能判断是岗位还是个例。`;
  return `${d.n_sources} 家公司出现过，要求仍在审核，先看下面已入谱的部分。`;
}

/** 时间线按日和审核状态归并，一天几十条要求变化压成一行。 */
function groupEvents(events: Event[]) {
  const map = new Map<string, { day: string; review: string; names: string[]; n: number }>();
  for (const e of events) {
    const key = `${day(e.at)}|${e.review}`;
    const g = map.get(key) ?? { day: day(e.at), review: e.review, names: [], n: 0 };
    g.n += 1;
    if (e.skill_name && g.names.length < 6 && !g.names.includes(e.skill_name)) g.names.push(e.skill_name);
    map.set(key, g);
  }
  return [...map.values()].sort((a, b) => (a.day < b.day ? 1 : -1));
}

export function DiscoverBoard() {
  const [board, setBoard] = useState<Board>({ candidate: [], emerging: [], formed: [] });
  const [feed, setFeed] = useState<Feed | null>(null);
  const [pick, setPick] = useState("");
  const [dossier, setDossier] = useState<Dossier | null>(null);
  const [stage, setStage] = useState<"all" | Stage>("all");
  const [domain, setDomain] = useState("all");
  const [q, setQ] = useState("");
  const [allHeat, setAllHeat] = useState(false);
  const [allCompanies, setAllCompanies] = useState(false);

  useEffect(() => {
    fetch(`${API}/discover`)
      .then((r) => r.json())
      .then((body: Board) => {
        setBoard(body);
        const first = body.emerging[0] || body.formed[0] || body.candidate[0];
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
    setAllCompanies(false);
    fetch(`${API}/discover/${encodeURIComponent(pick)}`)
      .then((r) => r.json())
      .then((body: Dossier) => setDossier(body))
      .catch(() => setDossier(null));
  }, [pick]);

  const all = useMemo(() => [...board.emerging, ...board.formed, ...board.candidate], [board]);
  const domains = useMemo(() => [...new Set(all.map((c) => c.domain))], [all]);
  const rows = useMemo(() => {
    const kw = q.trim().toLowerCase();
    return all
      .filter((c) => stage === "all" || c.status === stage)
      .filter((c) => domain === "all" || c.domain === domain)
      .filter((c) => !kw || c.name.toLowerCase().includes(kw))
      .sort((a, b) => ((a.last_change ?? "") < (b.last_change ?? "") ? 1 : -1));
  }, [all, stage, domain, q]);

  function onRowKey(event: KeyboardEvent<HTMLTableRowElement>, id: string) {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      setPick(id);
      return;
    }
    if (event.key !== "ArrowDown" && event.key !== "ArrowUp") return;
    event.preventDefault();
    const i = rows.findIndex((c) => c.id === id);
    if (i < 0) return;
    const next = event.key === "ArrowDown" ? rows[(i + 1) % rows.length] : rows[(i - 1 + rows.length) % rows.length];
    setPick(next.id);
    document.querySelector<HTMLTableRowElement>(`[data-job="${next.id}"]`)?.focus();
  }

  const grouped = useMemo(() => {
    if (!dossier) return [];
    const byCat = new Map<string, Requirement[]>();
    for (const r of dossier.requires) {
      const k = r.category || "其他";
      byCat.set(k, [...(byCat.get(k) ?? []), r]);
    }
    return [...byCat.entries()]
      .map(([cat, list]) => [cat, list.sort((a, b) => b.n_sources - a.n_sources)] as const)
      .sort((a, b) => b[1].length - a[1].length);
  }, [dossier]);
  const pendingN = dossier ? dossier.events.filter((e) => e.review === "pending").length : 0;
  const timeline = useMemo(() => (dossier ? groupEvents(dossier.events) : []), [dossier]);
  const evidenceByCompany = useMemo(() => {
    const m = new Map<string, string[]>();
    for (const e of dossier?.evidence ?? []) {
      const c = (e.company || "").trim();
      if (!c) continue;
      m.set(c, [...(m.get(c) ?? []), day(e.observed_at)].sort().reverse());
    }
    return m;
  }, [dossier]);
  const companies = dossier?.sources ?? [];
  const shownCompanies = allCompanies ? companies : companies.slice(0, 8);
  const heat = feed?.heat ?? [];

  return (
    <main id="main" className="page discover-page">
      <header className="disc-bar">
        <h1>市场演化</h1>
        {feed ? (
          <dl className="disc-readout">
            <div title="候选、萌芽、成型岗位合计，别名不计">
              <dt>岗位</dt>
              <dd>{feed.candidate + feed.emerging + feed.formed}</dd>
            </div>
            <div title="等待人工裁决的岗位变化条数，批准后才进卷宗">
              <dt>审核中</dt>
              <dd>{feed.pending}</dd>
            </div>
            <div title="抽取失败被拦下的样本，不进任何岗位">
              <dt>暂不展示</dt>
              <dd>{feed.barred}</dd>
            </div>
          </dl>
        ) : null}
        <input
          className="disc-search"
          type="search"
          placeholder="搜索岗位"
          aria-label="搜索岗位"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
      </header>
      <p className="disc-guide hint">筛选岗位状态或领域后，点一行查看卷宗。候选岗位只开放观察，不能用于简历对照。</p>

      <div className="disc-filters">
        <div className="market-filters" role="group" aria-label="岗位状态筛选">
          <button type="button" aria-pressed={stage === "all"} onClick={() => setStage("all")}>全部 {all.length}</button>
          {STAGES.map((s) => (
            <button key={s.key} type="button" title={STAGE_TIP[s.key]} aria-pressed={stage === s.key} onClick={() => setStage(s.key)}>
              {s.label} {board[s.key].length}
            </button>
          ))}
        </div>
        <div className="disc-domains" role="group" aria-label="领域筛选">
          <button type="button" aria-pressed={domain === "all"} onClick={() => setDomain("all")}>全部领域</button>
          {domains.map((d) => (
            <button key={d} type="button" aria-pressed={domain === d} onClick={() => setDomain(d)}>{DOMAIN[d] || d}</button>
          ))}
        </div>
        <p className="hint" role="status" aria-live="polite">
          显示 {rows.length} / {all.length} 个岗位{q.trim() ? `，搜索“${q.trim()}”` : ""}。
          {(stage !== "all" || domain !== "all" || q.trim()) && <button type="button" className="disc-more" onClick={() => { setStage("all"); setDomain("all"); setQ(""); }}>清除筛选</button>}
        </p>
      </div>

      <div className="disc-board">
        <section className="disc-list" aria-label="岗位列表">
          <table className="disc-table">
            <colgroup>
              <col className="w-status" />
              <col />
              <col className="w-domain" />
              <col className="w-num" />
              <col className="w-delta" />
              <col className="w-date" />
            </colgroup>
            <thead>
              <tr>
                <th>状态</th>
                <th>岗位</th>
                <th>领域</th>
                <th className="num" title="去重招聘公司数">公司</th>
                <th className="num" title="本周期新增 / 失效的岗位要求数">本期</th>
                <th title="最近一次岗位要求变化">最近变化</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((c) => (
                <tr
                  key={c.id}
                  data-job={c.id}
                  tabIndex={c.id === pick ? 0 : -1}
                  aria-current={c.id === pick ? "true" : undefined}
                  onClick={(e) => {
                    setPick(c.id);
                    e.currentTarget.focus();
                  }}
                  onKeyDown={(e) => onRowKey(e, c.id)}
                >
                  <td><span className={`pill ${pill(c.status)}`}>{statusLabel(c.status)}</span></td>
                  <td className="disc-name" title={c.name}>{c.name}</td>
                  <td className="mute">{DOMAIN[c.domain] || c.domain}</td>
                  <td className="num">{c.n_sources ?? 0}</td>
                  <td className="num disc-delta">
                    {c.n_added ? <span className="rise">+{c.n_added}</span> : null}
                    {c.n_expired ? <span className="fall">−{c.n_expired}</span> : null}
                    {!c.n_added && !c.n_expired ? <span className="mute">–</span> : null}
                  </td>
                  <td className="mute mono">{c.last_change || "–"}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {!rows.length && <p className="empty">当前筛选没有岗位。</p>}
        </section>

        <aside className="dossier-pane" aria-label="岗位卷宗">
          {dossier ? (
            <>
              <header className="dossier-head">
                <div className="dossier-title">
                  <span className={`pill ${pill(dossier.status)}`}>{statusLabel(dossier.status)}</span>
                  <h2>{dossier.name}</h2>
                </div>
                {dossier.status === "candidate" || dossier.alias_of ? (
                  <button type="button" className="primary" disabled title="未入谱的岗位不能对照简历，也不能进工作台">进工作台</button>
                ) : (
                  <Link className="primary" href={`/graph?job=${encodeURIComponent(dossier.id)}`}>进工作台</Link>
                )}
              </header>
              <p className="src dossier-src">
                {DOMAIN[dossier.domain] || dossier.domain} · 近 90 天 {dossier.n_window} 家 / 累计 {dossier.n_sources} 家去重公司招聘
              </p>
              <p className="dossier-verdict">{verdict(dossier)}</p>
              {dossier.aliases_in.length ? (
                <p className="hint">别名已并入：{dossier.aliases_in.map((r) => r.name).join("、")}</p>
              ) : null}

              <section className="dossier-sec">
                <h3>本周期变化</h3>
                {dossier.period_delta?.added?.length || dossier.period_delta?.expired?.length ? (
                  <div className="chips">
                    {dossier.period_delta?.added?.map((r) => <span key={`a-${r.name}`} className="chip rise">+ {r.name}</span>)}
                    {dossier.period_delta?.expired?.map((r) => <span key={`e-${r.name}`} className="chip fall">− {r.name}</span>)}
                  </div>
                ) : (
                  <p className="hint">本周期没有新增或失效的岗位要求。</p>
                )}
              </section>

              <section className="dossier-sec">
                <h3>
                  岗位要求 <span className="count">{dossier.requires.length}</span>
                  {pendingN ? <Link className="dossier-pending" href="/admin">另有 {pendingN} 条待审</Link> : null}
                </h3>
                {grouped.length ? (
                  <table className="req-table">
                    <colgroup>
                      <col />
                      <col className="w-kind" />
                      <col className="w-num" />
                      <col className="w-date" />
                    </colgroup>
                    <thead>
                      <tr>
                        <th>技能</th>
                        <th>性质</th>
                        <th className="num" title="要求出现在多少条招聘样本里">样本</th>
                        <th>首次出现</th>
                      </tr>
                    </thead>
                    {grouped.map(([cat, list]) => (
                      <tbody key={cat}>
                        <tr className="req-cat">
                          <th colSpan={4}>{cat} <span className="count">{list.length}</span></th>
                        </tr>
                        {list.map((r) => (
                          <tr key={r.skill_id} title={r.excerpt || undefined}>
                            <td className="disc-name">{r.name}</td>
                            <td className="mute">{kindLabel(r.kind)}</td>
                            <td className="num">{r.n_sources || "–"}</td>
                            <td className="mute mono">{r.valid_from ? r.valid_from.slice(0, 7) : "–"}</td>
                          </tr>
                        ))}
                      </tbody>
                    ))}
                  </table>
                ) : (
                  <p className="hint">{pendingN ? "要求都还在审核中，批准后出现在这里。" : "尚无已入谱的岗位要求。"}</p>
                )}
              </section>

              <section className="dossier-sec">
                <h3>招聘公司 <span className="count">{companies.length}</span></h3>
                {companies.length ? (
                  <div className="chips">
                    {shownCompanies.map((c) => {
                      const dates = evidenceByCompany.get(c) ?? [];
                      return (
                        <span key={c} className="chip" title={dates.length ? `样本 ${dates.length} 条，最近 ${dates[0]}` : undefined}>
                          {c}
                          {dates.length > 1 ? <i>{dates.length}</i> : null}
                        </span>
                      );
                    })}
                    {companies.length > 8 ? (
                      <button type="button" className="chip more" onClick={() => setAllCompanies((v) => !v)}>
                        {allCompanies ? "收起" : `等 ${companies.length} 家`}
                      </button>
                    ) : null}
                  </div>
                ) : (
                  <p className="hint">暂无公司证据。</p>
                )}
              </section>

              {dossier.neighbor ? (
                <section className="dossier-sec">
                  <h3>相近岗位</h3>
                  <p className="hint">
                    与 <Link href={`/graph?job=${encodeURIComponent(dossier.neighbor.job_id)}`}>{dossier.neighbor.name}</Link> 共有 {dossier.neighbor.shared_requirements.length} 项要求
                    {dossier.neighbor.shared_requirements.length ? `（${dossier.neighbor.shared_requirements.slice(0, 4).join("、")}）` : ""}
                    ，对方独有 {dossier.neighbor.unique_requirements.length} 项
                    {dossier.neighbor.unique_requirements.length ? `（${dossier.neighbor.unique_requirements.slice(0, 4).join("、")}）` : ""}。
                  </p>
                </section>
              ) : null}

              <details className="dossier-sec dossier-timeline">
                <summary>
                  <h3>岗位变化时间线 <span className="count">{dossier.events.length}</span></h3>
                </summary>
                {timeline.length ? (
                  <ul className="timeline">
                    {timeline.map((g) => (
                      <li key={`${g.day}-${g.review}`}>
                        <span className="mono">{g.day || "未知日期"}</span>
                        <span>
                          <span className={`pill ${g.review === "pending" ? "mid" : g.review === "rejected" || g.review === "retracted" ? "warn" : "ok"}`}>{reviewLabel(g.review)}</span>
                          {" "}{g.n} 条{g.names.length ? `：${g.names.join("、")}${g.n > g.names.length ? " 等" : ""}` : ""}
                        </span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="hint">暂无岗位变化记录。</p>
                )}
              </details>
            </>
          ) : (
            <p className="hint">在左侧选一个岗位打开卷宗。</p>
          )}
        </aside>
      </div>

      <details className="disc-method">
        <summary>本周期怎么算出来的</summary>
        <div className="disc-lower">
          <section>
            <h2>数据来源</h2>
            <p className="hint">招聘样本按采集渠道计数，与首页同一口径。</p>
            <Pipe rows={feed?.pipeline || []} />
          </section>
          <section>
            <h2>技能出现情况</h2>
            <p className="hint">公开岗位要求里出现的比例。</p>
            <Heat rows={allHeat ? heat : heat.slice(0, 15)} />
            {heat.length > 15 ? (
              <button type="button" className="disc-more" onClick={() => setAllHeat((v) => !v)}>
                {allHeat ? "收起" : `展开全部 ${heat.length} 项`}
              </button>
            ) : null}
          </section>
          <aside className="move">
            <h2 className="rise">升值</h2>
            {feed?.rise?.length ? (
              <ul>{feed.rise.map((r) => <li key={r.name}><span>{r.name}</span><span className="tag rise">新增</span></li>)}</ul>
            ) : (
              <p className="hint">本周期没有新增要求。</p>
            )}
            <h2 className="fall">贬值</h2>
            {feed?.fall?.length ? (
              <ul>{feed.fall.map((r) => <li key={r.name}><span>{r.name}</span><span className="tag fall">失效</span></li>)}</ul>
            ) : (
              <p className="hint">本周期没有失效要求。</p>
            )}
          </aside>
        </div>
        <section className="disc-feed">
          <h2>演化流水</h2>
          <p className="hint">最近的岗位要求和状态变化，同一岗位同一天的新增归成一行。</p>
          <EventList rows={feed?.events || []} />
        </section>
      </details>
    </main>
  );
}
